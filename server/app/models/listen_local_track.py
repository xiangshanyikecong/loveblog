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

import json
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ListenLocalTrack(Base):
    """A partner-uploaded audio file for cottage listen-together.

    Lets the couple play music without a NetEase scan-login (which requires
    the phone app and blocks playback behind a 409). The track is surfaced to
    the player with a synthetic ``song_id`` of ``local:<tid>`` so it routes
    around the NetEase URL resolver while reusing the same play / queue / WS
    sync machinery as NetEase songs.
    """

    __tablename__ = "listen_local_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    artists_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    album: Mapped[str | None] = mapped_column(String(256), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    audio_url: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_by_uid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def artists(self) -> list[str]:
        try:
            data = json.loads(self.artists_json or "[]")
            return [str(a) for a in data if a] if isinstance(data, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    @property
    def song_id(self) -> str:
        return f"local:{self.tid}"
