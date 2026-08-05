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

"""add cottage plans and reminders

Revision ID: 20260619_1000
Revises: 20260619_0900
Create Date: 2026-06-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "20260619_1000"
down_revision = "20260619_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cottage_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pid", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("plan_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'planned'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["completed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cottage_plans_id"), "cottage_plans", ["id"], unique=False)
    op.create_index(op.f("ix_cottage_plans_pid"), "cottage_plans", ["pid"], unique=True)
    op.create_index(op.f("ix_cottage_plans_author_id"), "cottage_plans", ["author_id"], unique=False)
    op.create_index(op.f("ix_cottage_plans_plan_date"), "cottage_plans", ["plan_date"], unique=False)
    op.create_index(op.f("ix_cottage_plans_status"), "cottage_plans", ["status"], unique=False)
    op.create_index(op.f("ix_cottage_plans_completed_by_id"), "cottage_plans", ["completed_by_id"], unique=False)

    op.create_table(
        "cottage_reminders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rid", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audience", sa.String(length=16), nullable=False, server_default=sa.text("'both'")),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_by_id", sa.Integer(), nullable=True),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["done_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cottage_reminders_id"), "cottage_reminders", ["id"], unique=False)
    op.create_index(op.f("ix_cottage_reminders_rid"), "cottage_reminders", ["rid"], unique=True)
    op.create_index(op.f("ix_cottage_reminders_author_id"), "cottage_reminders", ["author_id"], unique=False)
    op.create_index(op.f("ix_cottage_reminders_remind_at"), "cottage_reminders", ["remind_at"], unique=False)
    op.create_index(op.f("ix_cottage_reminders_audience"), "cottage_reminders", ["audience"], unique=False)
    op.create_index(op.f("ix_cottage_reminders_is_done"), "cottage_reminders", ["is_done"], unique=False)
    op.create_index(op.f("ix_cottage_reminders_done_by_id"), "cottage_reminders", ["done_by_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cottage_reminders_done_by_id"), table_name="cottage_reminders")
    op.drop_index(op.f("ix_cottage_reminders_is_done"), table_name="cottage_reminders")
    op.drop_index(op.f("ix_cottage_reminders_audience"), table_name="cottage_reminders")
    op.drop_index(op.f("ix_cottage_reminders_remind_at"), table_name="cottage_reminders")
    op.drop_index(op.f("ix_cottage_reminders_author_id"), table_name="cottage_reminders")
    op.drop_index(op.f("ix_cottage_reminders_rid"), table_name="cottage_reminders")
    op.drop_index(op.f("ix_cottage_reminders_id"), table_name="cottage_reminders")
    op.drop_table("cottage_reminders")

    op.drop_index(op.f("ix_cottage_plans_completed_by_id"), table_name="cottage_plans")
    op.drop_index(op.f("ix_cottage_plans_status"), table_name="cottage_plans")
    op.drop_index(op.f("ix_cottage_plans_plan_date"), table_name="cottage_plans")
    op.drop_index(op.f("ix_cottage_plans_author_id"), table_name="cottage_plans")
    op.drop_index(op.f("ix_cottage_plans_pid"), table_name="cottage_plans")
    op.drop_index(op.f("ix_cottage_plans_id"), table_name="cottage_plans")
    op.drop_table("cottage_plans")
