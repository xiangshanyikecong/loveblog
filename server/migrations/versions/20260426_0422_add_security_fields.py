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

"""Add security enhancement fields

Revision ID: 20260426_0422
Revises: 20260426_0415_add_visitor_fields_to_user
Create Date: 2026-04-26 04:22:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "20260426_0422"
down_revision = "202604260415"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 登录安全相关字段
    op.add_column(
        "users",
        sa.Column("login_failed_count", sa.Integer, default=0, nullable=False, comment="连续登录失败次数")
    )
    op.add_column(
        "users",
        sa.Column("login_freeze_until", sa.DateTime(timezone=True), nullable=True, comment="账户冻结截止时间")
    )
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True, comment="最后修改密码时间")
    )
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer, default=1, nullable=False, comment="会话版本号，用于控制多设备登录")
    )
    op.add_column(
        "users",
        sa.Column("last_login_ip", sa.String(64), nullable=True, comment="最后登录IP")
    )


def downgrade() -> None:
    op.drop_column("users", "last_login_ip")
    op.drop_column("users", "session_version")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "login_freeze_until")
    op.drop_column("users", "login_failed_count")
