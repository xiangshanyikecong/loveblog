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
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.tags import normalize_tags
from app.models.album import MediaType
from app.models.content_visibility import ContentVisibility

if TYPE_CHECKING:
    pass


class AlbumMediaCreateRequest(BaseModel):
    media_type: MediaType = MediaType.image
    file_url: str = Field(min_length=1, max_length=255)
    thumbnail_url: str | None = Field(default=None, max_length=255)
    file_size: int | None = Field(default=None, ge=0)
    mime_type: str | None = Field(default=None, max_length=80)
    is_encrypted: bool = False

    @field_validator("file_url")
    @classmethod
    def validate_file_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("file_url cannot be blank")
        return normalized


class AlbumCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = None
    cover_url: str | None = Field(default=None, max_length=255)
    is_encrypted: bool = False
    is_public: bool = True
    visibility: ContentVisibility = ContentVisibility.public
    password: str | None = Field(default=None, max_length=100, description="密码保护时的密码")
    tags: list[str] = Field(default_factory=list)
    media_items: list[AlbumMediaCreateRequest] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Title cannot be blank")
        return normalized

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)


class AlbumMediaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    media_id: str
    media_type: MediaType
    file_url: str
    thumbnail_url: str | None
    file_size: int | None
    mime_type: str | None
    is_encrypted: bool


class AlbumSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alb_id: str
    title: str
    description: str | None
    cover_url: str | None
    is_encrypted: bool
    is_public: bool
    visibility: ContentVisibility
    requires_password: bool = Field(default=False, description="是否需要密码")
    tags: list[str]
    author_uid: str
    author_nickname: str
    media_count: int
    created_at: datetime


class AlbumDetailResponse(AlbumSummaryResponse):
    media_items: list[AlbumMediaResponse]
    comments: list = Field(default_factory=list)  # 使用 list 而不是具体类型，避免循环导入


class AlbumListResponse(BaseModel):
    items: list[AlbumSummaryResponse]
    total: int


class AlbumPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    cover_url: str | None = Field(default=None, max_length=255)
    is_encrypted: bool | None = None
    is_public: bool | None = None
    visibility: ContentVisibility | None = None
    password: str | None = Field(default=None, max_length=100, description="密码保护时的密码，传空字符串清除密码")
    tags: list[str] | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Title cannot be blank")
        return normalized

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_tags(value)
