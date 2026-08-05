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

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.services.notifications import ensure_due_notifications_for_user


router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_response(item: Notification) -> NotificationResponse:
    return NotificationResponse(
        nid=item.nid,
        type=item.type,
        title=item.title,
        body=item.body,
        link=item.link,
        source_type=item.source_type,
        source_id=item.source_id,
        is_read=item.is_read,
        created_at=item.created_at,
        read_at=item.read_at,
    )


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationListResponse:
    ensure_due_notifications_for_user(db, current_user)
    db.commit()

    query = db.query(Notification).filter(Notification.recipient_id == current_user.id)
    unread_count = (
        db.query(func.count(Notification.id))
        .filter(Notification.recipient_id == current_user.id, Notification.is_read.is_(False))
        .scalar()
        or 0
    )
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    items = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return NotificationListResponse(
        items=[_to_response(item) for item in items],
        total=len(items),
        unread_count=unread_count,
    )


@router.post("/{nid}/read", response_model=NotificationResponse)
def mark_notification_read(
    nid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationResponse:
    item = (
        db.query(Notification)
        .filter(Notification.nid == nid, Notification.recipient_id == current_user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    item.is_read = True
    item.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return _to_response(item)


@router.post("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    now = datetime.now(timezone.utc)
    updated = (
        db.query(Notification)
        .filter(Notification.recipient_id == current_user.id, Notification.is_read.is_(False))
        .update({"is_read": True, "read_at": now}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}
