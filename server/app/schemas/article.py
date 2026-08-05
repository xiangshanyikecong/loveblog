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
from app.models.article import ArticleBlockType, ArticleStatus
from app.models.content_visibility import ContentVisibility

if TYPE_CHECKING:
    pass


class ArticleBlockCreateRequest(BaseModel):
    block_type: ArticleBlockType = ArticleBlockType.paragraph
    content: str = Field(min_length=1, max_length=10000)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Block content cannot be blank")
        return normalized


class ArticleBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bid: str
    block_type: ArticleBlockType
    content: str
    sort_order: int
    author_uid: str
    author_nickname: str


class ArticleCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    excerpt: str | None = Field(default=None, max_length=320)
    status: ArticleStatus = ArticleStatus.draft
    is_encrypted: bool = False
    is_co_created: bool = Field(
        default=False,
        description="两人共同创作的文章。partner_can_edit 为 true 时也保持该标记。",
    )
    partner_can_edit: bool = False
    visibility: ContentVisibility = ContentVisibility.public
    password: str | None = Field(default=None, max_length=100, description="密码保护时的密码")
    cover_url: str | None = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=list)
    blocks: list[ArticleBlockCreateRequest] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Title cannot be blank")
        return normalized

    @field_validator("excerpt")
    @classmethod
    def validate_excerpt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)


class ArticleSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    aid: str
    title: str
    excerpt: str | None
    status: ArticleStatus
    is_encrypted: bool
    is_co_created: bool = False
    partner_can_edit: bool
    visibility: ContentVisibility
    requires_password: bool = Field(default=False, description="是否需要密码")
    tags: list[str]
    version: int = 1
    author_uid: str
    author_nickname: str
    published_at: datetime | None
    created_at: datetime
    # Unique uids of all users who have ever saved a block on this article
    # (the original author + any partner who co-edited). Used by the UI to
    # render the "两人共同创作" badge and the co-creators avatar row.
    collaborator_uids: list[str] = Field(default_factory=list)


class ArticleDetailResponse(ArticleSummaryResponse):
    blocks: list[ArticleBlockResponse]
    comments: list = Field(default_factory=list)  # 使用 list 而不是具体类型，避免循环导入


class ArticleListResponse(BaseModel):
    items: list[ArticleSummaryResponse]
    total: int


class ArticlePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    excerpt: str | None = Field(default=None, max_length=320)
    status: ArticleStatus | None = None
    is_encrypted: bool | None = None
    is_co_created: bool | None = Field(
        default=None,
        description="切换共同创作标记。设为 true 后将永久标记该文章为两人共同创作。",
    )
    partner_can_edit: bool | None = None
    visibility: ContentVisibility | None = None
    password: str | None = Field(default=None, max_length=100, description="密码保护时的密码，传空字符串清除密码")
    cover_url: str | None = Field(default=None, max_length=255)
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

    @field_validator("excerpt")
    @classmethod
    def validate_excerpt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_tags(value)
