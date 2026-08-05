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

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Visibility(str, enum.Enum):
    public = "Public"
    partners_only = "PartnersOnly"
    encrypted = "Encrypted"


class Moment(Base):
    __tablename__ = "moments"
    __table_args__ = (
        # Offline-replay dedup; one row per (author, idempotency_key).
        UniqueConstraint("author_id", "client_idempotency_key", name="uq_moment_author_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Optional voice-diary recording: a server-relative ``/uploads/...`` path.
    audio_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    audio_duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visibility: Mapped[Visibility] = mapped_column(
        Enum(Visibility, name="moment_visibility"), default=Visibility.public, nullable=False
    )
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Offline-replay dedup key supplied by the client (Android uses this so
    # the SyncEngine can safely retry a queued Moment create on reconnect).
    client_idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    author = relationship("User", back_populates="moments")
    comments = relationship(
        "Comment",
        back_populates="moment",
        cascade="all,delete-orphan",
        order_by="Comment.created_at.asc()",
    )
