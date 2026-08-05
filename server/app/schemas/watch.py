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

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


_TITLE_MAX = 200
_URL_MAX = 4000


class WatchSourceCreateRequest(BaseModel):
    """Add a direct-URL source to the shared library (``POST .../sources``).

    Only http(s) direct links or this site's own ``/uploads/...`` paths are
    accepted. Uploaded files use the separate multipart upload endpoint.
    """

    title: str = Field(min_length=1, max_length=_TITLE_MAX)
    url: str = Field(min_length=1, max_length=_URL_MAX)
    poster_url: str | None = Field(default=None, max_length=_URL_MAX)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("标题不能为空")
        return normalized

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        v = (value or "").strip()
        if not (v.startswith("http://") or v.startswith("https://") or v.startswith("/uploads/")):
            raise ValueError("仅支持 http(s) 直链或本站上传的视频")
        return v

    @field_validator("poster_url")
    @classmethod
    def _normalize_poster(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class WatchSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    wsid: str
    title: str
    kind: str  # "upload" | "url"
    url: str
    poster_url: str | None
    size_bytes: int | None
    author_uid: str
    author_nickname: str
    created_at: datetime
    # Resume + bookmarks (added 2026-07).
    last_position_ms: int = 0
    last_viewed_at: datetime | None = None
    bookmarks: list["WatchBookmark"] = []


class WatchBookmark(BaseModel):
    """A position the couple pinned so it's easy to jump back later.

    ``vid`` is a stable per-bookmark id the client can use to delete the
    bookmark without a server-side index.
    """

    bid: str
    position_ms: int
    label: str
    created_at: datetime
    created_by_uid: str


class WatchSourcePatchRequest(BaseModel):
    """Partial update for resume position and/or bookmarks.

    Both fields are optional; an empty body is a no-op. ``bookmarks``
    REPLACES the list in full — clients should always read the current
    list and put it back. ``last_position_ms`` must be ``>= 0``; the
    server does not know the source duration, so a rewind past the end is
    the client's responsibility (e.g. clamp against the HTMLMediaElement).
    """

    model_config = ConfigDict(extra="forbid")

    last_position_ms: int | None = Field(default=None, ge=0)
    bookmarks: list[WatchBookmark] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=_TITLE_MAX)
    poster_url: str | None = Field(default=None, max_length=_URL_MAX)

    @field_validator("title")
    @classmethod
    def _normalize_patch_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("标题不能为空")
        return normalized

    @field_validator("poster_url")
    @classmethod
    def _normalize_patch_poster(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class WatchSourceListResponse(BaseModel):
    items: list[WatchSourceResponse]
    total: int


class WatchPartnerState(BaseModel):
    user_uid: str
    nickname: str
    online: bool


class WatchCurrent(BaseModel):
    """The room's current playback head, synthesized live on read."""

    source_wsid: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    source_kind: str | None = None
    paused: bool = True
    position_ms: int = 0
    rate: float = 1.0
    started_by: str | None = None
    event_seq: int = 0
    server_ts_ms: int = 0


class WatchStateResponse(BaseModel):
    current: WatchCurrent
    partners: list[WatchPartnerState]
