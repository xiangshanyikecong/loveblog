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

"""add health_snapshots table for trend / alert / auto-remediation

Revision ID: 20260718_1600
Revises: 20260718_1500
"""
from alembic import op
import sqlalchemy as sa


revision = "20260718_1600"
down_revision = "20260718_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "health_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("overall_status", sa.String(length=16), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("checks_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "remediated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("remediation_note", sa.String(length=500), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_health_snapshots_id"), "health_snapshots", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_health_snapshots_overall_status"),
        "health_snapshots",
        ["overall_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_health_snapshots_created_at"),
        "health_snapshots",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_health_snapshots_created_at"), table_name="health_snapshots")
    op.drop_index(op.f("ix_health_snapshots_overall_status"), table_name="health_snapshots")
    op.drop_index(op.f("ix_health_snapshots_id"), table_name="health_snapshots")
    op.drop_table("health_snapshots")
