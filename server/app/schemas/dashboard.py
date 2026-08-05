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

from pydantic import BaseModel

from app.schemas.album import AlbumSummaryResponse
from app.schemas.article import ArticleSummaryResponse
from app.schemas.event import EventResponse
from app.schemas.message import MessageResponse


class DashboardStats(BaseModel):
    article_count: int
    album_count: int
    event_count: int
    message_count: int


class LoveClock(BaseModel):
    days: int
    hours: int
    minutes: int
    seconds: int


class CoupleMember(BaseModel):
    """A single half of the couple, for the personalized homepage header."""

    role: str
    nickname: str | None = None
    avatar: str | None = None


class CoupleInfo(BaseModel):
    partner_a: CoupleMember | None = None
    partner_b: CoupleMember | None = None


class DashboardResponse(BaseModel):
    love_clock: LoveClock
    stats: DashboardStats
    couple: CoupleInfo
    recent_events: list[EventResponse]
    latest_articles: list[ArticleSummaryResponse]
    latest_albums: list[AlbumSummaryResponse]
    latest_messages: list[MessageResponse]
