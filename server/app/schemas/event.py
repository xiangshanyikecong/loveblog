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

from datetime import date as DateType, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.tags import normalize_tags
from app.models.event import EventType, Visibility


class EventCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    date: DateType
    type: EventType = EventType.countdown
    is_important: bool = False
    is_yearly_repeat: bool = False
    visibility: Visibility = Visibility.public
    tags: list[str] = Field(default_factory=list)

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


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    eid: str
    title: str
    date: DateType
    type: EventType
    creator_uid: str
    creator_nickname: str
    is_important: bool
    is_yearly_repeat: bool
    visibility: Visibility
    tags: list[str]
    next_occurrence_days: int | None
    created_at: datetime


class EventListResponse(BaseModel):
    items: list[EventResponse]
    total: int


class EventPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)
    date: DateType | None = None
    type: EventType | None = None
    is_important: bool | None = None
    is_yearly_repeat: bool | None = None
    visibility: Visibility | None = None
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
