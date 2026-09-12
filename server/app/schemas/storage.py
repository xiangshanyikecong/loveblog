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

"""Response schemas for the storage usage panel."""

from pydantic import BaseModel


class DiskInfo(BaseModel):
    """Usage of the disk volume that hosts the uploads directory."""

    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float


class DirInfo(BaseModel):
    """Aggregated size and file count of the uploads directory tree."""

    total_bytes: int
    file_count: int


class DbInfo(BaseModel):
    """Size of the PostgreSQL database (null when the query fails)."""

    size_bytes: int | None


class CategoryUsage(BaseModel):
    """Usage of one first-level uploads sub-directory (chat, avatars, ...)."""

    category: str
    bytes: int
    file_count: int


class StorageUsageResponse(BaseModel):
    """Storage overview shared by the couple: disk / uploads / database."""

    disk: DiskInfo
    uploads: DirInfo
    database: DbInfo
    breakdown: list[CategoryUsage]
