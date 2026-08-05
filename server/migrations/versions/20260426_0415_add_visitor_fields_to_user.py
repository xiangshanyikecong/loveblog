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

"""Add visitor management fields to users table

Revision ID: 202604260415
Revises: 20260425_1300_add_content_tags
Create Date: 2026-04-26 04:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "202604260415"
down_revision = "20260425_1300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加访客相关字段
    op.add_column(
        "users",
        sa.Column("sso_source", sa.String(64), nullable=True, comment="SSO来源，如 hub/center 等")
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True, comment="最近登录时间")
    )
    op.add_column(
        "users",
        sa.Column("is_banned", sa.Boolean, default=False, nullable=False, comment="是否被封禁")
    )
    op.add_column(
        "users",
        sa.Column("remark", sa.Text, nullable=True, comment="管理员备注")
    )
    op.add_column(
        "users",
        sa.Column("permission_status", sa.String(32), default="active", nullable=False, comment="权限状态: active/limited/banned")
    )
    op.add_column(
        "users",
        sa.Column("avatar_sync_record", sa.Text, nullable=True, comment="头像/昵称同步记录JSON")
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_sync_record")
    op.drop_column("users", "permission_status")
    op.drop_column("users", "remark")
    op.drop_column("users", "is_banned")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "sso_source")
