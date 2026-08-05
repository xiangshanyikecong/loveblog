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

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_optional_user
from app.db.session import get_db
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreateRequest, MessageListResponse, MessagePatchRequest, MessageResponse
from app.schemas.version import ContentVersionListResponse
from app.services.notifications import notify_partners
from app.services.versioning import (
    apply_message_snapshot,
    list_content_versions,
    record_message_version,
    version_to_response,
)
from app.services.visibility_policy import VisibilityPolicy


router = APIRouter(prefix="/messages", tags=["messages"])


def _ensure_idempotent_message_matches(message: Message, payload: MessageCreateRequest) -> None:
    if (
        message.content != payload.content
        or message.is_public != payload.is_public
        or (message.tags or []) != (payload.tags or [])
    ):
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key was reused with a different payload",
        )


def _to_response(item: Message) -> MessageResponse:
    return MessageResponse(
        msg_id=item.msg_id,
        content=item.content,
        is_public=item.is_public,
        tags=item.tags or [],
        is_deleted=item.is_deleted,
        version=item.version,
        created_at=item.created_at,
        author_uid=item.author.uid if item.author else None,
        author_nickname=item.author.nickname if item.author else None,
        visitor_name=item.visitor_name,
    )


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def create_message(
    payload: MessageCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(status_code=400, detail="Invalid Idempotency-Key")
        existing = (
            db.query(Message)
            .options(joinedload(Message.author))
            .filter(
                Message.author_id == current_user.id,
                Message.client_idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing is not None:
            _ensure_idempotent_message_matches(existing, payload)
            return _to_response(existing)

    message = Message(
        author_id=current_user.id,
        visitor_name=None,
        content=payload.content,
        is_public=payload.is_public,
        tags=payload.tags,
        client_idempotency_key=idempotency_key,
    )
    db.add(message)
    try:
        db.flush()
        db.refresh(message)

        message = (
            db.query(Message)
            .options(joinedload(Message.author))
            .filter(Message.id == message.id, Message.is_deleted.is_(False))
            .first()
        )
        record_message_version(db, message, current_user, "created")
        notify_partners(
            db,
            type="message.created",
            title="收到一条新留言",
            body=message.content[:160],
            link="/messages",
            source_type="message",
            source_id=message.msg_id,
            exclude_user_id=current_user.id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        if not idempotency_key:
            raise
        existing = (
            db.query(Message)
            .options(joinedload(Message.author))
            .filter(
                Message.author_id == current_user.id,
                Message.client_idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing is None:
            raise
        _ensure_idempotent_message_matches(existing, payload)
        return _to_response(existing)
    return _to_response(message)


@router.get("", response_model=MessageListResponse)
def list_messages(
    include_private: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> MessageListResponse:
    query = (
        db.query(Message)
        .options(joinedload(Message.author))
        .filter(Message.is_deleted.is_(False))
        .order_by(Message.created_at.desc())
    )

    if include_private and current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")

    query = query.filter(VisibilityPolicy.message_query_filter(current_user, include_private=include_private))
    items = query.all()

    return MessageListResponse(items=[_to_response(item) for item in items], total=len(items))


@router.patch("/{msg_id}", response_model=MessageResponse)
def patch_message(
    msg_id: str,
    payload: MessagePatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    message = (
        db.query(Message)
        .options(joinedload(Message.author))
        .filter(Message.msg_id == msg_id, Message.is_deleted.is_(False))
        .first()
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if not VisibilityPolicy.can_manage_message(message, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to edit message")

    record_message_version(db, message, current_user, "before patch")
    update_data = payload.model_dump(exclude_unset=True)
    if "content" in update_data:
        message.content = update_data["content"]
    if "is_public" in update_data:
        message.is_public = update_data["is_public"]
    if "tags" in update_data:
        message.tags = update_data["tags"]
    message.version += 1
    db.commit()
    db.refresh(message)
    record_message_version(db, message, current_user, "patched")
    db.commit()
    return _to_response(message)


@router.get("/{msg_id}/versions", response_model=ContentVersionListResponse)
def list_message_versions(
    msg_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContentVersionListResponse:
    message = (
        db.query(Message)
        .options(joinedload(Message.author))
        .filter(Message.msg_id == msg_id, Message.is_deleted.is_(False))
        .first()
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if not VisibilityPolicy.can_manage_message(message, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to view message history")

    record_message_version(db, message, current_user, "current snapshot")
    db.commit()
    versions = list_content_versions(db, content_type="message", content_id=msg_id)
    return ContentVersionListResponse(
        items=[version_to_response(item) for item in versions],
        total=len(versions),
    )


@router.post("/{msg_id}/versions/{version}/rollback", response_model=MessageResponse)
def rollback_message_version(
    msg_id: str,
    version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    message = (
        db.query(Message)
        .options(joinedload(Message.author))
        .filter(Message.msg_id == msg_id, Message.is_deleted.is_(False))
        .first()
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if not VisibilityPolicy.can_manage_message(message, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to rollback message")

    record_message_version(db, message, current_user, "before rollback")
    target = next(
        (
            item
            for item in list_content_versions(db, content_type="message", content_id=msg_id)
            if item.version == version
        ),
        None,
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    apply_message_snapshot(message, target.snapshot)
    db.commit()
    db.refresh(message)
    record_message_version(db, message, current_user, f"rollback to v{version}")
    db.commit()
    return _to_response(message)


@router.delete("/{msg_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_message(
    msg_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    message = (
        db.query(Message)
        .options(joinedload(Message.author))
        .filter(Message.msg_id == msg_id, Message.is_deleted.is_(False))
        .first()
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    if not VisibilityPolicy.can_manage_message(message, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to delete message")

    record_message_version(db, message, current_user, "before delete")
    message.is_deleted = True
    db.commit()
