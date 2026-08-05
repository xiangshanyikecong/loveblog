# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Cottage shared ledger (情侣账本 / AA 记账) routes.

A single expense ledger shared by both partners. Amounts are stored in cents.
Each entry records who paid (``payer``) and how it is split (``split_type``),
which drives the net "who owes whom" balance returned by ``/summary``.

Endpoints under ``/v1/cottage/ledger``:

- ``POST   /v1/cottage/ledger``          — log an expense
- ``GET    /v1/cottage/ledger``          — list (?category, ?month=YYYY-MM, paged)
- ``GET    /v1/cottage/ledger/summary``  — totals, per-payer, per-category, balance
- ``PATCH  /v1/cottage/ledger/{leid}``   — edit fields
- ``DELETE /v1/cottage/ledger/{leid}``   — soft delete
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.core.i18n import get_message
from app.db.session import get_db
from app.models.ledger_entry import LedgerEntry, SplitType
from app.models.user import User
from app.schemas.ledger import (
    LedgerBalance,
    LedgerCategoryStat,
    LedgerCreateRequest,
    LedgerListResponse,
    LedgerPayerStat,
    LedgerResponse,
    LedgerSummaryResponse,
    LedgerUpdateRequest,
)
from app.services.notifications import notify_partners, partner_recipients


