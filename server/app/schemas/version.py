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
from typing import Any

from pydantic import BaseModel, ConfigDict


class ContentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vid: str
    content_type: str
    content_id: str
    version: int
    title: str | None
    snapshot: dict[str, Any]
    note: str | None
    actor_uid: str | None
    actor_nickname: str | None
    created_at: datetime


class ContentVersionListResponse(BaseModel):
    items: list[ContentVersionResponse]
    total: int
