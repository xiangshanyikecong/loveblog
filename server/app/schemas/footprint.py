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


class FootprintCity(BaseModel):
    """One visited city aggregated from resolved check-ins."""

    city: str
    count: int
    first_at: datetime
    last_at: datetime


class FootprintRecent(BaseModel):
    """A recent located check-in, surfaced as a timeline entry on the map."""

    city: str
    author_nickname: str
    created_at: datetime


class FootprintResponse(BaseModel):
    cities: list[FootprintCity]
    total_cities: int
    total_checkins: int
    recent: list[FootprintRecent]
