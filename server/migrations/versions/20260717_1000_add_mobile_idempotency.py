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

"""add mobile outbox idempotency keys

Revision ID: 20260717_1000
Revises: 20260705_1000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260717_1000"
down_revision = "20260705_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table recreates the table on SQLite and emits normal ALTER
    # statements on PostgreSQL, keeping this startup migration portable.
    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(
            sa.Column("client_idempotency_key", sa.String(length=128), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_message_author_idempotency",
            ["author_id", "client_idempotency_key"],
        )
    op.create_table(
        "mood_idempotency_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("mood_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["mood_id"], ["mood_checkins.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_mood_user_idempotency"),
    )
    op.create_index(op.f("ix_mood_idempotency_records_id"), "mood_idempotency_records", ["id"], unique=False)
    op.create_index(op.f("ix_mood_idempotency_records_user_id"), "mood_idempotency_records", ["user_id"], unique=False)
    op.create_index(op.f("ix_mood_idempotency_records_mood_id"), "mood_idempotency_records", ["mood_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mood_idempotency_records_mood_id"), table_name="mood_idempotency_records")
    op.drop_index(op.f("ix_mood_idempotency_records_user_id"), table_name="mood_idempotency_records")
    op.drop_index(op.f("ix_mood_idempotency_records_id"), table_name="mood_idempotency_records")
    op.drop_table("mood_idempotency_records")
    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_constraint("uq_message_author_idempotency", type_="unique")
        batch_op.drop_column("client_idempotency_key")
