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

"""add coupons, ledger_entries and period_cycles tables

Revision ID: 20260620_1200
Revises: 20260620_1100
Create Date: 2026-06-20 12:00:00.000000

Adds three new cottage modules:
- coupons        — 甜蜜兑换券 (love coupons)
- ledger_entries — 情侣账本 / AA 记账 (shared ledger)
- period_cycles  — 生理期记录与关怀提醒 (period tracker)

(恋爱足迹地图 needs no table — it aggregates the existing checkins.location_text.)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260620_1200"
down_revision = "20260620_1100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── coupons ────────────────────────────────────────────────────────────
    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cpid", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_by_id", sa.Integer(), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["redeemed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coupons_id"), "coupons", ["id"], unique=False)
    op.create_index(op.f("ix_coupons_cpid"), "coupons", ["cpid"], unique=True)
    op.create_index(op.f("ix_coupons_author_id"), "coupons", ["author_id"], unique=False)
    op.create_index(op.f("ix_coupons_redeemed_by_id"), "coupons", ["redeemed_by_id"], unique=False)
    op.create_index(op.f("ix_coupons_status"), "coupons", ["status"], unique=False)

    # ── ledger_entries ─────────────────────────────────────────────────────
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("leid", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("split_type", sa.String(length=16), nullable=False, server_default=sa.text("'aa'")),
        sa.Column("spent_on", sa.Date(), nullable=False),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ledger_entries_id"), "ledger_entries", ["id"], unique=False)
    op.create_index(op.f("ix_ledger_entries_leid"), "ledger_entries", ["leid"], unique=True)
    op.create_index(op.f("ix_ledger_entries_author_id"), "ledger_entries", ["author_id"], unique=False)
    op.create_index(op.f("ix_ledger_entries_payer_id"), "ledger_entries", ["payer_id"], unique=False)
    op.create_index(op.f("ix_ledger_entries_spent_on"), "ledger_entries", ["spent_on"], unique=False)

    # ── period_cycles ──────────────────────────────────────────────────────
    op.create_table(
        "period_cycles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pcid", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("author_id", "start_date", name="uq_period_author_start"),
    )
    op.create_index(op.f("ix_period_cycles_id"), "period_cycles", ["id"], unique=False)
    op.create_index(op.f("ix_period_cycles_pcid"), "period_cycles", ["pcid"], unique=True)
    op.create_index(op.f("ix_period_cycles_author_id"), "period_cycles", ["author_id"], unique=False)
    op.create_index(op.f("ix_period_cycles_start_date"), "period_cycles", ["start_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_period_cycles_start_date"), table_name="period_cycles")
    op.drop_index(op.f("ix_period_cycles_author_id"), table_name="period_cycles")
    op.drop_index(op.f("ix_period_cycles_pcid"), table_name="period_cycles")
    op.drop_index(op.f("ix_period_cycles_id"), table_name="period_cycles")
    op.drop_table("period_cycles")

    op.drop_index(op.f("ix_ledger_entries_spent_on"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_payer_id"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_author_id"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_leid"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_id"), table_name="ledger_entries")
    op.drop_table("ledger_entries")

    op.drop_index(op.f("ix_coupons_status"), table_name="coupons")
    op.drop_index(op.f("ix_coupons_redeemed_by_id"), table_name="coupons")
    op.drop_index(op.f("ix_coupons_author_id"), table_name="coupons")
    op.drop_index(op.f("ix_coupons_cpid"), table_name="coupons")
    op.drop_index(op.f("ix_coupons_id"), table_name="coupons")
    op.drop_table("coupons")
