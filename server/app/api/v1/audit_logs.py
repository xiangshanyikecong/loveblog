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

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.core.text_normalization import normalize_maybe_mojibake_text, normalize_nested_text_values
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogListResponse, AuditLogResponse


router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


def _to_response(item: AuditLog) -> AuditLogResponse:
    return AuditLogResponse(
        log_id=item.log_id,
        action=item.action,
        result=item.result,
        actor_uid=item.actor_uid,
        actor_username=item.actor_username,
        actor_nickname=normalize_maybe_mojibake_text(item.actor_nickname),
        resource_type=item.resource_type,
        resource_id=item.resource_id,
        resource_name=normalize_maybe_mojibake_text(item.resource_name),
        detail=normalize_nested_text_values(item.detail),
        created_at=item.created_at,
    )


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    action: Annotated[str | None, Query(max_length=80)] = None,
    result: Annotated[str | None, Query(max_length=20)] = None,
    resource_type: Annotated[str | None, Query(max_length=50)] = None,
    actor_uid: Annotated[str | None, Query(max_length=36)] = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditLogListResponse:
    ensure_partner(current_user)

    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if result:
        query = query.filter(AuditLog.result == result)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if actor_uid:
        query = query.filter(AuditLog.actor_uid == actor_uid)
    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to:
        query = query.filter(AuditLog.created_at <= date_to)
    if q:
        keyword = f"%{q.strip()}%"
        query = query.filter(
            or_(
                AuditLog.action.ilike(keyword),
                AuditLog.actor_username.ilike(keyword),
                AuditLog.actor_nickname.ilike(keyword),
                AuditLog.resource_name.ilike(keyword),
                AuditLog.resource_id.ilike(keyword),
            )
        )

    total = query.count()
    offset = (page - 1) * page_size
    items = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return AuditLogListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + page_size) < total,
    )
