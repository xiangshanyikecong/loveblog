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

"""Background scheduler that proactively generates due in-app notifications."""
from __future__ import annotations

import asyncio
import logging

from app.db.session import SessionLocal
from app.services.anniversary_moments import run_anniversary_moment_tick
from app.services.notification_delivery import retry_pending_notification_deliveries
from app.services.notifications import run_scheduled_due_notifications

logger = logging.getLogger(__name__)


def run_notification_scheduler_tick(*, days_ahead: int = 7) -> int:
    """One scheduler pass: retry queued deliveries, then create due notifications."""
    retried = retry_pending_notification_deliveries()
    if retried:
        logger.info("Notification scheduler retried %d queued delivery item(s).", retried)

    db = SessionLocal()
    try:
        created = run_scheduled_due_notifications(db, days_ahead=days_ahead)
        db.commit()
        if created:
            logger.info("Notification scheduler created %d new notification(s).", len(created))
        return len(created)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_anniversary_tick() -> int:
    """Generate commemorative moments for events whose anniversary is today."""
    db = SessionLocal()
    try:
        return run_anniversary_moment_tick(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def notification_scheduler_loop(*, interval_seconds: int, days_ahead: int = 7) -> None:
    while True:
        try:
            await asyncio.to_thread(run_notification_scheduler_tick, days_ahead=days_ahead)
        except Exception:
            logger.exception("Notification scheduler tick failed.")
        try:
            count = await asyncio.to_thread(run_anniversary_tick)
            if count:
                logger.info("Anniversary moment generator created %d moment(s).", count)
        except Exception:
            logger.exception("Anniversary moment tick failed.")
        await asyncio.sleep(interval_seconds)
