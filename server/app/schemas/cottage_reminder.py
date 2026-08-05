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

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


_TITLE_MAX = 160
_NOTE_MAX = 1000
ReminderAudience = Literal["both", "me", "partner"]


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class CottageReminderCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=_TITLE_MAX)
    note: str | None = Field(default=None, max_length=_NOTE_MAX)
    remind_at: datetime
    audience: ReminderAudience = "both"

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("reminder title cannot be empty")
        return normalized

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("remind_at")
    @classmethod
    def _normalize_remind_at(cls, value: datetime) -> datetime:
        return _normalize_datetime(value)


class CottageReminderUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=_TITLE_MAX)
    note: str | None = Field(default=None, max_length=_NOTE_MAX)
    remind_at: datetime | None = None
    audience: ReminderAudience | None = None

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("reminder title cannot be empty")
        return normalized

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("remind_at")
    @classmethod
    def _normalize_remind_at(cls, value: datetime | None) -> datetime | None:
        return _normalize_datetime(value) if value is not None else None


class CottageReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rid: str
    title: str
    note: str | None
    remind_at: datetime
    audience: str
    is_due: bool
    is_done: bool
    author_uid: str
    author_nickname: str
    done_at: datetime | None
    done_by_uid: str | None
    done_by_nickname: str | None
    created_at: datetime
    updated_at: datetime


class CottageReminderListResponse(BaseModel):
    items: list[CottageReminderResponse]
    total: int
    active: int
    done: int
    due: int
