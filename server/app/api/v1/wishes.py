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

"""Cottage wishlist (心愿单) routes.

A single list shared by both partners: things they want to do / places to go /
gifts to get together. Ownership is shared — either partner may create, edit,
complete / reopen and delete any wish. All endpoints are partner-only.

Endpoints under ``/v1/cottage/wishes``:

- ``POST   /v1/cottage/wishes``            — create a wish
- ``GET    /v1/cottage/wishes``            — list wishes (optional ?status filter)
- ``GET    /v1/cottage/wishes/{wid}``      — single wish
- ``PATCH  /v1/cottage/wishes/{wid}``      — edit fields
- ``POST   /v1/cottage/wishes/{wid}/complete`` — mark realised
- ``POST   /v1/cottage/wishes/{wid}/reopen``   — move back to pending
- ``DELETE /v1/cottage/wishes/{wid}``      — soft delete
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.wish import Wish, WishStatus
from app.schemas.wish import (
    WishCreateRequest,
    WishListResponse,
    WishResponse,
    WishUpdateRequest,
)
from app.services.notifications import notify_partners


router = APIRouter(prefix="/cottage/wishes", tags=["cottage-wishlist"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_response(wish: Wish) -> WishResponse:
    return WishResponse(
        wid=wish.wid,
        title=wish.title,
        description=wish.description,
        category=wish.category,
        status=wish.status,
        priority=wish.priority,
        target_date=wish.target_date,
        author_uid=wish.author.uid if wish.author else "",
        author_nickname=wish.author.nickname if wish.author else "",
        completed_at=wish.completed_at,
        completed_by_uid=wish.completed_by.uid if wish.completed_by else None,
        completed_by_nickname=wish.completed_by.nickname if wish.completed_by else None,
        created_at=wish.created_at,
    )


def _load_wish(db: Session, wid: str) -> Wish:
    wish = (
        db.query(Wish)
        .options(joinedload(Wish.author), joinedload(Wish.completed_by))
        .filter(Wish.wid == wid, Wish.deleted_at.is_(None))
        .first()
    )
    if wish is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wish not found")
    return wish


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=WishResponse, status_code=status.HTTP_201_CREATED)
def create_wish(
    payload: WishCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> WishResponse:
    ensure_partner(current_user)
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Idempotency-Key")
        existing = (
            db.query(Wish)
            .options(joinedload(Wish.author), joinedload(Wish.completed_by))
            .filter(
                Wish.author_id == current_user.id,
                Wish.client_idempotency_key == idempotency_key,
                Wish.deleted_at.is_(None),
            )
            .first()
        )
        if existing is not None:
            return _to_response(existing)
    wish = Wish(
        author_id=current_user.id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        target_date=payload.target_date,
        priority=payload.priority,
        status=WishStatus.pending.value,
        client_idempotency_key=idempotency_key,
    )
    db.add(wish)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key is None:
            raise
        existing = (
            db.query(Wish)
            .options(joinedload(Wish.author), joinedload(Wish.completed_by))
            .filter(
                Wish.author_id == current_user.id,
                Wish.client_idempotency_key == idempotency_key,
                Wish.deleted_at.is_(None),
            )
            .first()
        )
        if existing is None:
            raise
        return _to_response(existing)
    db.refresh(wish)

    notify_partners(
        db,
        type="wish.created",
        title=f"{current_user.nickname} 添加了一个新心愿",
        body=wish.title[:160],
        link="/cottage/wishlist",
        source_type="wish",
        source_id=wish.wid,
        exclude_user_id=current_user.id,
    )
    db.commit()
    return _to_response(_load_wish(db, wish.wid))


@router.get("", response_model=WishListResponse)
def list_wishes(
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishListResponse:
    ensure_partner(current_user)

    base = db.query(Wish).filter(Wish.deleted_at.is_(None))
    total = base.count()
    pending_count = base.filter(Wish.status == WishStatus.pending.value).count()
    completed_count = total - pending_count

    query = (
        db.query(Wish)
        .options(joinedload(Wish.author), joinedload(Wish.completed_by))
        .filter(Wish.deleted_at.is_(None))
    )
    if status_filter in (WishStatus.pending.value, WishStatus.completed.value):
        query = query.filter(Wish.status == status_filter)

    # Pending first, then highest priority, then newest.
    pending_first = case((Wish.status == WishStatus.completed.value, 1), else_=0)
    items = (
        query.order_by(pending_first.asc(), Wish.priority.desc(), Wish.created_at.desc()).all()
    )

    return WishListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        pending=pending_count,
        completed=completed_count,
    )


@router.get("/{wid}", response_model=WishResponse)
def get_wish(
    wid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishResponse:
    ensure_partner(current_user)
    return _to_response(_load_wish(db, wid))


@router.patch("/{wid}", response_model=WishResponse)
def update_wish(
    wid: str,
    payload: WishUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishResponse:
    ensure_partner(current_user)
    wish = _load_wish(db, wid)

    data = payload.model_dump(exclude_unset=True)
    for field in ("title", "description", "category", "target_date", "priority"):
        if field in data:
            setattr(wish, field, data[field])
    wish.version += 1
    db.commit()
    return _to_response(_load_wish(db, wid))


@router.post("/{wid}/complete", response_model=WishResponse)
def complete_wish(
    wid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishResponse:
    ensure_partner(current_user)
    wish = _load_wish(db, wid)
    if wish.status != WishStatus.completed.value:
        wish.status = WishStatus.completed.value
        wish.completed_at = datetime.now(timezone.utc)
        wish.completed_by_id = current_user.id
        db.commit()
        notify_partners(
            db,
            type="wish.completed",
            title="你们的一个心愿达成啦",
            body=wish.title[:160],
            link="/cottage/wishlist",
            source_type="wish",
            source_id=wish.wid,
            exclude_user_id=current_user.id,
        )
        db.commit()
    return _to_response(_load_wish(db, wid))


@router.post("/{wid}/reopen", response_model=WishResponse)
def reopen_wish(
    wid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishResponse:
    ensure_partner(current_user)
    wish = _load_wish(db, wid)
    if wish.status != WishStatus.pending.value:
        wish.status = WishStatus.pending.value
        wish.completed_at = None
        wish.completed_by_id = None
        db.commit()
    return _to_response(_load_wish(db, wid))


@router.delete("/{wid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_wish(
    wid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_partner(current_user)
    wish = _load_wish(db, wid)
    wish.deleted_at = datetime.now(timezone.utc)
    db.commit()
