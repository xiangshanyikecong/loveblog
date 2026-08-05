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

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_CONTENT_MAX = 4000


class ChatSendRequest(BaseModel):
    """Request body for ``POST /v1/cottage/chat/messages``."""

    type: str = Field(default="text", max_length=16)
    content: str | None = Field(default=None, max_length=_CONTENT_MAX)
    media_url: str | None = Field(default=None, max_length=2000)
    audio_duration_sec: int | None = Field(default=None, ge=1, le=3600)
    visible_at: datetime | None = None
    reply_to_mid: str | None = Field(default=None, max_length=64)
    is_encrypted: bool = False
    iv: str | None = Field(default=None, min_length=8, max_length=64)
    ciphertext: str | None = Field(default=None, min_length=1, max_length=2_000_000)
    algo: str | None = Field(default=None, max_length=16)

    @field_validator("type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        allowed = {"text", "image", "sticker", "voice"}
        normalized = (value or "text").strip().lower()
        if normalized not in allowed:
            raise ValueError("不支持的消息类型")
        return normalized

    @field_validator("content")
    @classmethod
    def _normalize_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("reply_to_mid")
    @classmethod
    def _normalize_reply_mid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def _validate_encryption_envelope(self):
        envelope_present = any((self.iv, self.ciphertext, self.algo))
        if not self.is_encrypted:
            if envelope_present:
                raise ValueError("明文消息不能携带加密信封")
            return self
        if self.algo != "AES-GCM":
            raise ValueError("端到端加密算法不受支持")
        if not self.iv:
            raise ValueError("端到端加密信封缺少 iv")
        if self.content is not None:
            raise ValueError("端到端加密消息不能同时携带明文 content")
        if self.type == "text":
            # 加密文字消息：密文内联在 ciphertext 字段，不能有 media_url。
            if not self.ciphertext:
                raise ValueError("端到端加密文字消息缺少 ciphertext")
            if self.media_url is not None:
                raise ValueError("端到端加密文字消息不能携带 media_url")
        elif self.type in ("image", "sticker", "voice"):
            # 加密媒体消息：文件密文已上传到 media_url，ciphertext 不用。
            # media_url 指向服务器上的加密文件（服务端无法解密）。
            if not self.media_url:
                raise ValueError("端到端加密媒体消息缺少 media_url")
            if self.ciphertext is not None:
                raise ValueError("端到端加密媒体消息不应携带内联 ciphertext")
        else:
            raise ValueError("不支持该消息类型的端到端加密")
        return self


class ChatReplyPreview(BaseModel):
    mid: str
    sender_nickname: str
    type: str
    content: str | None
    is_recalled: bool = False


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mid: str
    sender_uid: str
    sender_nickname: str
    is_self: bool
    type: str
    content: str | None
    media_url: str | None
    audio_duration_sec: int | None = None
    is_favorite: bool = False
    is_future: bool = False
    is_recalled: bool = False
    can_recall: bool = False
    recalled_at: datetime | None = None
    reply_to: ChatReplyPreview | None = None
    read_at: datetime | None
    visible_at: datetime | None
    created_at: datetime
    # E2EE envelope: when is_encrypted=True, content / media_url are
    # base64 ciphertext and the client must decrypt with its derived
    # key using (iv, ciphertext, algo). When False, content is the
    # server's plaintext.
    is_encrypted: bool = False
    iv: str | None = None
    ciphertext: str | None = None
    algo: str | None = None


class ChatHistoryResponse(BaseModel):
    items: list[ChatMessageResponse]
    has_more: bool
    first_unread_mid: str | None = None
    # The cursor (oldest loaded message id) to pass as ``before_id`` for the
    # next older page. Null when there is no more history.
    next_before_id: int | None


class ChatStateResponse(BaseModel):
    """Snapshot for the cottage realtime header / home presence card."""

    partner_uid: str | None
    partner_nickname: str | None
    partner_online: bool
    partner_online_since: datetime | None = None
    partner_last_active_at: datetime | None = None
    self_online: bool
    unread: int


class ChatFavoriteListResponse(BaseModel):
    items: list[ChatMessageResponse]


class ChatPinnedQuoteRequest(BaseModel):
    mid: str = Field(min_length=1, max_length=64)


class ChatPinnedQuoteResponse(BaseModel):
    message: ChatMessageResponse | None


class ChatKeywordItem(BaseModel):
    keyword: str
    count: int


class ChatKeywordsResponse(BaseModel):
    on: date
    items: list[ChatKeywordItem]


class ChatMemoryCardResponse(BaseModel):
    on: date
    total_messages: int
    self_messages: int
    partner_messages: int
    favorite_count: int
    first_message: ChatMessageResponse | None
    last_message: ChatMessageResponse | None
    pinned_quote: ChatMessageResponse | None
    keywords: list[ChatKeywordItem]


class ChatSearchResponse(BaseModel):
    query: str
    items: list[ChatMessageResponse]


class ChatFutureMessagesResponse(BaseModel):
    items: list[ChatMessageResponse]


class ChatMediaPanelResponse(BaseModel):
    images: list[ChatMessageResponse]
    stickers: list[ChatMessageResponse]
    voices: list[ChatMessageResponse]
    favorites: list[ChatMessageResponse]


class PokeRequest(BaseModel):
    """Request body for ``POST /v1/cottage/poke`` — a lightweight nudge."""

    kind: str = Field(default="poke", max_length=16)

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        allowed = {"poke", "miss", "hug", "kiss"}
        normalized = (value or "poke").strip().lower()
        if normalized not in allowed:
            raise ValueError("不支持的互动类型")
        return normalized
