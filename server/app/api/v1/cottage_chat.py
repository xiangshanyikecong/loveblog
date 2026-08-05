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

"""Cottage two-person chat + poke (小屋·悄悄话 / 戳一戳) routes."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.core.i18n import get_message
from app.db.session import get_db
from app.models.chat_key import ChatKey
from app.models.chat_message import ChatMessage, ChatMessageType
from app.models.chat_message_meta import ChatMessageFavorite, ChatPinnedQuote
from app.models.user import User
from app.schemas.cottage_chat import (
    ChatFavoriteListResponse,
    ChatFutureMessagesResponse,
    ChatHistoryResponse,
    ChatKeywordItem,
    ChatKeywordsResponse,
    ChatMediaPanelResponse,
    ChatMemoryCardResponse,
    ChatMessageResponse,
    ChatPinnedQuoteRequest,
    ChatPinnedQuoteResponse,
    ChatReplyPreview,
    ChatSearchResponse,
    ChatSendRequest,
    ChatStateResponse,
    PokeRequest,
)
from app.services.chat_features import (
    event_payload,
    message_preview,
    release_due_future_messages,
    resolve_counterpart,
)
from app.services.cottage_realtime import manager, schedule_broadcast, schedule_send_to
from app.services.notifications import create_notification
from app.services.upload_references import sync_chat_message_upload_references


router = APIRouter(prefix="/cottage", tags=["cottage-chat"])


POKE_LABELS = {
    "poke": "戳了戳你",
    "miss": "想你了",
    "hug": "抱抱你",
    "kiss": "亲亲你",
}
_KEYWORD_STOPWORDS = {
    "我们", "你们", "自己", "一下", "这个", "那个", "今天", "明天", "现在", "晚上", "早上", "中午",
    "然后", "因为", "所以", "就是", "真的", "可以", "已经", "还是", "一个", "没有", "什么", "怎么",
    "时候", "宝宝", "老公", "老婆", "哈哈", "嘿嘿", "呜呜", "晚安", "早安",
}
_RECALL_WINDOW = timedelta(minutes=2)


def _chat_e2e_initialized(db: Session) -> bool:
    """True if the couple has set up an E2E chat key (ChatKey row exists).

    Once initialised, the server must refuse plaintext text messages so that
    a compromised session or XSS cannot bypass the client-side encryption and
    inject readable content into the encrypted chat.
    """
    return db.query(ChatKey.id).limit(1).first() is not None


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _favorite_message_ids(db: Session, current_user: User, message_ids: list[int]) -> set[int]:
    if not message_ids:
        return set()
    rows = (
        db.query(ChatMessageFavorite.message_id)
        .filter(
            ChatMessageFavorite.user_id == current_user.id,
            ChatMessageFavorite.message_id.in_(message_ids),
        )
        .all()
    )
    return {row[0] for row in rows}


def _message_preview_for_user(msg: ChatMessage, current_user: User) -> tuple[str | None, str | None, int | None]:
    if msg.recalled_at is not None:
        label = "你撤回了一条消息" if msg.sender_id == current_user.id else "Ta 撤回了一条消息"
        return label, None, None
    return msg.content, msg.media_url, msg.audio_duration_sec


def _reply_preview(msg: ChatMessage | None) -> ChatReplyPreview | None:
    if msg is None:
        return None
    if msg.recalled_at is not None:
        content = "这条消息已撤回"
    elif msg.type == ChatMessageType.voice.value:
        content = "[语音]"
    elif msg.type == ChatMessageType.image.value:
        content = "[图片]"
    elif msg.type == ChatMessageType.sticker.value:
        content = "[贴纸]"
    else:
        content = msg.content
    return ChatReplyPreview(
        mid=msg.mid,
        sender_nickname=msg.sender.nickname if msg.sender else "",
        type=msg.type,
        content=content,
        is_recalled=msg.recalled_at is not None,
    )


def _can_recall(msg: ChatMessage, current_user: User) -> bool:
    if msg.sender_id != current_user.id or msg.recalled_at is not None or msg.released_at is None:
        return False
    created_at = _coerce_utc(msg.created_at)
    if created_at is None:
        return False
    return datetime.now(timezone.utc) - created_at <= _RECALL_WINDOW


def _to_response(
    msg: ChatMessage,
    current_user: User,
    *,
    favorite_ids: set[int] | None = None,
) -> ChatMessageResponse:
    favorite_ids = favorite_ids or set()
    visible_at = _coerce_utc(msg.visible_at)
    content, media_url, audio_duration_sec = _message_preview_for_user(msg, current_user)
    return ChatMessageResponse(
        id=msg.id,
        mid=msg.mid,
        sender_uid=msg.sender.uid if msg.sender else "",
        sender_nickname=msg.sender.nickname if msg.sender else "",
        is_self=(msg.sender_id == current_user.id),
        type=msg.type,
        content=content,
        media_url=media_url,
        audio_duration_sec=audio_duration_sec,
        is_favorite=msg.id in favorite_ids,
        is_future=msg.released_at is None and bool(
            visible_at and visible_at > datetime.now(timezone.utc)
        ),
        is_recalled=msg.recalled_at is not None,
        can_recall=_can_recall(msg, current_user),
        recalled_at=_coerce_utc(msg.recalled_at),
        reply_to=_reply_preview(msg.reply_to),
        read_at=msg.read_at,
        visible_at=visible_at,
        created_at=_coerce_utc(msg.created_at) or msg.created_at,
        is_encrypted=bool(getattr(msg, "is_encrypted", False)),
        iv=getattr(msg, "iv", None),
        ciphertext=getattr(msg, "ciphertext", None),
        algo=getattr(msg, "algo", None),
    )


def _visible_message_query(db: Session):
    return (
        db.query(ChatMessage)
        .options(
            joinedload(ChatMessage.sender),
            joinedload(ChatMessage.reply_to).joinedload(ChatMessage.sender),
        )
        .filter(
            ChatMessage.deleted_at.is_(None),
            ChatMessage.released_at.is_not(None),
        )
    )


def _find_visible_message(db: Session, *, mid: str) -> ChatMessage | None:
    return (
        _visible_message_query(db)
        .filter(ChatMessage.mid == mid)
        .first()
    )


def _keyword_tokens(text: str) -> list[str]:
    raw = str(text or "").strip().lower()
    if not raw:
        return []
    tokens: list[str] = []
    tokens.extend(re.findall(r"[a-z0-9]{2,20}", raw))
    for segment in re.findall(r"[\u4e00-\u9fff]{2,12}", raw):
        if len(segment) <= 4:
            tokens.append(segment)
            continue
        for size in (2, 3):
            for idx in range(0, len(segment) - size + 1):
                tokens.append(segment[idx:idx + size])
    cleaned: list[str] = []
    for token in tokens:
        if token in _KEYWORD_STOPWORDS:
            continue
        if len(set(token)) == 1:
            continue
        cleaned.append(token)
    return cleaned


def _build_keywords(messages: list[ChatMessage], *, limit: int = 5) -> list[ChatKeywordItem]:
    counter: Counter[str] = Counter()
    for message in messages:
        if message.type != "text" or not message.content:
            continue
        counter.update(_keyword_tokens(message.content))
    items: list[ChatKeywordItem] = []
    for keyword, count in counter.most_common(limit):
        items.append(ChatKeywordItem(keyword=keyword, count=int(count)))
    return items


def _day_bounds(on: date) -> tuple[datetime, datetime]:
    # User-facing chat days are local calendar days; timestamps stay in UTC.
    start = datetime.combine(on, time.min).astimezone(timezone.utc)
    end = datetime.combine(on + timedelta(days=1), time.min).astimezone(timezone.utc)
    return start, end


def _load_pinned_quote(db: Session, current_user: User) -> ChatMessage | None:
    pinned = (
        db.query(ChatPinnedQuote)
        .options(joinedload(ChatPinnedQuote.message).joinedload(ChatMessage.sender))
        .options(joinedload(ChatPinnedQuote.message).joinedload(ChatMessage.reply_to).joinedload(ChatMessage.sender))
        .filter(ChatPinnedQuote.user_id == current_user.id)
        .first()
    )
    if pinned is None or pinned.message is None or pinned.message.deleted_at is not None:
        return None
    if pinned.message.released_at is None:
        return None
    return pinned.message


@router.post("/chat/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
def send_message(
    payload: ChatSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ChatMessageResponse:
    ensure_partner(current_user)
    now = datetime.now(timezone.utc)

    # Idempotency-Key: when the same key is replayed with the same payload,
    # return the previously persisted message instead of creating a duplicate.
    # This is what makes the Android offline SyncEngine retry-safe: a network
    # blip after the server commit but before the 2xx ack returns the original
    # row on retry rather than a second copy.
    # FastAPI resolves Header() to ``None`` for HTTP requests. Keeping direct
    # service-level callers compatible avoids treating the descriptor itself as
    # a string when this function is exercised without dependency injection.
    if not isinstance(idempotency_key, str):
        idempotency_key = None
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Idempotency-Key")
        existing = (
            db.query(ChatMessage)
            .options(
                joinedload(ChatMessage.sender),
                joinedload(ChatMessage.reply_to).joinedload(ChatMessage.sender),
            )
            .filter(
                ChatMessage.sender_id == current_user.id,
                ChatMessage.client_idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing is not None:
            return _to_response(existing, current_user)

    if payload.type == "text" and not payload.is_encrypted and not payload.content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=get_message("error.message_content_empty"))
    if payload.type in ("image", "sticker", "voice") and not payload.media_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=get_message("error.media_url_missing"))
    if payload.type == "voice" and not payload.audio_duration_sec:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=get_message("error.audio_duration_missing"))

    # E2E enforcement: once the couple has initialised a chat key, the server
    # must refuse ALL plaintext messages (text and media). Without this, a
    # compromised session or XSS could bypass the client-side encryption guard
    # and inject readable content that the README explicitly promises is
    # "never sent as plaintext".
    if not payload.is_encrypted and _chat_e2e_initialized(db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=get_message("error.encrypted_chat_no_plaintext"),
        )

    reply_to_message: ChatMessage | None = None
    if payload.reply_to_mid:
        reply_to_message = _find_visible_message(db, mid=payload.reply_to_mid)
        if reply_to_message is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=get_message("error.reply_message_not_found"))

    visible_at = _coerce_utc(payload.visible_at) or now
    msg = ChatMessage(
        sender_id=current_user.id,
        type=payload.type,
        content=payload.content,
        media_url=payload.media_url,
        audio_duration_sec=payload.audio_duration_sec,
        reply_to_message_id=reply_to_message.id if reply_to_message else None,
        visible_at=visible_at,
        released_at=now if visible_at <= now else None,
        client_idempotency_key=idempotency_key,
        is_encrypted=payload.is_encrypted,
        iv=payload.iv,
        ciphertext=payload.ciphertext,
        algo=payload.algo,
    )
    db.add(msg)

    try:
        db.flush()
    except IntegrityError:
        # A concurrent retry landed first; return its row.
        db.rollback()
        if idempotency_key is None:
            raise
        existing = (
            db.query(ChatMessage)
            .options(
                joinedload(ChatMessage.sender),
                joinedload(ChatMessage.reply_to).joinedload(ChatMessage.sender),
            )
            .filter(
                ChatMessage.sender_id == current_user.id,
                ChatMessage.client_idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing is None:
            raise
        return _to_response(existing, current_user)

    if msg.media_url:
        sync_chat_message_upload_references(db, msg)

    db.commit()
    msg = (
        db.query(ChatMessage)
        .options(
            joinedload(ChatMessage.sender),
            joinedload(ChatMessage.reply_to).joinedload(ChatMessage.sender),
        )
        .filter(ChatMessage.id == msg.id)
        .first()
    )

    counterpart = resolve_counterpart(db, current_user)
    if msg.released_at is not None:
        schedule_broadcast({"type": "CHAT_MESSAGE", "payload": event_payload(msg)})
        if counterpart is not None and not manager.is_online(counterpart.uid):
            create_notification(
                db,
                recipient=counterpart,
                type="chat.message",
                title=f"{current_user.nickname} 给你发了悄悄话",
                body=message_preview(msg),
                link="/cottage/chat",
                source_type="chat",
                source_id=msg.mid,
            )
            db.commit()

    return _to_response(msg, current_user)


@router.get("/chat/messages", response_model=ChatHistoryResponse)
def list_messages(
    before_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatHistoryResponse:
    ensure_partner(current_user)

    released = release_due_future_messages(db)
    if released:
        db.commit()

    query = _visible_message_query(db)
    if before_id is not None:
        query = query.filter(ChatMessage.id < before_id)

    rows = query.order_by(ChatMessage.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    rows_asc = list(reversed(rows))
    favorite_ids = _favorite_message_ids(db, current_user, [row.id for row in rows_asc])
    first_unread = next(
        (row.mid for row in rows_asc if row.sender_id != current_user.id and row.read_at is None),
        None,
    )

    next_before_id = rows_asc[0].id if (rows_asc and has_more) else None
    return ChatHistoryResponse(
        items=[_to_response(m, current_user, favorite_ids=favorite_ids) for m in rows_asc],
        has_more=has_more,
        first_unread_mid=first_unread,
        next_before_id=next_before_id,
    )


@router.get("/chat/search", response_model=ChatSearchResponse)
def search_messages(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSearchResponse:
    """Search plaintext chat messages by keyword (case-insensitive).

    Encrypted messages cannot be searched server-side because the server
    has no access to the derived key. The frontend supplements results by
    searching decrypted content from already-loaded messages client-side.
    """
    ensure_partner(current_user)
    keyword = q.strip()
    if not keyword:
        return ChatSearchResponse(query=q, items=[])

    rows = (
        _visible_message_query(db)
        .filter(
            ChatMessage.is_encrypted.is_(False),
            ChatMessage.type == "text",
            ChatMessage.content.ilike(f"%{keyword}%"),
        )
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    favorite_ids = _favorite_message_ids(db, current_user, [row.id for row in rows])
    return ChatSearchResponse(
        query=q,
        items=[_to_response(m, current_user, favorite_ids=favorite_ids) for m in rows],
    )


@router.get("/chat/favorites", response_model=ChatFavoriteListResponse)
def list_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatFavoriteListResponse:
    ensure_partner(current_user)
    rows = (
        db.query(ChatMessageFavorite)
        .options(joinedload(ChatMessageFavorite.message).joinedload(ChatMessage.sender))
        .options(
            joinedload(ChatMessageFavorite.message)
            .joinedload(ChatMessage.reply_to)
            .joinedload(ChatMessage.sender)
        )
        .filter(ChatMessageFavorite.user_id == current_user.id)
        .order_by(ChatMessageFavorite.created_at.desc())
        .all()
    )
    messages = [
        row.message for row in rows
        if row.message is not None and row.message.deleted_at is None and row.message.released_at is not None
    ]
    favorite_ids = {msg.id for msg in messages}
    return ChatFavoriteListResponse(
        items=[_to_response(msg, current_user, favorite_ids=favorite_ids) for msg in messages]
    )


@router.get("/chat/future", response_model=ChatFutureMessagesResponse)
def list_future_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatFutureMessagesResponse:
    ensure_partner(current_user)
    now = datetime.now(timezone.utc)
    rows = (
        db.query(ChatMessage)
        .options(
            joinedload(ChatMessage.sender),
            joinedload(ChatMessage.reply_to).joinedload(ChatMessage.sender),
        )
        .filter(
            ChatMessage.sender_id == current_user.id,
            ChatMessage.deleted_at.is_(None),
            ChatMessage.released_at.is_(None),
            ChatMessage.visible_at > now,
        )
        .order_by(ChatMessage.visible_at.asc(), ChatMessage.id.asc())
        .all()
    )
    return ChatFutureMessagesResponse(items=[_to_response(row, current_user) for row in rows])


@router.post("/chat/messages/{mid}/recall", response_model=ChatMessageResponse)
def recall_message(
    mid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMessageResponse:
    ensure_partner(current_user)
    message = _find_visible_message(db, mid=mid)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=get_message("error.message_not_found"))
    if message.sender_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=get_message("error.can_only_recall_own_message"))
    if message.recalled_at is not None:
        return _to_response(message, current_user)
    if not _can_recall(message, current_user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=get_message("error.message_recall_window_expired"))

    message.recalled_at = datetime.now(timezone.utc)
    message.content = None
    message.media_url = None
    message.audio_duration_sec = None
    # Preserve the E2EE envelope on recall so the recipient client can still
    # decrypt and render the placeholder; we just drop the plaintext hint.
    # (is_encrypted / iv / ciphertext / algo stay untouched.)
    sync_chat_message_upload_references(db, message)
    db.commit()

    message = (
        db.query(ChatMessage)
        .options(
            joinedload(ChatMessage.sender),
            joinedload(ChatMessage.reply_to).joinedload(ChatMessage.sender),
        )
        .filter(ChatMessage.id == message.id)
        .first()
    )
    schedule_broadcast({"type": "CHAT_MESSAGE", "payload": event_payload(message)})
    return _to_response(message, current_user)


@router.post("/chat/messages/{mid}/favorite", response_model=ChatMessageResponse)
def favorite_message(
    mid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMessageResponse:
    ensure_partner(current_user)
    message = _find_visible_message(db, mid=mid)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=get_message("error.message_not_found"))

    existing = (
        db.query(ChatMessageFavorite)
        .filter(ChatMessageFavorite.user_id == current_user.id, ChatMessageFavorite.message_id == message.id)
        .first()
    )
    if existing is None:
        db.add(ChatMessageFavorite(user_id=current_user.id, message_id=message.id))
        db.commit()
    return _to_response(message, current_user, favorite_ids={message.id})


@router.delete("/chat/messages/{mid}/favorite", response_model=ChatMessageResponse)
def unfavorite_message(
    mid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMessageResponse:
    ensure_partner(current_user)
    message = _find_visible_message(db, mid=mid)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=get_message("error.message_not_found"))

    (
        db.query(ChatMessageFavorite)
        .filter(ChatMessageFavorite.user_id == current_user.id, ChatMessageFavorite.message_id == message.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return _to_response(message, current_user)


@router.get("/chat/media-panel", response_model=ChatMediaPanelResponse)
def get_media_panel(
    limit: Annotated[int, Query(ge=1, le=60)] = 18,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMediaPanelResponse:
    ensure_partner(current_user)

    images = (
        _visible_message_query(db)
        .filter(ChatMessage.type == ChatMessageType.image.value)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    stickers = (
        _visible_message_query(db)
        .filter(ChatMessage.type == ChatMessageType.sticker.value)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    voices = (
        _visible_message_query(db)
        .filter(ChatMessage.type == ChatMessageType.voice.value)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    favorite_rows = (
        db.query(ChatMessageFavorite)
        .options(joinedload(ChatMessageFavorite.message).joinedload(ChatMessage.sender))
        .options(
            joinedload(ChatMessageFavorite.message)
            .joinedload(ChatMessage.reply_to)
            .joinedload(ChatMessage.sender)
        )
        .filter(ChatMessageFavorite.user_id == current_user.id)
        .order_by(ChatMessageFavorite.created_at.desc())
        .limit(limit)
        .all()
    )
    favorites = [
        row.message for row in favorite_rows
        if row.message is not None and row.message.deleted_at is None and row.message.released_at is not None
    ]
    favorite_ids = _favorite_message_ids(
        db,
        current_user,
        [msg.id for msg in [*images, *stickers, *voices, *favorites]],
    )
    return ChatMediaPanelResponse(
        images=[_to_response(msg, current_user, favorite_ids=favorite_ids) for msg in images],
        stickers=[_to_response(msg, current_user, favorite_ids=favorite_ids) for msg in stickers],
        voices=[_to_response(msg, current_user, favorite_ids=favorite_ids) for msg in voices],
        favorites=[_to_response(msg, current_user, favorite_ids=favorite_ids) for msg in favorites],
    )


@router.get("/chat/pinned-quote", response_model=ChatPinnedQuoteResponse)
def get_pinned_quote(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatPinnedQuoteResponse:
    ensure_partner(current_user)
    message = _load_pinned_quote(db, current_user)
    favorite_ids = {message.id} if message else set()
    return ChatPinnedQuoteResponse(
        message=_to_response(message, current_user, favorite_ids=favorite_ids) if message else None
    )


@router.put("/chat/pinned-quote", response_model=ChatPinnedQuoteResponse)
def set_pinned_quote(
    payload: ChatPinnedQuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatPinnedQuoteResponse:
    ensure_partner(current_user)
    message = _find_visible_message(db, mid=payload.mid)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=get_message("error.message_not_found"))
    if not message.content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=get_message("error.only_text_can_pin"))

    pinned = db.query(ChatPinnedQuote).filter(ChatPinnedQuote.user_id == current_user.id).first()
    if pinned is None:
        pinned = ChatPinnedQuote(user_id=current_user.id, message_id=message.id)
        db.add(pinned)
    else:
        pinned.message_id = message.id
        pinned.created_at = datetime.now(timezone.utc)
    db.commit()
    return ChatPinnedQuoteResponse(message=_to_response(message, current_user))


@router.delete("/chat/pinned-quote", response_model=ChatPinnedQuoteResponse)
def clear_pinned_quote(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatPinnedQuoteResponse:
    ensure_partner(current_user)
    (
        db.query(ChatPinnedQuote)
        .filter(ChatPinnedQuote.user_id == current_user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return ChatPinnedQuoteResponse(message=None)


@router.get("/chat/keywords", response_model=ChatKeywordsResponse)
def get_keywords(
    on: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatKeywordsResponse:
    ensure_partner(current_user)
    target_day = on or date.today()
    start, end = _day_bounds(target_day)
    rows = (
        _visible_message_query(db)
        .filter(ChatMessage.visible_at >= start, ChatMessage.visible_at < end)
        .order_by(ChatMessage.visible_at.asc(), ChatMessage.id.asc())
        .all()
    )
    return ChatKeywordsResponse(on=target_day, items=_build_keywords(rows))


@router.get("/chat/memory-card", response_model=ChatMemoryCardResponse)
def get_memory_card(
    on: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMemoryCardResponse:
    ensure_partner(current_user)
    target_day = on or date.today()
    start, end = _day_bounds(target_day)
    rows = (
        _visible_message_query(db)
        .filter(ChatMessage.visible_at >= start, ChatMessage.visible_at < end)
        .order_by(ChatMessage.visible_at.asc(), ChatMessage.id.asc())
        .all()
    )
    favorite_ids = _favorite_message_ids(db, current_user, [row.id for row in rows])
    pinned = _load_pinned_quote(db, current_user)
    pinned_visible_at = _coerce_utc(pinned.visible_at) if pinned is not None else None
    if pinned is not None and not (pinned_visible_at and start <= pinned_visible_at < end):
        pinned = None

    return ChatMemoryCardResponse(
        on=target_day,
        total_messages=len(rows),
        self_messages=sum(1 for row in rows if row.sender_id == current_user.id),
        partner_messages=sum(1 for row in rows if row.sender_id != current_user.id),
        favorite_count=sum(1 for row in rows if row.id in favorite_ids),
        first_message=_to_response(rows[0], current_user, favorite_ids=favorite_ids) if rows else None,
        last_message=_to_response(rows[-1], current_user, favorite_ids=favorite_ids) if rows else None,
        pinned_quote=_to_response(pinned, current_user, favorite_ids={pinned.id}) if pinned else None,
        keywords=_build_keywords(rows),
    )


@router.post("/chat/read")
def mark_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    ensure_partner(current_user)
    released = release_due_future_messages(db)
    now = datetime.now(timezone.utc)
    updated = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.sender_id != current_user.id,
            ChatMessage.read_at.is_(None),
            ChatMessage.deleted_at.is_(None),
            ChatMessage.released_at.is_not(None),
        )
        .update({ChatMessage.read_at: now}, synchronize_session=False)
    )
    db.commit()

    if updated:
        counterpart = resolve_counterpart(db, current_user)
        if counterpart is not None:
            schedule_send_to(
                counterpart.uid,
                {
                    "type": "CHAT_READ",
                    "payload": {"reader_uid": current_user.uid, "read_at": now.isoformat()},
                },
            )
    return {"updated": int(updated + released * 0)}


@router.get("/chat/state", response_model=ChatStateResponse)
def chat_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatStateResponse:
    ensure_partner(current_user)
    released = release_due_future_messages(db)
    if released:
        db.commit()
    counterpart = resolve_counterpart(db, current_user)
    unread = (
        db.query(func.count(ChatMessage.id))
        .filter(
            ChatMessage.sender_id != current_user.id,
            ChatMessage.read_at.is_(None),
            ChatMessage.deleted_at.is_(None),
            ChatMessage.released_at.is_not(None),
        )
        .scalar()
        or 0
    )
    return ChatStateResponse(
        partner_uid=counterpart.uid if counterpart else None,
        partner_nickname=counterpart.nickname if counterpart else None,
        partner_online=manager.is_online(counterpart.uid) if counterpart else False,
        partner_online_since=_coerce_utc(manager.online_since(counterpart.uid)) if counterpart else None,
        partner_last_active_at=_coerce_utc(manager.last_active_at(counterpart.uid)) if counterpart else None,
        self_online=manager.is_online(current_user.uid),
        unread=int(unread),
    )


@router.post("/poke")
def poke(
    payload: PokeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    ensure_partner(current_user)
    counterpart = resolve_counterpart(db, current_user)
    if counterpart is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=get_message("error.no_partner_account"))

    label = POKE_LABELS.get(payload.kind, "戳了戳你")
    online = manager.is_online(counterpart.uid)
    schedule_send_to(
        counterpart.uid,
        {
            "type": "POKE",
            "payload": {
                "from_uid": current_user.uid,
                "from_nickname": current_user.nickname,
                "kind": payload.kind,
                "label": label,
                "at": datetime.now(timezone.utc).isoformat(),
            },
        },
    )
    if not online:
        create_notification(
            db,
            recipient=counterpart,
            type="cottage.poke",
            title=f"{current_user.nickname} {label}",
            body=None,
            link="/cottage",
            source_type="poke",
            source_id=None,
        )
        db.commit()
    return {"ok": True, "delivered_online": online}
