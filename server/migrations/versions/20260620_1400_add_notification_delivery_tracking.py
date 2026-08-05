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

"""add notification delivery tracking

Revision ID: 20260620_1400
Revises: 20260620_1300
Create Date: 2026-06-20 16:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260620_1400"
down_revision = "20260620_1300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = {column["name"] for column in insp.get_columns("notifications")}
    indexes = {index["name"] for index in insp.get_indexes("notifications")}

    if "delivery_status" not in columns:
        op.add_column(
            "notifications",
            sa.Column(
                "delivery_status",
                sa.String(length=24),
                nullable=False,
                server_default="not_queued",
            ),
        )
    if "delivery_attempts" not in columns:
        op.add_column(
            "notifications",
            sa.Column(
                "delivery_attempts",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
    if "delivery_last_error" not in columns:
        op.add_column("notifications", sa.Column("delivery_last_error", sa.Text(), nullable=True))
    if "delivery_last_attempt_at" not in columns:
        op.add_column(
            "notifications",
            sa.Column("delivery_last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "delivery_completed_at" not in columns:
        op.add_column(
            "notifications",
            sa.Column("delivery_completed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "ix_notifications_delivery_status" not in indexes:
        op.create_index(
            op.f("ix_notifications_delivery_status"),
            "notifications",
            ["delivery_status"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = {column["name"] for column in insp.get_columns("notifications")}
    indexes = {index["name"] for index in insp.get_indexes("notifications")}

    if "ix_notifications_delivery_status" in indexes:
        op.drop_index(op.f("ix_notifications_delivery_status"), table_name="notifications")
    if "delivery_completed_at" in columns:
        op.drop_column("notifications", "delivery_completed_at")
    if "delivery_last_attempt_at" in columns:
        op.drop_column("notifications", "delivery_last_attempt_at")
    if "delivery_last_error" in columns:
        op.drop_column("notifications", "delivery_last_error")
    if "delivery_attempts" in columns:
        op.drop_column("notifications", "delivery_attempts")
    if "delivery_status" in columns:
        op.drop_column("notifications", "delivery_status")
