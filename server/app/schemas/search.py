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
from typing import Literal

from pydantic import BaseModel, Field


SearchContentType = Literal["article", "album", "event", "moment", "message"]
SearchTagMode = Literal["any", "all"]


class SearchResultItem(BaseModel):
    type: SearchContentType
    id: str
    title: str
    snippet: str
    url: str
    date: datetime
    tags: list[str] = Field(default_factory=list)
    visibility: str
    is_encrypted: bool = False
    author_nickname: str | None = None


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    total: int
    page: int
    page_size: int
    q: str | None
    types: list[SearchContentType]
    tags: list[str]
    tag_mode: SearchTagMode
