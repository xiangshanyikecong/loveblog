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

"""Pydantic schemas for the cottage-listen music library.

Two collections:

- Liked songs ("我喜欢") — per-partner favorites, keyed by (user_id, song_id).
- Couple playlists ("我们的歌单") — shared playlists both partners edit.

All datetime fields are serialized as ISO-8601 strings (``.isoformat()``).
``song_id`` values are either NetEase numeric ids or ``local:<tid>`` refs to
partner-uploaded audio.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Liked songs ("我喜欢")
# ---------------------------------------------------------------------------

class LikedTrackItem(BaseModel):
    """One liked song of the current partner."""

    song_id: str
    name: str
    artists: list[str] = []
    album: str | None = None
    duration_ms: int | None = None
    cover_url: str | None = None
    liked_at: str  # ISO-8601


class LikedTracksResponse(BaseModel):
    items: list[LikedTrackItem]
    total: int


class LikedStatusResponse(BaseModel):
    """Batch heart-state check: which of the queried song ids are liked.

    ``song_ids`` is the liked subset of the ids the caller asked about;
    ``total`` is the partner's overall liked count (same meaning as in
    :class:`LikedTracksResponse` / :class:`LikedToggleResponse`).
    """

    song_ids: list[str]
    total: int


class LikedToggleRequest(BaseModel):
    song_id: str
    name: str = ""
    artists: list[str] = []
    album: str | None = None
    duration_ms: int | None = None
    cover_url: str | None = None


class LikedToggleResponse(BaseModel):
    liked: bool
    total: int


# ---------------------------------------------------------------------------
# Couple playlists ("我们的歌单")
# ---------------------------------------------------------------------------

class PlaylistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    cover_url: str | None = None


class PlaylistUpdateRequest(BaseModel):
    """Partial playlist update — only non-None fields are applied."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    cover_url: str | None = None


class PlaylistTrackAddRequest(BaseModel):
    song_id: str
    name: str = ""
    artists: list[str] = []
    album: str | None = None
    duration_ms: int | None = None
    cover_url: str | None = None


class PlaylistTrackItem(BaseModel):
    """One song inside a playlist, ordered by ``position``."""

    song_id: str
    name: str
    artists: list[str] = []
    album: str | None = None
    duration_ms: int | None = None
    cover_url: str | None = None
    added_by_uid: str
    position: int
    added_at: str  # ISO-8601


class PlaylistSummary(BaseModel):
    """Playlist metadata as shown in the couple's playlist list."""

    pid: str
    name: str
    description: str | None = None
    cover_url: str | None = None
    created_by_uid: str
    track_count: int
    created_at: str  # ISO-8601
    updated_at: str  # ISO-8601


class PlaylistDetail(PlaylistSummary):
    """Summary plus the full ordered track list."""

    tracks: list[PlaylistTrackItem] = []