router = APIRouter(prefix="/cottage/ledger", tags=["cottage-ledger"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _counterpart(db: Session, current_user: User) -> User | None:
    partners = partner_recipients(db, exclude_user_id=current_user.id)
    return partners[0] if partners else None


def _to_response(entry: LedgerEntry) -> LedgerResponse:
    return LedgerResponse(
        leid=entry.leid,
        title=entry.title,
        note=entry.note,
        amount_cents=entry.amount_cents,
        category=entry.category,
        split_type=entry.split_type,
        spent_on=entry.spent_on,
        payer_uid=entry.payer.uid if entry.payer else "",
        payer_nickname=entry.payer.nickname if entry.payer else "",
        author_uid=entry.author.uid if entry.author else "",
        author_nickname=entry.author.nickname if entry.author else "",
        created_at=entry.created_at,
    )


def _load_entry(db: Session, leid: str) -> LedgerEntry:
    entry = (
        db.query(LedgerEntry)
        .options(joinedload(LedgerEntry.author), joinedload(LedgerEntry.payer))
        .filter(LedgerEntry.leid == leid, LedgerEntry.deleted_at.is_(None))
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger entry not found")
    return entry


def _month_bounds(month: str) -> tuple[date, date]:
    """Return [start, end_exclusive) for a ``YYYY-MM`` string."""
    try:
        year_s, mon_s = month.split("-")
        year, mon = int(year_s), int(mon_s)
        start = date(year, mon, 1)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=get_message("error.invalid_month_format")
        ) from exc
    end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
    return start, end


def _resolve_payer_id(payer: str, current_user: User, counterpart: User | None) -> int:
    if payer == "partner":
        if counterpart is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=get_message("error.no_partner_for_payer")
            )
        return counterpart.id
    return current_user.id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=LedgerResponse, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: LedgerCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerResponse:
    ensure_partner(current_user)
    counterpart = _counterpart(db, current_user)
    payer_id = _resolve_payer_id(payload.payer, current_user, counterpart)

    entry = LedgerEntry(
        author_id=current_user.id,
        payer_id=payer_id,
        title=payload.title,
        note=payload.note,
        amount_cents=payload.amount_cents,
        category=payload.category,
        split_type=payload.split_type,
        spent_on=payload.spent_on,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    notify_partners(
        db,
        type="ledger.created",
        title=f"{current_user.nickname} 记了一笔账",
        body=f"{entry.title} · ¥{entry.amount_cents / 100:.2f}",
        link="/cottage/ledger",
        source_type="ledger",
        source_id=entry.leid,
        exclude_user_id=current_user.id,
    )
    db.commit()
    return _to_response(_load_entry(db, entry.leid))


@router.get("", response_model=LedgerListResponse)
def list_entries(
    category: Annotated[str | None, Query()] = None,
    month: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerListResponse:
    ensure_partner(current_user)

    query = db.query(LedgerEntry).filter(LedgerEntry.deleted_at.is_(None))
    if category:
        query = query.filter(LedgerEntry.category == category)
    if month:
        start, end = _month_bounds(month)
        query = query.filter(LedgerEntry.spent_on >= start, LedgerEntry.spent_on < end)

    total = query.count()
    offset = (page - 1) * page_size
    items = (
        query.options(joinedload(LedgerEntry.author), joinedload(LedgerEntry.payer))
        .order_by(LedgerEntry.spent_on.desc(), LedgerEntry.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return LedgerListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + page_size) < total,
    )


@router.get("/summary", response_model=LedgerSummaryResponse)
def ledger_summary(
    month: Annotated[str | None, Query()] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerSummaryResponse:
    ensure_partner(current_user)
    counterpart = _counterpart(db, current_user)

    query = (
        db.query(LedgerEntry)
        .options(joinedload(LedgerEntry.payer))
        .filter(LedgerEntry.deleted_at.is_(None))
    )
    if month:
        start, end = _month_bounds(month)
        query = query.filter(LedgerEntry.spent_on >= start, LedgerEntry.spent_on < end)
    entries = query.all()

    # Per-payer total paid and per-category total spent.
    paid: dict[int, int] = {}
    by_category: dict[str, int] = {}
    # Net balance keyed by user id (positive → others owe this user).
    net: dict[int, int] = {current_user.id: 0}
    if counterpart is not None:
        net[counterpart.id] = 0

    users: dict[int, User] = {current_user.id: current_user}
    if counterpart is not None:
        users[counterpart.id] = counterpart

    total_spent = 0
    for entry in entries:
        total_spent += entry.amount_cents
        paid[entry.payer_id] = paid.get(entry.payer_id, 0) + entry.amount_cents
        cat = entry.category or "未分类"
        by_category[cat] = by_category.get(cat, 0) + entry.amount_cents
        if entry.payer is not None:
            users.setdefault(entry.payer_id, entry.payer)

        if entry.split_type == SplitType.treat.value:
            continue
        payer_id = entry.payer_id
        other_id = next((uid for uid in net if uid != payer_id), None)
        if other_id is None or payer_id not in net:
            continue
        owe = (
            entry.amount_cents
            if entry.split_type == SplitType.owed_full.value
            else entry.amount_cents // 2
        )
        net[payer_id] += owe
        net[other_id] -= owe

    by_payer = [
        LedgerPayerStat(
            uid=users[uid].uid if uid in users else "",
            nickname=users[uid].nickname if uid in users else "",
            paid_cents=amount,
        )
        for uid, amount in sorted(paid.items(), key=lambda kv: kv[1], reverse=True)
    ]
    category_stats = [
        LedgerCategoryStat(category=cat, amount_cents=amount)
        for cat, amount in sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
    ]

    balance = _build_balance(net, users)

    return LedgerSummaryResponse(
        month=month,
        total_spent_cents=total_spent,
        entry_count=len(entries),
        by_payer=by_payer,
        by_category=category_stats,
        balance=balance,
    )


def _build_balance(net: dict[int, int], users: dict[int, User]) -> LedgerBalance:
    creditor_id = max(net, key=lambda uid: net[uid]) if net else None
    if creditor_id is None or net[creditor_id] <= 0:
        return LedgerBalance(settled=True)
    debtor_id = min(net, key=lambda uid: net[uid])
    amount = net[creditor_id]
    creditor = users.get(creditor_id)
    debtor = users.get(debtor_id)
    if creditor is None or debtor is None:
        return LedgerBalance(settled=True)
    return LedgerBalance(
        settled=False,
        debtor_uid=debtor.uid,
        debtor_nickname=debtor.nickname,
        creditor_uid=creditor.uid,
        creditor_nickname=creditor.nickname,
        amount_cents=amount,
    )


@router.patch("/{leid}", response_model=LedgerResponse)
def update_entry(
    leid: str,
    payload: LedgerUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerResponse:
    ensure_partner(current_user)
    entry = _load_entry(db, leid)

    data = payload.model_dump(exclude_unset=True)
    for field in ("title", "note", "amount_cents", "category", "split_type", "spent_on"):
        if field in data:
            setattr(entry, field, data[field])
    if "payer" in data:
        counterpart = _counterpart(db, current_user)
        entry.payer_id = _resolve_payer_id(data["payer"], current_user, counterpart)
    entry.version += 1
    db.commit()
    return _to_response(_load_entry(db, leid))


@router.delete("/{leid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_entry(
    leid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_partner(current_user)
    entry = _load_entry(db, leid)
    entry.deleted_at = datetime.now(timezone.utc)
    db.commit()
