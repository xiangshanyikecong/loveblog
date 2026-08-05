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

"""Anniversary auto-moment generator.

On each yearly anniversary of a ``is_yearly_repeat`` event, proactively create
a commemorative Moment so the couple gets a memory entry without manual action.

Idempotency relies on ``Moment.client_idempotency_key`` (``anniversary:{eid}:{year}``)
which is guarded by a unique constraint, so a tick never duplicates a moment that
was already generated for the same event + year -- even across scheduler restarts.
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models.event import Event
from app.models.moment import Moment, Visibility
from app.models.user import User
from app.services.notifications import notify_partners

logger = logging.getLogger(__name__)


def _idempotency_key(eid: str, year: int) -> str:
    return f"anniversary:{eid}:{year}"


def _build_content(event: Event, years: int) -> str:
    formatted = event.date.strftime("%Y年%m月%d日")
    if years == 1:
        return (
            f"🎉 今天是「{event.title}」一周年纪念日！\n\n"
            f"从 {formatted} 起，属于我们的故事翻开了第一页。"
        )
    ordinal = "两" if years == 2 else str(years)
    return (
        f"🎉 今天是「{event.title}」{ordinal} 周年纪念日！\n\n"
        f"从 {formatted} 到今天，已经一起走过 {years} 年啦～"
    )


def _moment_already_exists(db: Session, author_id: int, key: str) -> bool:
    """True if a moment (alive or soft-deleted) already holds this idempotency key.

    We deliberately do *not* filter ``deleted_at`` so that a user-deleted
    auto-moment is not regenerated the next time the scheduler ticks.
    """
    existing = (
        db.query(Moment.id)
        .filter(
            Moment.author_id == author_id,
            Moment.client_idempotency_key == key,
        )
        .first()
    )
    return existing is not None


def run_anniversary_moment_tick(db: Session) -> int:
    """Create commemorative moments for every event whose anniversary is today.

    Returns the number of moments created this tick.
    """
    today = date.today()
    events = (
        db.query(Event)
        .options(joinedload(Event.creator))
        .filter(
            Event.deleted_at.is_(None),
            Event.is_yearly_repeat.is_(True),
        )
        .all()
    )

    created = 0
    for event in events:
        # Only match the month/day of the event (the "anniversary" itself).
        if event.date.month != today.month or event.date.day != today.day:
            continue

        years = today.year - event.date.year
        if years < 1:
            # The original year or a future-dated event -- countdown handles it.
            continue

        creator: User | None = event.creator
        if creator is None or creator.deleted_at is not None:
            continue

        key = _idempotency_key(event.eid, today.year)
        if _moment_already_exists(db, creator.id, key):
            continue

        try:
            # Mirror the event visibility onto the moment so private anniversaries
            # stay private. Both enums share the same string values.
            visibility = Visibility(event.visibility.value)
        except ValueError:
            visibility = Visibility.partners_only

        moment = Moment(
            author_id=creator.id,
            content=_build_content(event, years),
            media_urls=[],
            visibility=visibility,
            tags=["纪念日", f"anniversary:{event.eid}"],
            client_idempotency_key=key,
        )
        db.add(moment)
        try:
            db.flush()
        except Exception:
            db.rollback()
            logger.warning(
                "Anniversary moment for event %s (%s) already exists, skipped.",
                event.eid,
                event.title,
            )
            continue

        created += 1
        logger.info(
            "Auto-created anniversary moment for event %s (%s) - %d year(s).",
            event.eid,
            event.title,
            years,
        )

        notify_partners(
            db,
            type="event.anniversary",
            title=f"🎉 {event.title} {years} 周年快乐！",
            body="已自动为你们生成一条纪念动态，去看看吧～",
            link="/timeline",
            source_type="event_anniversary",
            source_id=f"{event.eid}:{today.year}",
            dedupe=True,
        )

    if created:
        db.commit()
    return created
