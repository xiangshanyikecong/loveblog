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

from pydantic import BaseModel, Field, field_validator


class BackupScheduleUpdateRequest(BaseModel):
    enabled: bool = False
    interval_hours: int = Field(default=24, ge=1, le=168)
    keep_last: int = Field(default=7, ge=1, le=30)
    backup_dir: str = Field(default="backups", min_length=1, max_length=120)

    @field_validator("backup_dir")
    @classmethod
    def validate_backup_dir(cls, value: str) -> str:
        normalized = value.strip().replace("\\", "/")
        if not normalized or normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("Backup directory must be a relative path")
        return normalized


class BackupScheduleResponse(BackupScheduleUpdateRequest):
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    updated_at: datetime | None = None


class AutoBackupRunResponse(BaseModel):
    ok: bool
    message: str
    record: dict
