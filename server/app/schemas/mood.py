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

_NOTE_MAX = 500


class MoodCheckinRequest(BaseModel):
    """Request body for ``POST /v1/cottage/mood`` (upsert today's mood)."""

    mood: str = Field(min_length=1, max_length=32)
    emoji: str | None = Field(default=None, max_length=16)
    note: str | None = Field(default=None, max_length=_NOTE_MAX)
    # The client's local calendar date. Defaults to server UTC today when
    # omitted, but the frontend always sends its own local date so the entry
    # lands on the couple's local day.
    mood_date: date | None = None

    @field_validator("mood")
    @classmethod
    def _normalize_mood(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("心情不能为空")
        return normalized

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class MoodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mid: str
    author_uid: str
    author_nickname: str
    is_self: bool
    mood_date: date
    mood: str
    emoji: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class MoodTodayResponse(BaseModel):
    mine: MoodResponse | None
    partner: MoodResponse | None


class MoodCalendarResponse(BaseModel):
    year: int
    month: int
    items: list[MoodResponse]
