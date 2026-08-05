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


_TITLE_MAX = 160
_DESC_MAX = 2000
_ICON_MAX = 16


class CouponCreateRequest(BaseModel):
    """Request body for ``POST /v1/cottage/coupons``."""

    title: str = Field(min_length=1, max_length=_TITLE_MAX)
    description: str | None = Field(default=None, max_length=_DESC_MAX)
    icon: str | None = Field(default=None, max_length=_ICON_MAX)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("兑换券名称不能为空")
        return normalized

    @field_validator("description", "icon")
    @classmethod
    def _normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CouponUpdateRequest(BaseModel):
    """Partial update for a coupon (only the author may edit, before redeem)."""

    title: str | None = Field(default=None, max_length=_TITLE_MAX)
    description: str | None = Field(default=None, max_length=_DESC_MAX)
    icon: str | None = Field(default=None, max_length=_ICON_MAX)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("兑换券名称不能为空")
        return normalized

    @field_validator("description", "icon")
    @classmethod
    def _normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CouponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cpid: str
    title: str
    description: str | None
    icon: str | None
    status: str  # see app.models.coupon.CouponStatus values
    author_uid: str
    author_nickname: str
    # True when the current viewer issued this coupon (i.e. it is outgoing).
    is_mine: bool
    redeemed_at: datetime | None
    redeemed_by_uid: str | None
    redeemed_by_nickname: str | None
    created_at: datetime


class CouponListResponse(BaseModel):
    items: list[CouponResponse]
    total: int
    active: int
    redeemed: int
