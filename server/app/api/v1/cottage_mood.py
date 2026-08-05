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

"""Cottage daily mood check-in (小屋·心情打卡) routes.

Reuses the "报备" paradigm: one mood per partner per day, upserted. Both
partners' moods feed a shared emotion calendar. All endpoints are partner-only.

Endpoints under ``/v1/cottage/mood``:

- ``POST /v1/cottage/mood``          — upsert today's (or a given day's) mood
- ``GET  /v1/cottage/mood/today``    — both partners' mood for a given day
- ``GET  /v1/cottage/mood/calendar`` — both partners' moods for a month
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.mood import MoodCheckin
from app.models.mood_idempotency import MoodIdempotencyRecord
from app.models.user import User
from app.schemas.mood import (
    MoodCalendarResponse,
    MoodCheckinRequest,
    MoodResponse,
    MoodTodayResponse,
)
from app.services.cottage_realtime import schedule_broadcast
from app.services.notifications import notify_partners


router = APIRouter(prefix="/cottage/mood", tags=["cottage-mood"])


def _payload_hash(payload: MoodCheckinRequest, mood_date: date) -> str:
    canonical = json.dumps(
        {
            "mood_date": mood_date.isoformat(),
            "mood": payload.mood,
            "emoji": payload.emoji,
            "note": payload.note,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _response_for_idempotency_record(
    db: Session,
    record: MoodIdempotencyRecord,
    *,
    expected_payload_hash: str,
    current_user: User,
) -> MoodResponse:
    if record.payload_hash != expected_payload_hash:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key was reused with a different payload",
        )
    row = (
        db.query(MoodCheckin)
        .options(joinedload(MoodCheckin.author))
        .filter(MoodCheckin.id == record.mood_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=409, detail="Idempotency record no longer has a mood")
    return _to_response(row, current_user)


def _commit_mood_operation(
    db: Session,
    *,
    payload: MoodCheckinRequest,
    mood_date: date,
    current_user: User,
    idempotency_key: str | None,
    payload_hash: str,
) -> MoodCheckin:
    row = (
        db.query(MoodCheckin)
        .filter(MoodCheckin.author_id == current_user.id, MoodCheckin.mood_date == mood_date)
        .first()
    )
    if row is None:
        row = MoodCheckin(author_id=current_user.id, mood_date=mood_date)
        db.add(row)
    row.mood = payload.mood
    row.emoji = payload.emoji
    row.note = payload.note

    db.flush()
    if idempotency_key:
        db.add(
            MoodIdempotencyRecord(
                user_id=current_user.id,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                mood_id=row.id,
            )
        )
    notify_partners(
        db,
        type="mood.checkin",
        title=f"{current_user.nickname} 记录了今天的心情 {payload.emoji or ''}".strip(),
        body=(payload.note[:80] if payload.note else None),
        link="/cottage/mood",
        source_type="mood",
        source_id=row.mid,
        exclude_user_id=current_user.id,
    )
    db.commit()
    return (
        db.query(MoodCheckin)
        .options(joinedload(MoodCheckin.author))
        .filter(MoodCheckin.id == row.id)
        .first()
    )


def _to_response(row: MoodCheckin, current_user: User) -> MoodResponse:
    return MoodResponse(
        mid=row.mid,
        author_uid=row.author.uid if row.author else "",
        author_nickname=row.author.nickname if row.author else "",
        is_self=(row.author_id == current_user.id),
        mood_date=row.mood_date,
        mood=row.mood,
        emoji=row.emoji,
        note=row.note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("", response_model=MoodResponse)
def upsert_mood(
    payload: MoodCheckinRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MoodResponse:
    ensure_partner(current_user)
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(status_code=400, detail="Invalid Idempotency-Key")
    the_date = payload.mood_date or datetime.now(timezone.utc).date()
    request_payload_hash = _payload_hash(payload, the_date)

    if idempotency_key:
        existing_record = db.query(MoodIdempotencyRecord).filter(
            MoodIdempotencyRecord.user_id == current_user.id,
            MoodIdempotencyRecord.idempotency_key == idempotency_key,
        ).first()
        if existing_record is not None:
            return _response_for_idempotency_record(
                db,
                existing_record,
                expected_payload_hash=request_payload_hash,
                current_user=current_user,
            )

    try:
        row = _commit_mood_operation(
            db,
            payload=payload,
            mood_date=the_date,
            current_user=current_user,
            idempotency_key=idempotency_key,
            payload_hash=request_payload_hash,
        )
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing_record = db.query(MoodIdempotencyRecord).filter(
                MoodIdempotencyRecord.user_id == current_user.id,
                MoodIdempotencyRecord.idempotency_key == idempotency_key,
            ).first()
            if existing_record is not None:
                return _response_for_idempotency_record(
                    db,
                    existing_record,
                    expected_payload_hash=request_payload_hash,
                    current_user=current_user,
                )
        # A concurrent first check-in for the same calendar day can lose the
        # author/date unique race. Retry once as an update of the committed row.
        row = _commit_mood_operation(
            db,
            payload=payload,
            mood_date=the_date,
            current_user=current_user,
            idempotency_key=idempotency_key,
            payload_hash=request_payload_hash,
        )

    schedule_broadcast(
        {
            "type": "MOOD",
            "payload": {
                "author_uid": current_user.uid,
                "author_nickname": current_user.nickname,
                "mood_date": the_date.isoformat(),
                "mood": row.mood,
                "emoji": row.emoji,
            },
        },
        exclude_uid=current_user.uid,
    )
    return _to_response(row, current_user)


@router.get("/today", response_model=MoodTodayResponse)
def mood_today(
    on: Annotated[date | None, Query()] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MoodTodayResponse:
    ensure_partner(current_user)
    the_date = on or datetime.now(timezone.utc).date()
    rows = (
        db.query(MoodCheckin)
        .options(joinedload(MoodCheckin.author))
        .filter(MoodCheckin.mood_date == the_date)
        .all()
    )
    mine: MoodResponse | None = None
    partner: MoodResponse | None = None
    for row in rows:
        if row.author_id == current_user.id:
            mine = _to_response(row, current_user)
        else:
            partner = _to_response(row, current_user)
    return MoodTodayResponse(mine=mine, partner=partner)


@router.get("/calendar", response_model=MoodCalendarResponse)
def mood_calendar(
    year: Annotated[int, Query(ge=1970, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MoodCalendarResponse:
    ensure_partner(current_user)
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    rows = (
        db.query(MoodCheckin)
        .options(joinedload(MoodCheckin.author))
        .filter(MoodCheckin.mood_date >= start, MoodCheckin.mood_date < end)
        .order_by(MoodCheckin.mood_date.asc())
        .all()
    )
    return MoodCalendarResponse(
        year=year,
        month=month,
        items=[_to_response(row, current_user) for row in rows],
    )
