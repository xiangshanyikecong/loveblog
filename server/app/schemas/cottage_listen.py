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

"""Pydantic schemas for cottage-listen-together.

Privacy invariant: NO *response* schema in this file carries a NetEase cookie
field (by design). Routes that handle cookies use them only as function locals;
they don't get a chance to leak through any response model defined here.

The single exception is :class:`ImportCookieRequest` — an INBOUND-only schema
that carries a cookie the partner pasted in. It is consumed into the vault and
never echoed back in any response.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Auth (QR-code login)
# ---------------------------------------------------------------------------

class QrKeyResponse(BaseModel):
    unikey: str
    qr_image_data_url: str  # data:image/png;base64,...


class ImportCookieRequest(BaseModel):
    """Manually-imported NetEase cookie (defeats 异地登录 risk-control).

    The partner logs into music.163.com from their OWN network — which is
    in-region, so NetEase doesn't flag it — then pastes the cookie here. We
    only need ``MUSIC_U``; callers may paste the full cookie string and we
    extract it. INBOUND only; never returned in a response.
    """

    cookie: str


class QrStatusResponse(BaseModel):
    status: Literal["waiting", "scanned", "confirmed", "expired", "error"]
    message: str | None = None


# ---------------------------------------------------------------------------
# Song / playlist primitives
# ---------------------------------------------------------------------------

class SongMeta(BaseModel):
    """One song shown in the player, queue, or search result."""

    model_config = ConfigDict(from_attributes=True)

    song_id: str
    name: str
    artists: list[str]
    album: str | None = None
    duration_ms: int | None = None
    cover_url: str | None = None


class SongSearchResponse(BaseModel):
    items: list[SongMeta]
    page: int
    page_size: int
    has_next: bool


class PlaylistItem(BaseModel):
    playlist_id: str
    name: str
    cover_url: str | None = None
    track_count: int


class PlaylistsResponse(BaseModel):
    items: list[PlaylistItem]


class PlaylistTracksResponse(BaseModel):
    items: list[SongMeta]
    page: int
    page_size: int
    has_next: bool


class ToplistItem(BaseModel):
    """One official NetEase chart / ranking playlist."""

    toplist_id: str
    name: str
    cover_url: str | None = None
    update_frequency: str | None = None
    track_count: int = 0


class ToplistResponse(BaseModel):
    items: list[ToplistItem]


class ListenHistoryItem(SongMeta):
    """One recently played song in the shared room history."""

    played_at_ms: int
    started_by_uid: str


class ListenHistoryResponse(BaseModel):
    items: list[ListenHistoryItem]


class LocalTracksResponse(BaseModel):
    """Partner-uploaded audio files available to play without a NetEase login."""

    items: list[SongMeta]


# ---------------------------------------------------------------------------
# Direct URL
# ---------------------------------------------------------------------------

class SongUrlResponse(BaseModel):
    """Result of resolving a song's playable mp3 URL.

    ``url is None`` indicates the song is unplayable (copyright / VIP /
    region). The frontend treats this as "skip to next" rather than as an
    error condition. ``error_kind`` is a short tag the frontend uses for UI
    messaging.
    """

    song_id: str
    url: str | None
    expires_at_ms: int | None = None
    provider: Literal["netease", "local"] = "netease"
    error_kind: str | None = None


# ---------------------------------------------------------------------------
# Lyric
# ---------------------------------------------------------------------------

class LyricLine(BaseModel):
    """One timestamped lyric line. ``trans`` carries the Chinese translation
    for that same line when the song has one (foreign-language tracks)."""

    time_ms: int
    text: str
    trans: str | None = None


class SongLyricResponse(BaseModel):
    """Parsed lyric for a song.

    ``kind`` tells the frontend what to render when ``lines`` is empty:
    ``instrumental`` (pure music, no lyric exists) vs ``none`` (lyric not
    available / not yet transcribed). ``lrc`` means ``lines`` is populated.
    """

    song_id: str
    lines: list[LyricLine] = []
    kind: Literal["lrc", "instrumental", "none"] = "lrc"


# ---------------------------------------------------------------------------
# Room state
# ---------------------------------------------------------------------------

class PartnerLoginState(BaseModel):
    user_uid: str
    nickname: str
    netease_logged_in: bool


class RoomCurrent(BaseModel):
    song_id: str | None
    song_meta: SongMeta | None
    paused: bool
    position_ms: int
    started_by: str | None
    event_seq: int
    server_ts_ms: int


class RoomStateResponse(BaseModel):
    event_seq: int
    current: RoomCurrent
    queue: list[SongMeta]
    partners: list[PartnerLoginState]
