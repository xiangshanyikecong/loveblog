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

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WatchSource(Base):
    """A video source in the cottage "watch together" (一起看) shared library.

    Either partner may add a source — an uploaded video file stored under
    ``/uploads/videos`` (``kind="upload"``) or a direct, non-DRM playable URL
    such as a ``.mp4`` / ``.m3u8`` link (``kind="url"``). Both partners pick a
    source from this shared library and load it into the room; playback is then
    kept in sync over the watch WebSocket.

    Scope note: premium streaming platforms (Netflix / 腾讯视频 / 爱奇艺 /
    Disney+ …) cannot be co-watched here because of DRM + cross-origin
    restrictions, so sources are intentionally limited to self-hosted files and
    plain direct links.
    """

    __tablename__ = "watch_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    wsid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # "upload" → url is a server-relative ``/uploads/videos/...`` path;
    # "url"    → url is an external / direct playable link.
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional poster / cover image URL. Unused by the M1 player but kept for a
    # richer library UI later without a follow-up migration.
    poster_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Bytes for uploaded files (None for external URLs). BigInteger so a
    # multi-GB movie doesn't overflow a 4-byte INT on PostgreSQL.
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
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
    # Resume-position bookkeeping. Both partners can update this; it's a
    # "shared last seen" so a late joiner knows where to start the video.
    last_position_ms: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Bookmarks the couple pinned to a position. JSON list of
    # ``{position_ms, label, created_at, created_by_uid}``.
    bookmarks_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    author = relationship("User", foreign_keys=[author_id])
