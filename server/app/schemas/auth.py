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
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole


_USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,32}$")


def _normalize_username(value: str, *, error_message: str) -> str:
    normalized = value.strip().lower()
    if not _USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError(error_message)
    return normalized


def _validate_password_strength(value: str) -> str:
    if value != value.strip():
        raise ValueError("Password cannot start or end with spaces")
    if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
        raise ValueError("Password must contain both letters and numbers")
    return value


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=50)
    role: UserRole = UserRole.partner_a

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _normalize_username(
            value,
            error_message="Username must be 3-32 chars with lowercase letters, numbers, or underscore",
        )

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_strength(value)

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Nickname cannot be blank")
        return normalized


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=128)
    # Optional second factor. If the account has 2FA enabled and this field is
    # absent, login returns 401 with detail "totp_required" so the client can
    # prompt for the code; the value may be a 6-digit TOTP code or a recovery
    # code of the form "xxxx-xxxx".
    totp_code: str | None = Field(default=None, min_length=1, max_length=16)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _normalize_username(value, error_message="Invalid username")


class PasswordRecoveryRequest(BaseModel):
    """Unauthenticated password reset, authorized by the instance bootstrap token."""

    username: str = Field(min_length=3, max_length=32)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _normalize_username(value, error_message="Invalid username")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str | None = None


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    username: str
    nickname: str
    avatar: str | None
    role: UserRole


class UpdatePartnerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(default=None, min_length=3, max_length=32)
    nickname: str | None = Field(default=None, min_length=1, max_length=50)
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_username(
            value,
            error_message="Username must be 3-32 chars with lowercase letters, numbers, or underscore",
        )

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Nickname cannot be blank")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_password_strength(value)


class PartnerRegisterRequest(RegisterRequest):
    role: UserRole = UserRole.partner_a

    @field_validator("role")
    @classmethod
    def validate_partner_role(cls, value: UserRole) -> UserRole:
        if value not in {UserRole.partner_a, UserRole.partner_b}:
            raise ValueError("Only partner roles are supported")
        return value


class BootstrapRegisterRequest(PartnerRegisterRequest):
    site_name: str = Field(default="恋爱记", max_length=120)
    love_start_date: datetime | None = None

    @field_validator("site_name")
    @classmethod
    def validate_site_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Site name cannot be blank")
        return normalized


class BootstrapStatusResponse(BaseModel):
    bootstrapped: bool


class PartnerListResponse(BaseModel):
    items: list[UserProfile]


class VisitorProfile(BaseModel):
    """访客账号详情"""
    model_config = ConfigDict(from_attributes=True)

    uid: str
    username: str
    nickname: str
    avatar: str | None
    role: UserRole
    sso_source: str | None
    last_login_at: datetime | None
    is_banned: bool
    remark: str | None
    permission_status: str
    avatar_sync_record: str | None
    created_at: datetime
    updated_at: datetime


class VisitorListResponse(BaseModel):
    """访客列表响应"""
    items: list[VisitorProfile]
    total: int
    page: int
    page_size: int


class UpdateVisitorRequest(BaseModel):
    """更新访客信息请求"""
    model_config = ConfigDict(extra="forbid")

    nickname: str | None = Field(default=None, min_length=1, max_length=50)
    is_banned: bool | None = None
    remark: str | None = Field(default=None, max_length=500)
    permission_status: str | None = Field(default=None, pattern="^(active|limited|banned)$")

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Nickname cannot be blank")
        return normalized

    @field_validator("remark")
    @classmethod
    def validate_remark(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() if value.strip() else None
