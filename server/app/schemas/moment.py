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

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.tags import normalize_tags
from app.models.moment import Visibility
from app.schemas.comment import CommentNodeResponse


TimelineSort = Literal["asc", "desc"]
_MAX_MEDIA_URLS = 9


class MomentCreateRequest(BaseModel):
    # Optional so a moment can be a pure voice diary; cross-checked below.
    content: str = Field(default="", max_length=5000)
    media_urls: list[str] = Field(default_factory=list)
    audio_url: str | None = Field(default=None, max_length=512)
    audio_duration_sec: int | None = Field(default=None, ge=0, le=24 * 3600)
    location: str | None = Field(default=None, max_length=255)
    visibility: Visibility = Visibility.public
    tags: list[str] = Field(default_factory=list)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return value.strip()

    @field_validator("audio_url")
    @classmethod
    def validate_audio_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        url = value.strip()
        if not url:
            return None
        # Accept our own server-relative upload paths or absolute http(s) URLs.
        if url.startswith("/uploads/"):
            return url
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return url
        raise ValueError("audio_url must be a /uploads path or http(s) URL")

    @model_validator(mode="after")
    def _require_text_or_audio(self) -> "MomentCreateRequest":
        if not self.content and not self.audio_url:
            raise ValueError("说点什么，或录一段语音吧")
        return self

    @field_validator("media_urls")
    @classmethod
    def validate_media_urls(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for raw in values:
            url = raw.strip()
            if not url or url in seen:
                continue

            # Accept our own server-relative upload paths (e.g. the
            # /uploads/timeline/... value the upload endpoint returns and the
            # frontend posts straight back) as well as absolute http(s) URLs,
            # mirroring the ``audio_url`` validator above.
            if not url.startswith("/uploads/"):
                parsed = urlparse(url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError("Each media url must be a /uploads path or http(s) URL")

            seen.add(url)
            normalized.append(url)

        if len(normalized) > _MAX_MEDIA_URLS:
            raise ValueError(f"At most {_MAX_MEDIA_URLS} media URLs are allowed")
        return normalized

    @field_validator("location")
    @classmethod
    def validate_location(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)


class MomentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mid: str
    author_uid: str
    author_nickname: str
    content: str
    media_urls: list[str]
    audio_url: str | None = None
    audio_duration_sec: int | None = None
    location: str | None
    visibility: Visibility
    tags: list[str]
    timestamp: datetime
    comments: list[CommentNodeResponse] = Field(default_factory=list)


class TimelineListResponse(BaseModel):
    items: list[MomentResponse]
    page: int
    page_size: int
    total: int
    has_next: bool
    sort: TimelineSort
