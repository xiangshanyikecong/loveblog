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

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatMessageType(str, enum.Enum):
    """Kind of a cottage chat message.

    Persisted as a plain ``String(16)`` (not a SQL ENUM) so SQLite / Postgres
    migrations stay symmetric and future additions don't need an ``ALTER TYPE``
    round-trip — mirroring ``CheckIn.location_status`` / ``Wish.status``.
    """

    text = "text"
    image = "image"
    sticker = "sticker"
    voice = "voice"
    system = "system"


class ChatMessage(Base):
    """A single message in the cottage two-person chat (小屋·悄悄话).

    The chat is a private 1:1 channel shared by the two partner accounts.
    Because there are at most two partners, "read" state is a single
    ``read_at`` timestamp set when the *recipient* reads the message — no
    per-user read table is needed.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        # Stable across offline-retry replays; mirrors the messages table.
        # Only enforced when the row was created with an Idempotency-Key
        # (nullable so historical rows / system messages still fit).
        UniqueConstraint("sender_id", "client_idempotency_key", name="uq_chat_message_sender_idempotency"),
    )

    # ── E2EE columns (added 2026-07) ──────────────────────────────────
    # When ``is_encrypted`` is true, ``content`` / ``media_url`` are
    # server-opaque ciphertext and ``iv`` is the AES-GCM nonce. The
    # server NEVER decrypts: it just stores + forwards ciphertext to
    # the partner over the realtime channel. Plaintext mode stays
    # supported for users who haven't enabled E2E.
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    iv: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    algo: Mapped[str | None] = mapped_column(String(16), nullable=True)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # One of ChatMessageType values, persisted as the string value.
    type: Mapped[str] = mapped_column(
        String(16), default=ChatMessageType.text.value, nullable=False
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Server-relative ``/uploads/...`` path for image / sticker messages.
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reply_to_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id"), nullable=True, index=True
    )
    # Set when the counterpart reads the message — drives the ✓✓ receipt.
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    # The time this message should become visible to both partners. Future
    # messages stay hidden until this timestamp arrives.
    visible_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # Set once the message has been "released" to the live chat stream.
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    recalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    # Offline-replay dedup; see UniqueConstraint above. Empty string is treated
    # the same as NULL by the unique index because SQLite/Postgres coalesce
    # NULLs in unique indexes (multiple NULLs are allowed).
    client_idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    sender = relationship("User", foreign_keys=[sender_id])
    reply_to = relationship("ChatMessage", remote_side=[id], foreign_keys=[reply_to_message_id])
