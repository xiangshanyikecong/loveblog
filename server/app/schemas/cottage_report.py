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

from pydantic import BaseModel


class CottageMoodStat(BaseModel):
    mood: str
    emoji: str | None
    count: int


class CottageReportHighlight(BaseModel):
    kind: str
    title: str
    subtitle: str | None = None
    occurred_at: datetime | None = None


class CottageMonthlyReportResponse(BaseModel):
    year: int
    month: int
    start_date: str
    end_date: str
    generated_at: datetime
    stats: dict[str, int]
    top_moods: list[CottageMoodStat]
    highlights: list[CottageReportHighlight]
