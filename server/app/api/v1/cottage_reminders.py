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

"""Shared reminders for the cottage."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.cottage_reminder import CottageReminder
from app.models.user import User
from app.schemas.cottage_reminder import (
    CottageReminderCreateRequest,
    CottageReminderListResponse,
    CottageReminderResponse,
    CottageReminderUpdateRequest,
)
from app.services.notifications import notify_partners


router = APIRouter(prefix="/cottage/reminders", tags=["cottage-reminders"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_response(item: CottageReminder, now: datetime | None = None) -> CottageReminderResponse:
    current_time = now or _now()
    remind_at = _as_utc(item.remind_at)
    return CottageReminderResponse(
        rid=item.rid,
        title=item.title,
        note=item.note,
        remind_at=remind_at,
        audience=item.audience,
        is_due=(not item.is_done and remind_at <= current_time),
        is_done=item.is_done,
        author_uid=item.author.uid if item.author else "",
        author_nickname=item.author.nickname if item.author else "",
        done_at=item.done_at,
        done_by_uid=item.done_by.uid if item.done_by else None,
        done_by_nickname=item.done_by.nickname if item.done_by else None,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _load_reminder(db: Session, rid: str) -> CottageReminder:
    reminder = (
        db.query(CottageReminder)
        .options(joinedload(CottageReminder.author), joinedload(CottageReminder.done_by))
        .filter(CottageReminder.rid == rid, CottageReminder.deleted_at.is_(None))
        .first()
    )
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return reminder


@router.post("", response_model=CottageReminderResponse, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: CottageReminderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottageReminderResponse:
    ensure_partner(current_user)
    reminder = CottageReminder(
        author_id=current_user.id,
        title=payload.title,
        note=payload.note,
        remind_at=payload.remind_at,
        audience=payload.audience,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    if payload.audience in {"both", "partner"}:
        notify_partners(
            db,
            type="cottage_reminder.created",
            title=f"{current_user.nickname} set a cottage reminder",
            body=reminder.title[:160],
            link="/cottage/reminders",
            source_type="cottage_reminder",
            source_id=reminder.rid,
            exclude_user_id=current_user.id,
        )
        db.commit()
    return _to_response(_load_reminder(db, reminder.rid))


@router.get("", response_model=CottageReminderListResponse)
def list_reminders(
    include_done: bool = Query(default=False),
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottageReminderListResponse:
    ensure_partner(current_user)
    now = _now()
    base = db.query(CottageReminder).filter(CottageReminder.deleted_at.is_(None))
    total = base.count()
    done = base.filter(CottageReminder.is_done.is_(True)).count()
    active = total - done
    due = base.filter(CottageReminder.is_done.is_(False), CottageReminder.remind_at <= now).count()

    query = (
        db.query(CottageReminder)
        .options(joinedload(CottageReminder.author), joinedload(CottageReminder.done_by))
        .filter(CottageReminder.deleted_at.is_(None))
    )
    if not include_done:
        query = query.filter(CottageReminder.is_done.is_(False))

    done_last = case((CottageReminder.is_done.is_(True), 1), else_=0)
    items = (
        query.order_by(done_last.asc(), CottageReminder.remind_at.asc(), CottageReminder.created_at.desc())
        .limit(limit)
        .all()
    )
    return CottageReminderListResponse(
        items=[_to_response(item, now) for item in items],
        total=total,
        active=active,
        done=done,
        due=due,
    )


@router.get("/{rid}", response_model=CottageReminderResponse)
def get_reminder(
    rid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottageReminderResponse:
    ensure_partner(current_user)
    return _to_response(_load_reminder(db, rid))


@router.patch("/{rid}", response_model=CottageReminderResponse)
def update_reminder(
    rid: str,
    payload: CottageReminderUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottageReminderResponse:
    ensure_partner(current_user)
    reminder = _load_reminder(db, rid)
    data = payload.model_dump(exclude_unset=True)
    for field in ("title", "note", "remind_at", "audience"):
        if field in data:
            setattr(reminder, field, data[field])
    if "remind_at" in data:
        reminder.last_notified_at = None
    reminder.version += 1
    db.commit()
    return _to_response(_load_reminder(db, rid))


@router.post("/{rid}/done", response_model=CottageReminderResponse)
def mark_reminder_done(
    rid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottageReminderResponse:
    ensure_partner(current_user)
    reminder = _load_reminder(db, rid)
    if not reminder.is_done:
        reminder.is_done = True
        reminder.done_at = _now()
        reminder.done_by_id = current_user.id
        reminder.version += 1
        db.commit()
    return _to_response(_load_reminder(db, rid))


@router.post("/{rid}/reopen", response_model=CottageReminderResponse)
def reopen_reminder(
    rid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottageReminderResponse:
    ensure_partner(current_user)
    reminder = _load_reminder(db, rid)
    if reminder.is_done:
        reminder.is_done = False
        reminder.done_at = None
        reminder.done_by_id = None
        reminder.last_notified_at = None
        reminder.version += 1
        db.commit()
    return _to_response(_load_reminder(db, rid))


@router.delete("/{rid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_reminder(
    rid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_partner(current_user)
    reminder = _load_reminder(db, rid)
    reminder.deleted_at = _now()
    db.commit()
