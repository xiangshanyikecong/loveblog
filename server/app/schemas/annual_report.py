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

"""Schemas for the couple annual report API."""

from pydantic import BaseModel, Field


class AnnualStats(BaseModel):
    """Whole-year counts across the couple's shared content."""

    articles: int
    albums: int
    photos: int
    checkins: int
    messages: int
    songs_played: int
    songs_minutes: int
    capsules_created: int
    wishes_completed: int


class MonthlyActivity(BaseModel):
    """Per-month counts for the year activity chart."""

    month: int
    articles: int
    songs: int
    checkins: int


class TopSong(BaseModel):
    """One song with its play count for the year."""

    song_id: str
    name: str
    artists: list[str] = Field(default_factory=list)
    cover_url: str | None = None
    play_count: int


class AnnualReportResponse(BaseModel):
    year: int
    couple_since: str | None = None
    days_together: int
    stats: AnnualStats
    monthly: list[MonthlyActivity] = Field(default_factory=list)
    top_songs: list[TopSong] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
