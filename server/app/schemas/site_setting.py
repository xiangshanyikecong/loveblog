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

from app.core.media import ALL_IMAGE_TYPES


class SiteSettingResponse(BaseModel):
    site_name: str
    love_start_date: datetime | None
    uploads_root: str
    articles_path: str
    albums_path: str
    avatar_path: str
    timeline_path: str
    videos_path: str
    allow_registration: bool
    partner_a_avatar: str | None
    partner_b_avatar: str | None
    # Media policy
    max_image_kb: int
    thumb_width: int
    compress_quality: int
    strip_exif: bool
    allowed_image_types: str


class SiteSettingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_name: str | None = Field(default=None, max_length=120)
    love_start_date: datetime | None = None
    uploads_root: str | None = Field(default=None, max_length=255)
    articles_path: str | None = Field(default=None, max_length=255)
    albums_path: str | None = Field(default=None, max_length=255)
    avatar_path: str | None = Field(default=None, max_length=255)
    timeline_path: str | None = Field(default=None, max_length=255)
    videos_path: str | None = Field(default=None, max_length=255)
    allow_registration: bool | None = None
    partner_a_avatar: str | None = Field(default=None, max_length=255)
    partner_b_avatar: str | None = Field(default=None, max_length=255)
    # Media policy
    max_image_kb: int | None = Field(default=None, ge=0, le=102400)
    thumb_width: int | None = Field(default=None, ge=0, le=4096)
    compress_quality: int | None = Field(default=None, ge=1, le=95)
    strip_exif: bool | None = None
    allowed_image_types: str | None = Field(default=None, max_length=512)

    @field_validator("love_start_date", mode="before")
    @classmethod
    def normalize_love_start_date(cls, value):
        if value == "":
            return None
        return value

    @field_validator(
        "site_name", "uploads_root", "articles_path", "albums_path",
        "avatar_path", "timeline_path", "videos_path",
    )
    @classmethod
    def validate_non_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank")
        return normalized

    @field_validator("allowed_image_types", mode="before")
    @classmethod
    def validate_allowed_image_types(cls, value: str | None) -> str | None:
        if value is None:
            return None
        types = [t.strip().lower() for t in value.split(",") if t.strip()]
        invalid = [t for t in types if t not in ALL_IMAGE_TYPES]
        if invalid:
            raise ValueError(
                f"不支持的 MIME 类型: {', '.join(invalid)}。"
                f"可用类型: {', '.join(sorted(ALL_IMAGE_TYPES))}"
            )
        if not types:
            raise ValueError("至少需要选择一种图片类型")
        return ",".join(types)
