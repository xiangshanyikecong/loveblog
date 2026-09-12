# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import json
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ListenLikedTrack(Base):
    """A song liked ("我喜欢") by a specific partner in cottage listen-together."""

    __tablename__ = "listen_liked_tracks"
    __table_args__ = (UniqueConstraint("user_id", "song_id", name="uq_listen_liked_user_song"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    song_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    artists_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    album: Mapped[str | None] = mapped_column(String(256), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    @property
    def artists(self) -> list[str]:
        try:
            data = json.loads(self.artists_json or "[]")
            return [str(a) for a in data if a] if isinstance(data, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
