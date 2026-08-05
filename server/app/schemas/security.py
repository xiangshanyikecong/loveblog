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


class SecurityProfile(BaseModel):
    """账号安全信息"""
    model_config = ConfigDict(from_attributes=True)

    uid: str
    username: str
    nickname: str
    role: str
    login_failed_count: int
    login_freeze_until: datetime | None
    password_changed_at: datetime | None
    session_version: int
    last_login_ip: str | None
    last_login_at: datetime | None


class SecurityListResponse(BaseModel):
    """安全信息列表响应"""
    items: list[SecurityProfile]
    total: int


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    model_config = ConfigDict(extra="forbid")

    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("Password must contain both letters and numbers")
        if value != value.strip():
            raise ValueError("Password cannot start or end with spaces")
        return value


class ResetPasswordRequest(BaseModel):
    """重置密码请求（管理员操作）"""
    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("Password must contain both letters and numbers")
        return value


class RevokeSessionsRequest(BaseModel):
    """撤销所有会话请求"""
    model_config = ConfigDict(extra="forbid")

    confirm: bool = Field(default=False)


class UnlockAccountRequest(BaseModel):
    """解锁账户请求"""
    model_config = ConfigDict(extra="forbid")

    confirm: bool = Field(default=False)


class SecurityStats(BaseModel):
    """安全统计"""
    total_users: int
    frozen_users: int
    failed_login_today: int
    active_sessions: int
