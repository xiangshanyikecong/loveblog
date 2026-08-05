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

"""add wishes table (cottage wishlist)

Revision ID: 20260613_1000
Revises: 20260524_0900
Create Date: 2026-06-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260613_1000"
down_revision = "20260524_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wishes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wid", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["completed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wishes_id"), "wishes", ["id"], unique=False)
    op.create_index(op.f("ix_wishes_wid"), "wishes", ["wid"], unique=True)
    op.create_index(op.f("ix_wishes_author_id"), "wishes", ["author_id"], unique=False)
    op.create_index(op.f("ix_wishes_completed_by_id"), "wishes", ["completed_by_id"], unique=False)
    op.create_index(op.f("ix_wishes_status"), "wishes", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_wishes_status"), table_name="wishes")
    op.drop_index(op.f("ix_wishes_completed_by_id"), table_name="wishes")
    op.drop_index(op.f("ix_wishes_author_id"), table_name="wishes")
    op.drop_index(op.f("ix_wishes_wid"), table_name="wishes")
    op.drop_index(op.f("ix_wishes_id"), table_name="wishes")
    op.drop_table("wishes")
