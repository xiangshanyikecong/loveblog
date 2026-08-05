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

from pydantic import BaseModel, ConfigDict, Field, model_validator


_NOTE_MAX = 2000


class PeriodCreateRequest(BaseModel):
    """Request body for ``POST /v1/cottage/period``."""

    start_date: date
    end_date: date | None = None
    note: str | None = Field(default=None, max_length=_NOTE_MAX)

    @model_validator(mode="after")
    def _check_dates(self) -> "PeriodCreateRequest":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class PeriodUpdateRequest(BaseModel):
    """Partial update for a period cycle."""

    start_date: date | None = None
    end_date: date | None = None
    note: str | None = Field(default=None, max_length=_NOTE_MAX)

    @model_validator(mode="after")
    def _check_dates(self) -> "PeriodUpdateRequest":
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("结束日期不能早于开始日期")
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class PeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pcid: str
    start_date: date
    end_date: date | None
    note: str | None
    # Number of days this period lasted (inclusive); None while ongoing.
    length_days: int | None
    author_uid: str
    author_nickname: str
    created_at: datetime


class PeriodListResponse(BaseModel):
    items: list[PeriodResponse]
    total: int


class PeriodSummaryResponse(BaseModel):
    cycle_count: int
    # Average gap between consecutive period starts (full cycle length).
    avg_cycle_days: int | None
    # Average bleeding duration across cycles with a recorded end_date.
    avg_period_days: int | None
    last_start: date | None
    last_end: date | None
    predicted_next_start: date | None
    # Days from today until the predicted next start (negative if overdue).
    predicted_days_until: int | None
    # One of: "in_period" / "due_soon" / "overdue" / "normal" / "unknown".
    phase: str
