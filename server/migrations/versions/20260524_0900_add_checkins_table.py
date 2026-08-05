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

"""add checkins table

Revision ID: 20260524_0900
Revises: 20260503_1000
Create Date: 2026-05-24 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260524_0900"
down_revision = "20260503_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cid", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("media_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("location_status", sa.String(length=32), nullable=False),
        sa.Column("location_provider", sa.String(length=32), nullable=True),
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
    )
    op.create_index(op.f("ix_checkins_id"), "checkins", ["id"], unique=False)
    op.create_index(op.f("ix_checkins_cid"), "checkins", ["cid"], unique=True)
    op.create_index(op.f("ix_checkins_author_id"), "checkins", ["author_id"], unique=False)
    # Composite index for "Counterpart latest" and "Counterpart history page"
    # query patterns: filter by author_id, ordered by created_at DESC, with
    # deleted_at as a final tiebreaker / soft-delete filter helper.
    op.create_index(
        "ix_checkins_author_created",
        "checkins",
        ["author_id", sa.text("created_at DESC"), "deleted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_checkins_author_created", table_name="checkins")
    op.drop_index(op.f("ix_checkins_author_id"), table_name="checkins")
    op.drop_index(op.f("ix_checkins_cid"), table_name="checkins")
    op.drop_index(op.f("ix_checkins_id"), table_name="checkins")
    op.drop_table("checkins")
