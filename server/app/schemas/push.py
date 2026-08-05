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


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=512)
    auth: str = Field(min_length=1, max_length=255)


class PushSubscriptionUpsertRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=4096)
    expiration_time: int | None = None
    keys: PushSubscriptionKeys
    user_agent: str | None = Field(default=None, max_length=512)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Endpoint cannot be blank")
        return normalized

    @field_validator("user_agent")
    @classmethod
    def validate_user_agent(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class PushSubscriptionDeleteRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=4096)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Endpoint cannot be blank")
        return normalized


class PushPublicKeyResponse(BaseModel):
    enabled: bool
    public_key: str | None


class PushSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sid: str
    endpoint: str
    is_active: bool
    fail_count: int
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class PushSubscriptionListResponse(BaseModel):
    items: list[PushSubscriptionResponse]


class FcmTokenUpsertRequest(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    platform: str = Field(default="android", min_length=1, max_length=32)
    device_name: str | None = Field(default=None, max_length=255)
    app_version: str | None = Field(default=None, max_length=64)

    @field_validator("token", "platform")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value cannot be blank")
        return normalized

    @field_validator("device_name", "app_version")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class FcmTokenDeleteRequest(BaseModel):
    token: str = Field(min_length=1, max_length=4096)

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Token cannot be blank")
        return normalized


class FcmTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tid: str
    platform: str
    device_name: str | None
    app_version: str | None
    is_active: bool
    fail_count: int
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class FcmTokenListResponse(BaseModel):
    items: list[FcmTokenResponse]
