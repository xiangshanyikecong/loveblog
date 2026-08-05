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

"""密码验证相关的Schema"""
from pydantic import BaseModel, Field


class PasswordVerifyRequest(BaseModel):
    """密码验证请求"""
    password: str = Field(min_length=1, max_length=100, description="访问密码")


class PasswordVerifyResponse(BaseModel):
    """密码验证响应"""
    verified: bool = Field(description="是否验证成功")
    access_token: str | None = Field(default=None, description="访问令牌，用于后续请求")
