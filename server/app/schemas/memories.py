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

"""Schemas for the on-this-day memories API."""

from pydantic import BaseModel, Field


class MemoryArticleItem(BaseModel):
    """One diary article remembered on this day."""

    aid: str
    title: str
    excerpt: str | None = None
    created_at: str


class MemoryAlbumItem(BaseModel):
    """One photo album remembered on this day."""

    alb_id: str
    title: str
    cover_url: str | None = None
    created_at: str


class MemorySongItem(BaseModel):
    """One listen-together play remembered on this day."""

    song_id: str
    name: str
    artists: list[str] = Field(default_factory=list)
    cover_url: str | None = None
    played_at: str


class MemoryTotals(BaseModel):
    """True (uncapped) counts of matched items."""

    articles: int
    albums: int
    songs: int


class MemoryYearGroup(BaseModel):
    """Everything that happened on this month/day in one past year."""

    year: int
    articles: list[MemoryArticleItem] = Field(default_factory=list)
    albums: list[MemoryAlbumItem] = Field(default_factory=list)
    songs: list[MemorySongItem] = Field(default_factory=list)
    totals: MemoryTotals


class OnThisDayResponse(BaseModel):
    date: str
    years: list[MemoryYearGroup] = Field(default_factory=list)
    totals: MemoryTotals
