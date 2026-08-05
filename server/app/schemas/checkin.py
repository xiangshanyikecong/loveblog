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

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Mirrors MomentCreateRequest's media-url cap so the upload pipeline reuse stays
# symmetric. Note we accept server-relative ``/uploads/...`` paths here (not
# absolute http/https URLs) because the upload endpoints return relative paths
# by design (see archived spec ``upload-absolute-url-host-leak``).
_MAX_MEDIA_URLS = 9
_CONTENT_MAX_LENGTH = 1000


class CheckInCreateRequest(BaseModel):
    """Request body for ``POST /v1/checkins``.

    Privacy invariant: ``latitude`` / ``longitude`` are *transient* — the
    backend uses them to call the geocoding provider and discards them
    before persisting. The schema permits them on the request only.
    """

    content: str | None = Field(default=None, max_length=_CONTENT_MAX_LENGTH)
    media_urls: list[str] = Field(default_factory=list)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_permission_denied: bool = False

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("media_urls")
    @classmethod
    def validate_media_urls(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in values:
            url = (raw or "").strip()
            if not url or url in seen:
                continue
            # Accept only server-relative /uploads/<...> paths. This rejects
            # absolute http/https URLs (host-locked, see archived spec) and
            # any path outside /uploads/.
            if not url.startswith("/uploads/"):
                raise ValueError("Each media url must start with /uploads/")
            seen.add(url)
            normalized.append(url)
        if len(normalized) > _MAX_MEDIA_URLS:
            raise ValueError(f"At most {_MAX_MEDIA_URLS} media URLs are allowed")
        return normalized


class CheckInResponse(BaseModel):
    """Response shape for a single CheckIn record.

    Privacy invariant: this model deliberately does NOT include ``latitude``,
    ``longitude``, or any IP-derived field. Those values are never persisted
    on the row, so they cannot leak through this response either.
    """

    model_config = ConfigDict(from_attributes=True)

    cid: str
    author_uid: str
    author_nickname: str
    content: str | None
    media_urls: list[str]
    location_text: str | None
    location_status: str  # see app.models.checkin.LocationStatus values
    location_provider: str | None
    created_at: datetime


class CheckInLatestResponse(BaseModel):
    item: CheckInResponse | None


class CheckInListResponse(BaseModel):
    items: list[CheckInResponse]
    page: int
    page_size: int
    total: int
    has_next: bool
