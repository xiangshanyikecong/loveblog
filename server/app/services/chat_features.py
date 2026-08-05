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

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.chat_message import ChatMessage
from app.models.user import User, UserRole
from app.services.cottage_realtime import manager, schedule_broadcast_batch
from app.services.notifications import create_notification


def resolve_counterpart(db: Session, current_user: User) -> User | None:
    return (
        db.query(User)
        .filter(
            User.role.in_([UserRole.partner_a, UserRole.partner_b]),
            User.id != current_user.id,
            User.deleted_at.is_(None),
        )
        .order_by(User.id.asc())
        .first()
    )


def _reply_payload(message: ChatMessage | None) -> dict[str, str | bool | None] | None:
    if message is None:
        return None
    is_recalled = bool(message.recalled_at)
    if is_recalled:
        content = "这条消息已撤回"
    elif message.type == "voice":
        content = "[语音]"
    elif message.type in {"image", "sticker"}:
        content = "[图片]" if message.type == "image" else "[贴纸]"
    else:
        content = message.content
    return {
        "mid": message.mid,
        "sender_nickname": message.sender.nickname if message.sender else "",
        "type": message.type,
        "content": content,
        "is_recalled": is_recalled,
    }


def event_payload(msg: ChatMessage) -> dict[str, str | int | bool | None]:
    return {
        "id": msg.id,
        "mid": msg.mid,
        "sender_uid": msg.sender.uid if msg.sender else "",
        "sender_nickname": msg.sender.nickname if msg.sender else "",
        "type": msg.type,
        "content": msg.content,
        "media_url": msg.media_url,
        "audio_duration_sec": msg.audio_duration_sec,
        "is_recalled": bool(msg.recalled_at),
        "reply_to": _reply_payload(msg.reply_to),
        "recalled_at": msg.recalled_at.isoformat() if msg.recalled_at else None,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
        "visible_at": msg.visible_at.isoformat() if msg.visible_at else None,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        # E2EE envelope: partner-client uses these to decrypt the chat
        # payload locally; the server never sees the plaintext.
        "is_encrypted": bool(getattr(msg, "is_encrypted", False)),
        "iv": getattr(msg, "iv", None),
        "ciphertext": getattr(msg, "ciphertext", None),
        "algo": getattr(msg, "algo", None),
    }


def message_preview(msg: ChatMessage) -> str:
    if msg.recalled_at:
        return "[已撤回]"
    if msg.content:
        return msg.content[:80]
    if msg.type == "voice":
        return "[语音]"
    if msg.type == "sticker":
        return "[贴纸]"
    if msg.type == "image":
        return "[图片]"
    return "[消息]"


def release_due_future_messages(db: Session) -> int:
    now = datetime.now(timezone.utc)
    due_messages = (
        db.query(ChatMessage)
        .options(
            joinedload(ChatMessage.sender),
            joinedload(ChatMessage.reply_to).joinedload(ChatMessage.sender),
        )
        .filter(
            ChatMessage.deleted_at.is_(None),
            ChatMessage.visible_at <= now,
            ChatMessage.released_at.is_(None),
        )
        .order_by(ChatMessage.visible_at.asc(), ChatMessage.id.asc())
        .all()
    )
    if not due_messages:
        return 0

    counterpart_cache: dict[int, User | None] = {}
    for msg in due_messages:
        msg.released_at = now

    db.flush()

    # Batch all broadcasts into a single call to avoid N lock acquisitions.
    events: list[dict[str, Any]] = []
    for msg in due_messages:
        events.append({"type": "CHAT_MESSAGE", "payload": event_payload(msg)})

        counterpart = counterpart_cache.get(msg.sender_id)
        if counterpart is None:
            sender = msg.sender
            if sender is not None:
                counterpart = resolve_counterpart(db, sender)
            counterpart_cache[msg.sender_id] = counterpart

        if counterpart is not None and not manager.is_online(counterpart.uid):
            sender_name = msg.sender.nickname if msg.sender else "Ta"
            create_notification(
                db,
                recipient=counterpart,
                type="chat.future_message",
                title=f"{sender_name} 给你留了一条未来悄悄话",
                body=message_preview(msg),
                link="/cottage/chat",
                source_type="chat",
                source_id=msg.mid,
                dedupe=True,
            )
    schedule_broadcast_batch(events)
    return len(due_messages)
