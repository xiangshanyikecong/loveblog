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

import re

from pydantic import BaseModel, Field, field_validator


_QQ_NUMBER_PATTERN = re.compile(r"^\d{5,12}$")


class UploadResponse(BaseModel):
    url: str
    file_name: str
    content_type: str | None
    size: int


class QQAvatarRequest(BaseModel):
    """Fetch an avatar image from a QQ account by its number."""

    qq: str = Field(min_length=5, max_length=12)

    @field_validator("qq")
    @classmethod
    def validate_qq(cls, value: str) -> str:
        normalized = value.strip()
        if not _QQ_NUMBER_PATTERN.fullmatch(normalized):
            raise ValueError("QQ 号应为 5-12 位数字")
        return normalized


class UploadCleanupResponse(BaseModel):
    dry_run: bool
    scanned: int
    referenced: int
    orphaned: int
    deleted: int
    deleted_files: list[str] = Field(default_factory=list)
