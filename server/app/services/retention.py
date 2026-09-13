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

"""Data retention cleanup for append-heavy tables.

``audit_logs`` and ``notifications`` grow unboundedly (one row per audited
request / notification event). A daily background task prunes rows older
than the configured retention windows, in bounded batches so no single
delete transaction grows large.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.notification import Notification

logger = logging.getLogger(__name__)

AUDIT_LOG_RETENTION_DAYS = 180
NOTIFICATION_RETENTION_DAYS = 90
_BATCH_SIZE = 5000


def _delete_expired_in_batches(db, model, cutoff: datetime) -> int:
    """Delete rows older than *cutoff*, committing every batch."""
    total = 0
    while True:
        batch = db.scalars(
            select(model.id).where(model.created_at < cutoff).limit(_BATCH_SIZE)
        ).all()
        if not batch:
            break
        db.execute(delete(model).where(model.id.in_(batch)))
        db.commit()
        total += len(batch)
        if len(batch) < _BATCH_SIZE:
            break
    return total


def run_retention_cleanup() -> dict[str, int]:
    """Delete expired rows; returns the number of rows removed per table."""
    now = datetime.now(timezone.utc)
    removed: dict[str, int] = {}

    db = SessionLocal()
    try:
        removed["audit_logs"] = _delete_expired_in_batches(
            db, AuditLog, now - timedelta(days=AUDIT_LOG_RETENTION_DAYS)
        )
        removed["notifications"] = _delete_expired_in_batches(
            db, Notification, now - timedelta(days=NOTIFICATION_RETENTION_DAYS)
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return removed
