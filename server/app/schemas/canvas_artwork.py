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


class CanvasArtworkCreateRequest(BaseModel):
    """Body of ``POST /v1/cottage/canvas/artworks``.

    The client captures the live strokes once the partner presses save,
    rasterises them onto a 960x600 PNG, and uploads the payload. We do
    not rasterise server-side because (a) the client already has the
    canvas bitmap in memory, and (b) every drawing framework renders
    strokes slightly differently (round caps, brush textures, etc.) —
    re-rasterising on the server would lose the partner's exact pixels.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=120)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    strokes_json: str = Field(min_length=2, max_length=2_000_000)
    thumb_data_url: str = Field(min_length=32, max_length=2_000_000)

    @field_validator("strokes_json")
    @classmethod
    def _validate_strokes_shape(cls, value: str) -> str:
        # Cheap pre-check: must be parseable JSON with a 'strokes' list. We
        # do NOT re-render, just confirm the shape so we don't persist pure
        # garbage that would explode the gallery view.
        import json

        try:
            data = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("strokes_json 必须是合法 JSON") from exc
        if not isinstance(data, dict) or not isinstance(data.get("strokes"), list):
            raise ValueError("strokes_json 必须包含 strokes 数组")
        return value

    @field_validator("thumb_data_url")
    @classmethod
    def _validate_thumb(cls, value: str) -> str:
        if not value.startswith("data:image/"):
            raise ValueError("thumb_data_url 必须是 data:image/... 形式")
        return value

    width: int = Field(default=960, ge=64, le=4096)
    height: int = Field(default=600, ge=64, le=4096)
    # Optional client-side idempotency, so the Android SyncEngine can
    # safely retry the save across reconnects without duplicating rows.
    idempotency_key: str | None = Field(default=None, max_length=128)


class CanvasArtworkCollaboratorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_uid: str
    nickname: str
    stroke_count: int


class CanvasArtworkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    caid: str
    title: str | None
    width: int
    height: int
    stroke_count: int
    author_uid: str
    author_nickname: str
    thumb_data_url: str
    # When ``strokes_json`` is omitted (gallery list view), the client
    # re-fetches ``GET /{caid}`` to replay the drawing. The strokes are
    # intentionally kept out of list responses to keep the wire payload
    # small.
    strokes_json: str | None = None
    created_at: datetime
    updated_at: datetime
    collaborators: list[CanvasArtworkCollaboratorResponse] = []


class CanvasArtworkListResponse(BaseModel):
    items: list[CanvasArtworkResponse]
    total: int
    has_next: bool
