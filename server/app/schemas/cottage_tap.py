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
from typing import Literal

from pydantic import BaseModel, Field


class TapCreateRequest(BaseModel):
    kind: Literal["tap", "heartbeat"] = "tap"


class TapResponse(BaseModel):
    tid: str
    kind: str
    from_uid: str
    from_nickname: str
    to_uid: str
    to_nickname: str
    created_at: datetime


class TapListResponse(BaseModel):
    items: list[TapResponse]
    total_kept: int = Field(
        description="How many taps are retained in total (rows are pruned beyond the cap)."
    )
