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

import logging
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.core.i18n import DEFAULT_LOCALE, get_message
from app.models.capsule import Capsule
from app.models.cottage_reminder import CottageReminder
from app.models.event import Event
from app.models.notification import Notification
from app.models.period_cycle import PeriodCycle
from app.models.user import User, UserRole
from app.services.notification_delivery import queue_notification_delivery
from app.services.period_prediction import CARE_LEAD_DAYS, compute_period_stats
from app.services.visibility_policy import VisibilityPolicy

logger = logging.getLogger(__name__)


def partner_recipients(db: Session, *, exclude_user_id: int | None = None) -> list[User]:
    query = db.query(User).filter(
        User.role.in_([UserRole.partner_a, UserRole.partner_b]),
        User.deleted_at.is_(None),
    )
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.all()


def create_notification(
    db: Session,
    *,
    recipient: User,
    type: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    dedupe: bool = False,
    queue_delivery: bool = True,
) -> Notification | None:
    if dedupe and source_type and source_id:
        existing = (
            db.query(Notification)
            .filter(
                Notification.recipient_id == recipient.id,
                Notification.type == type,
                Notification.source_type == source_type,
                Notification.source_id == source_id,
            )
            .first()
        )
        if existing is not None:
            return None

    item = Notification(
        recipient_id=recipient.id,
        type=type,
        title=title,
        body=body,
        link=link,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(item)
    if queue_delivery:
        queue_notification_delivery(db, item)
    return item


def notify_partners(
    db: Session,
    *,
    type: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    exclude_user_id: int | None = None,
    dedupe: bool = False,
    queue_delivery: bool = True,
) -> None:
    for recipient in partner_recipients(db, exclude_user_id=exclude_user_id):
        create_notification(
            db,
            recipient=recipient,
            type=type,
            title=title,
            body=body,
            link=link,
            source_type=source_type,
            source_id=source_id,
            dedupe=dedupe,
            queue_delivery=queue_delivery,
        )


def _safe_replace_year(value: date, year: int) -> date:
    """Replace the year, surviving a Feb 29 source date in a non-leap year.

    ``date(2024, 2, 29).replace(year=2026)`` raises ``ValueError``; for a yearly
    anniversary we degrade Feb 29 to Feb 28 in non-leap years instead of crashing.
    """
    try:
        return value.replace(year=year)
    except ValueError:
        return value.replace(year=year, day=28)


def _next_event_date(event: Event, today: date) -> date:
    target = event.date
    if not event.is_yearly_repeat:
        return target
    target = _safe_replace_year(target, today.year)
    if target < today:
        target = _safe_replace_year(target, today.year + 1)
    return target


def _reminder_matches_user(reminder: CottageReminder, current_user: User) -> bool:
    if reminder.audience == "both":
        return True
    if reminder.audience == "me":
        return reminder.author_id == current_user.id
    if reminder.audience == "partner":
        return reminder.author_id != current_user.id
    return True


def create_due_cottage_reminders(
    db: Session, current_user: User, *, queue_delivery: bool = True
) -> list[Notification]:
    if not VisibilityPolicy.is_partner(current_user):
        return []

    now = datetime.now(timezone.utc)
    reminders = (
        db.query(CottageReminder)
        .filter(
            CottageReminder.deleted_at.is_(None),
            CottageReminder.is_done.is_(False),
            CottageReminder.remind_at <= now,
        )
        .all()
    )
    created: list[Notification] = []
    for reminder in reminders:
        if not _reminder_matches_user(reminder, current_user):
            continue
        item = create_notification(
            db,
            recipient=current_user,
            type="cottage_reminder.due",
            title=reminder.title,
            body=reminder.note,
            link="/cottage/reminders",
            source_type="cottage_reminder",
            source_id=reminder.rid,
            dedupe=True,
            queue_delivery=queue_delivery,
        )
        if item is not None:
            created.append(item)
            db.flush()
    return created


def create_due_event_reminders(
    db: Session,
    current_user: User,
    days_ahead: int = 7,
    *,
    queue_delivery: bool = True,
) -> list[Notification]:
    if not VisibilityPolicy.is_partner(current_user):
        return []

    today = date.today()
    events = db.query(Event).filter(Event.deleted_at.is_(None)).all()
    created: list[Notification] = []
    for event in events:
        try:
            if not VisibilityPolicy.can_view_event(event, current_user):
                continue
            target = _next_event_date(event, today)
            days_left = (target - today).days
            if days_left < 0 or days_left > days_ahead:
                continue
            if days_left == 0:
                title = get_message(
                    "notification.event.reminder_today.title",
                    DEFAULT_LOCALE,
                    title=event.title,
                )
                body = get_message(
                    "notification.event.reminder_today.body",
                    DEFAULT_LOCALE,
                    date=target.isoformat(),
                )
            else:
                title = get_message(
                    "notification.event.reminder_days.title",
                    DEFAULT_LOCALE,
                    title=event.title,
                    days=days_left,
                )
                body = get_message(
                    "notification.event.reminder_days.body",
                    DEFAULT_LOCALE,
                    date=target.isoformat(),
                )
            item = create_notification(
                db,
                recipient=current_user,
                type="event.reminder",
                title=title,
                body=body,
                link="/events",
                source_type="event",
                source_id=f"{event.eid}:{target.isoformat()}",
                dedupe=True,
                queue_delivery=queue_delivery,
            )
            if item is not None:
                created.append(item)
        except Exception:
            # A single malformed event must never abort the whole batch — that
            # would block every reminder and 500 the notifications endpoint.
            logger.warning("Skipped a due-event reminder due to error", exc_info=True)
            continue
    return created


def create_due_capsule_reminders(
    db: Session, current_user: User, *, queue_delivery: bool = True
) -> list[Notification]:
    """Notify partners when a time capsule reaches its open time."""
    if not VisibilityPolicy.is_partner(current_user):
        return []

    now = datetime.now(timezone.utc)
    capsules = (
        db.query(Capsule)
        .options(joinedload(Capsule.author))
        .filter(
            Capsule.deleted_at.is_(None),
            Capsule.open_at <= now,
        )
        .all()
    )
    created: list[Notification] = []
    for capsule in capsules:
        author_name = capsule.author.nickname if capsule.author else "Ta"
        item = create_notification(
            db,
            recipient=current_user,
            type="capsule.open",
            title=get_message("notification.capsule.unlocked_title", DEFAULT_LOCALE),
            body=get_message(
                "notification.capsule.unlocked_body",
                DEFAULT_LOCALE,
                author=author_name,
            ),
            link="/capsules",
            source_type="capsule",
            source_id=capsule.uuid,
            dedupe=True,
            queue_delivery=queue_delivery,
        )
        if item is not None:
            created.append(item)
    return created


def create_due_period_reminders(
    db: Session, current_user: User, *, queue_delivery: bool = True
) -> list[Notification]:
    """Nudge ``current_user`` to care for their partner's upcoming period.

    The reminder is addressed to ``current_user`` and is about *their partner's*
    predicted cycle, so only the non-tracking partner receives it. Fires within
    ``CARE_LEAD_DAYS`` of the predicted start (including the day itself).
    """
    if not VisibilityPolicy.is_partner(current_user):
        return []

    today = date.today()
    created: list[Notification] = []
    for partner in partner_recipients(db, exclude_user_id=current_user.id):
        cycles = (
            db.query(PeriodCycle)
            .filter(
                PeriodCycle.author_id == partner.id,
                PeriodCycle.deleted_at.is_(None),
            )
            .all()
        )
        stats = compute_period_stats(cycles, today)
        next_start = stats["predicted_next_start"]
        days_until = stats["predicted_days_until"]
        if next_start is None or days_until is None:
            continue
        if not (0 <= days_until <= CARE_LEAD_DAYS):
            continue
        when_text = (
            get_message("notification.period.today", DEFAULT_LOCALE)
            if days_until == 0
            else get_message(
                "notification.period.days_later",
                DEFAULT_LOCALE,
                days=days_until,
            )
        )
        item = create_notification(
            db,
            recipient=current_user,
            type="period.care",
            title=get_message(
                "notification.period.care_title",
                DEFAULT_LOCALE,
                name=partner.nickname,
                when=when_text,
            ),
            body=get_message("notification.period.care_body", DEFAULT_LOCALE),
            link="/cottage/period",
            source_type="period",
            source_id=f"{partner.id}:{next_start.isoformat()}",
            dedupe=True,
            queue_delivery=queue_delivery,
        )
        if item is not None:
            created.append(item)
    return created


def ensure_due_notifications_for_user(
    db: Session,
    current_user: User,
    *,
    days_ahead: int = 7,
    queue_delivery: bool = False,
) -> list[Notification]:
    """Generate all due in-app reminders for one partner (idempotent via dedupe)."""
    created: list[Notification] = []
    created.extend(
        create_due_event_reminders(
            db,
            current_user,
            days_ahead=days_ahead,
            queue_delivery=queue_delivery,
        )
    )
    created.extend(create_due_cottage_reminders(db, current_user, queue_delivery=queue_delivery))
    created.extend(create_due_capsule_reminders(db, current_user, queue_delivery=queue_delivery))
    created.extend(create_due_period_reminders(db, current_user, queue_delivery=queue_delivery))
    return created


def run_scheduled_due_notifications(db: Session, *, days_ahead: int = 7) -> list[Notification]:
    """Background tick: generate due reminders for every active partner."""
    created: list[Notification] = []
    for partner in partner_recipients(db):
        created.extend(
            ensure_due_notifications_for_user(
                db,
                partner,
                days_ahead=days_ahead,
                queue_delivery=True,
            )
        )
    return created
