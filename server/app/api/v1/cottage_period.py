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

"""Cottage period tracker (生理期记录与关怀提醒) routes.

Lets a partner log menstrual cycles and exposes a derived prediction + cycle
statistics. The data is sensitive, so every endpoint is partner-only and edit /
delete is restricted to the record's author. The notification scheduler reads
the same prediction logic to push a gentle care reminder to the partner before
the next predicted start (see ``app.services.notifications``).

Endpoints under ``/v1/cottage/period``:

- ``POST   /v1/cottage/period``         — log a cycle (start / optional end)
- ``GET    /v1/cottage/period``         — list cycles (newest first)
- ``GET    /v1/cottage/period/summary`` — stats + next-start prediction
- ``PATCH  /v1/cottage/period/{pcid}``  — edit (author only)
- ``DELETE /v1/cottage/period/{pcid}``  — soft delete (author only)
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.period_cycle import PeriodCycle
from app.models.user import User
from app.schemas.period_cycle import (
    PeriodCreateRequest,
    PeriodListResponse,
    PeriodResponse,
    PeriodSummaryResponse,
    PeriodUpdateRequest,
)
from app.services.notifications import notify_partners
from app.services.period_prediction import compute_period_stats


router = APIRouter(prefix="/cottage/period", tags=["cottage-period"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _length_days(cycle: PeriodCycle) -> int | None:
    if cycle.end_date is None:
        return None
    return (cycle.end_date - cycle.start_date).days + 1


def _to_response(cycle: PeriodCycle) -> PeriodResponse:
    return PeriodResponse(
        pcid=cycle.pcid,
        start_date=cycle.start_date,
        end_date=cycle.end_date,
        note=cycle.note,
        length_days=_length_days(cycle),
        author_uid=cycle.author.uid if cycle.author else "",
        author_nickname=cycle.author.nickname if cycle.author else "",
        created_at=cycle.created_at,
    )


def _load_cycle(db: Session, pcid: str) -> PeriodCycle:
    cycle = (
        db.query(PeriodCycle)
        .options(joinedload(PeriodCycle.author))
        .filter(PeriodCycle.pcid == pcid, PeriodCycle.deleted_at.is_(None))
        .first()
    )
    if cycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period cycle not found")
    return cycle


def _ensure_author(cycle: PeriodCycle, current_user: User) -> None:
    if cycle.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="只能修改自己的生理期记录"
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=PeriodResponse, status_code=status.HTTP_201_CREATED)
def create_cycle(
    payload: PeriodCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PeriodResponse:
    ensure_partner(current_user)

    existing = (
        db.query(PeriodCycle)
        .filter(
            PeriodCycle.author_id == current_user.id,
            PeriodCycle.start_date == payload.start_date,
            PeriodCycle.deleted_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="这一天已经有记录了"
        )

    cycle = PeriodCycle(
        author_id=current_user.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        note=payload.note,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    # Gentle heads-up to the partner; body kept generic to respect privacy.
    notify_partners(
        db,
        type="period.logged",
        title=f"{current_user.nickname} 更新了生理期记录",
        body="记得多关心 Ta 哦～",
        link="/cottage/period",
        source_type="period",
        source_id=cycle.pcid,
        exclude_user_id=current_user.id,
    )
    db.commit()
    return _to_response(_load_cycle(db, cycle.pcid))


@router.get("", response_model=PeriodListResponse)
def list_cycles(
    limit: Annotated[int, Query(ge=1, le=200)] = 60,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PeriodListResponse:
    ensure_partner(current_user)
    base = db.query(PeriodCycle).filter(PeriodCycle.deleted_at.is_(None))
    total = base.count()
    items = (
        base.options(joinedload(PeriodCycle.author))
        .order_by(PeriodCycle.start_date.desc())
        .limit(limit)
        .all()
    )
    return PeriodListResponse(items=[_to_response(item) for item in items], total=total)


@router.get("/summary", response_model=PeriodSummaryResponse)
def period_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PeriodSummaryResponse:
    ensure_partner(current_user)
    cycles = (
        db.query(PeriodCycle)
        .filter(PeriodCycle.deleted_at.is_(None))
        .all()
    )
    today = date.today()
    stats = compute_period_stats(cycles, today)
    return PeriodSummaryResponse(**stats)


@router.patch("/{pcid}", response_model=PeriodResponse)
def update_cycle(
    pcid: str,
    payload: PeriodUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PeriodResponse:
    ensure_partner(current_user)
    cycle = _load_cycle(db, pcid)
    _ensure_author(cycle, current_user)

    data = payload.model_dump(exclude_unset=True)
    new_start = data.get("start_date", cycle.start_date)
    new_end = data.get("end_date", cycle.end_date)
    if new_end is not None and new_end < new_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="结束日期不能早于开始日期"
        )
    for field in ("start_date", "end_date", "note"):
        if field in data:
            setattr(cycle, field, data[field])
    cycle.version += 1
    db.commit()
    return _to_response(_load_cycle(db, pcid))


@router.delete("/{pcid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_cycle(
    pcid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_partner(current_user)
    cycle = _load_cycle(db, pcid)
    _ensure_author(cycle, current_user)
    cycle.deleted_at = datetime.now(timezone.utc)
    db.commit()
