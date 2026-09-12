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

"""Request/response schemas for login-device management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class LoginDeviceResponse(BaseModel):
    """A device/browser recorded at login."""

    model_config = ConfigDict(from_attributes=True)

    did: str
    device_name: str
    ip: str | None
    user_agent: str | None
    first_seen_at: str
    last_login_at: str

    @field_validator("first_seen_at", "last_login_at", mode="before")
    @classmethod
    def _coerce_datetime(cls, value):
        # SQLAlchemy returns datetime objects; expose them as ISO-8601 strings.
        if isinstance(value, datetime):
            return value.isoformat()
        return value


class DeviceRevokeResponse(BaseModel):
    """Single-device revocation result (all sessions are force-expired)."""

    revoked: bool
    new_session_version: int


class DevicesRevokeAllResponse(BaseModel):
    """Bulk revocation result: number of removed device records."""

    revoked: int
