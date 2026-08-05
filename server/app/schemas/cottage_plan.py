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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


_TITLE_MAX = 160
_TEXT_MAX = 2000
_LOCATION_MAX = 160
_CHECKLIST_MAX = 30

CottagePlanStatusValue = Literal["planned", "in_progress", "done", "cancelled"]


class PlanChecklistItem(BaseModel):
    key: str | None = Field(default=None, max_length=64)
    text: str = Field(min_length=1, max_length=160)
    done: bool = False

    @field_validator("key")
    @classmethod
    def _strip_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("text")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("checklist text cannot be empty")
        return normalized


class CottagePlanCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=_TITLE_MAX)
    description: str | None = Field(default=None, max_length=_TEXT_MAX)
    location: str | None = Field(default=None, max_length=_LOCATION_MAX)
    plan_date: date | None = None
    priority: int = Field(default=0, ge=0, le=1000)
    checklist: list[PlanChecklistItem] = Field(default_factory=list, max_length=_CHECKLIST_MAX)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("plan title cannot be empty")
        return normalized

    @field_validator("description", "location")
    @classmethod
    def _normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CottagePlanUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=_TITLE_MAX)
    description: str | None = Field(default=None, max_length=_TEXT_MAX)
    location: str | None = Field(default=None, max_length=_LOCATION_MAX)
    plan_date: date | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    checklist: list[PlanChecklistItem] | None = Field(default=None, max_length=_CHECKLIST_MAX)
    status: CottagePlanStatusValue | None = None

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("plan title cannot be empty")
        return normalized

    @field_validator("description", "location")
    @classmethod
    def _normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CottagePlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pid: str
    title: str
    description: str | None
    location: str | None
    plan_date: date | None
    status: str
    priority: int
    checklist: list[PlanChecklistItem]
    author_uid: str
    author_nickname: str
    completed_at: datetime | None
    completed_by_uid: str | None
    completed_by_nickname: str | None
    created_at: datetime
    updated_at: datetime


class CottagePlanListResponse(BaseModel):
    items: list[CottagePlanResponse]
    total: int
    active: int
    completed: int
    cancelled: int
