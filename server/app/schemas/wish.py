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

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


_TITLE_MAX = 160
_DESC_MAX = 2000
_CATEGORY_MAX = 32


class WishCreateRequest(BaseModel):
    """Request body for ``POST /v1/cottage/wishes``."""

    title: str = Field(min_length=1, max_length=_TITLE_MAX)
    description: str | None = Field(default=None, max_length=_DESC_MAX)
    category: str | None = Field(default=None, max_length=_CATEGORY_MAX)
    target_date: date | None = None
    priority: int = Field(default=0, ge=0, le=1000)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("心愿标题不能为空")
        return normalized

    @field_validator("description", "category")
    @classmethod
    def _normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class WishUpdateRequest(BaseModel):
    """Partial update for a wish. Only provided fields are changed (PATCH).

    ``target_date`` may be explicitly set to ``null`` to clear it.
    """

    title: str | None = Field(default=None, max_length=_TITLE_MAX)
    description: str | None = Field(default=None, max_length=_DESC_MAX)
    category: str | None = Field(default=None, max_length=_CATEGORY_MAX)
    target_date: date | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("心愿标题不能为空")
        return normalized

    @field_validator("description", "category")
    @classmethod
    def _normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class WishResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    wid: str
    title: str
    description: str | None
    category: str | None
    status: str  # see app.models.wish.WishStatus values
    priority: int
    target_date: date | None
    author_uid: str
    author_nickname: str
    completed_at: datetime | None
    completed_by_uid: str | None
    completed_by_nickname: str | None
    created_at: datetime


class WishListResponse(BaseModel):
    items: list[WishResponse]
    total: int
    pending: int
    completed: int
