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

"""add web push subscriptions

Revision ID: 20260620_1300
Revises: 20260620_1230
Create Date: 2026-06-20 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260620_1300"
down_revision = "20260620_1230"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())

    if "push_subscriptions" not in existing:
        op.create_table(
            "push_subscriptions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("sid", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("endpoint", sa.Text(), nullable=False),
            sa.Column("p256dh", sa.String(length=512), nullable=False),
            sa.Column("auth", sa.String(length=255), nullable=False),
            sa.Column("expiration_time", sa.Integer(), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
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
            sa.UniqueConstraint("endpoint"),
            sa.UniqueConstraint("sid"),
        )
        op.create_index(op.f("ix_push_subscriptions_id"), "push_subscriptions", ["id"], unique=False)
        op.create_index(op.f("ix_push_subscriptions_sid"), "push_subscriptions", ["sid"], unique=False)
        op.create_index(op.f("ix_push_subscriptions_user_id"), "push_subscriptions", ["user_id"], unique=False)
        op.create_index(
            op.f("ix_push_subscriptions_is_active"),
            "push_subscriptions",
            ["is_active"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_push_subscriptions_is_active"), table_name="push_subscriptions")
    op.drop_index(op.f("ix_push_subscriptions_user_id"), table_name="push_subscriptions")
    op.drop_index(op.f("ix_push_subscriptions_sid"), table_name="push_subscriptions")
    op.drop_index(op.f("ix_push_subscriptions_id"), table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
