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
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CapsuleCreateRequest(BaseModel):
    # Text is optional: a capsule may be a pure voice / video message.
    content: str | None = Field(default=None, max_length=5000)
    open_at: datetime
    media_url: str | None = Field(default=None, max_length=512)
    media_type: str | None = Field(default=None, max_length=16)
    media_duration_sec: int | None = Field(default=None, ge=0, le=24 * 3600)

    @model_validator(mode="after")
    def _require_text_or_media(self) -> "CapsuleCreateRequest":
        text = (self.content or "").strip()
        if not text and not self.media_url:
            raise ValueError("胶囊需要文字或语音/视频内容")
        if self.media_url and self.media_type not in ("audio", "video"):
            raise ValueError("media_type 必须是 audio 或 video")
        return self


class CapsuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: str
    content: str | None  # Masked (None) until open_at
    open_at: datetime
    created_at: datetime
    author_uid: str
    author_nickname: str
    is_open: bool
    has_media: bool = False
    media_type: str | None = None
    media_duration_sec: int | None = None
    media_url: str | None = None  # Masked (None) until open_at
