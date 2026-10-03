# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
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


class CoupleLevel(BaseModel):
    level: int
    title: str
    points: int
    next_level_points: int | None = None
    next_level_title: str | None = None
    # 0-100 progress towards the next level (100 when max level reached).
    progress_percent: int


class BadgeProgress(BaseModel):
    code: str
    name: str
    description: str
    icon: str
    category: str
    # Highest achieved tier: "none" | "bronze" | "silver" | "gold".
    tier: str
    achieved: bool
    current: int
    next_target: int | None = None


class AchievementsResponse(BaseModel):
    generated_at: datetime
    stats: dict[str, int]
    level: CoupleLevel
    badges: list[BadgeProgress]
