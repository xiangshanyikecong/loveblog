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

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CommentCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    parent_cid: str | None = None
    mention_uids: list[str] = Field(default_factory=list)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Comment content cannot be blank")
        return normalized


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cid: str
    parent_cid: str | None
    content: str
    author_uid: str
    author_nickname: str
    mention_uids: list[str] = Field(default_factory=list)
    created_at: datetime


class CommentNodeResponse(CommentResponse):
    replies: list["CommentNodeResponse"] = Field(default_factory=list)


CommentNodeResponse.model_rebuild()
