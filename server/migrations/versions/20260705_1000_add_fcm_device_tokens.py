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

"""add fcm device tokens

Revision ID: 20260705_1000
Revises: 20260626_1300
Create Date: 2026-07-05 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260705_1000"
down_revision = "20260626_1300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())

    if "fcm_device_tokens" not in existing:
        op.create_table(
            "fcm_device_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tid", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token", sa.Text(), nullable=False),
            sa.Column("platform", sa.String(length=32), nullable=False, server_default="android"),
            sa.Column("device_name", sa.String(length=255), nullable=True),
            sa.Column("app_version", sa.String(length=64), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("fail_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tid"),
            sa.UniqueConstraint("token"),
        )
        op.create_index(op.f("ix_fcm_device_tokens_id"), "fcm_device_tokens", ["id"], unique=False)
        op.create_index(op.f("ix_fcm_device_tokens_tid"), "fcm_device_tokens", ["tid"], unique=False)
        op.create_index(op.f("ix_fcm_device_tokens_user_id"), "fcm_device_tokens", ["user_id"], unique=False)
        op.create_index(op.f("ix_fcm_device_tokens_platform"), "fcm_device_tokens", ["platform"], unique=False)
        op.create_index(op.f("ix_fcm_device_tokens_is_active"), "fcm_device_tokens", ["is_active"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "fcm_device_tokens" not in set(insp.get_table_names()):
        return

    indexes = {index["name"] for index in insp.get_indexes("fcm_device_tokens")}
    for index_name in (
        op.f("ix_fcm_device_tokens_is_active"),
        op.f("ix_fcm_device_tokens_platform"),
        op.f("ix_fcm_device_tokens_user_id"),
        op.f("ix_fcm_device_tokens_tid"),
        op.f("ix_fcm_device_tokens_id"),
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="fcm_device_tokens")
    op.drop_table("fcm_device_tokens")
