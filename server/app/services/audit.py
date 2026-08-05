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

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.text_normalization import normalize_maybe_mojibake_text, normalize_nested_text_values
from app.models.audit_log import AuditLog
from app.models.user import User


logger = logging.getLogger(__name__)


def _dump_detail(detail: dict[str, Any] | None) -> str | None:
    if not detail:
        return None
    normalized_detail = normalize_nested_text_values(detail)
    return json.dumps(normalized_detail, ensure_ascii=False, default=str)


def write_audit_log(
    db: Session,
    *,
    action: str,
    actor: User | None = None,
    actor_username: str | None = None,
    result: str = "success",
    resource_type: str | None = None,
    resource_id: str | None = None,
    resource_name: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog | None:
    log = AuditLog(
        action=action,
        result=result,
        actor_id=actor.id if actor is not None else None,
        actor_uid=actor.uid if actor is not None else None,
        actor_username=normalize_maybe_mojibake_text(
            actor.username if actor is not None else actor_username
        ),
        actor_nickname=normalize_maybe_mojibake_text(actor.nickname if actor is not None else None),
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=normalize_maybe_mojibake_text(resource_name),
        detail_json=_dump_detail(detail),
    )
    db.add(log)
    try:
        db.commit()
        db.refresh(log)
        return log
    except Exception:
        db.rollback()
        logger.warning("Failed to write audit log action=%s", action, exc_info=True)
        return None
