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

"""add watch_sources table (cottage 一起看 / watch together)

Revision ID: 20260613_1100
Revises: 20260613_1000
Create Date: 2026-06-13 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260613_1100"
down_revision = "20260613_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watch_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wsid", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("poster_url", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
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
    op.create_index(op.f("ix_watch_sources_id"), "watch_sources", ["id"], unique=False)
    op.create_index(op.f("ix_watch_sources_wsid"), "watch_sources", ["wsid"], unique=True)
    op.create_index(op.f("ix_watch_sources_author_id"), "watch_sources", ["author_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_watch_sources_author_id"), table_name="watch_sources")
    op.drop_index(op.f("ix_watch_sources_wsid"), table_name="watch_sources")
    op.drop_index(op.f("ix_watch_sources_id"), table_name="watch_sources")
    op.drop_table("watch_sources")
