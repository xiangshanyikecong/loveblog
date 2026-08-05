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

"""add canvas artwork gallery

Revision ID: 20260718_1300
Revises: 20260718_1200
"""
from alembic import op
import sqlalchemy as sa


revision = "20260718_1300"
down_revision = "20260718_1200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canvas_artworks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("caid", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column("strokes_json", sa.Text(), nullable=False),
        sa.Column("thumb_data_url", sa.Text(), nullable=False),
        sa.Column("stroke_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("width", sa.Integer(), nullable=False, server_default="960"),
        sa.Column("height", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("caid", name="uq_canvas_artwork_caid"),
    )
    op.create_index(op.f("ix_canvas_artworks_id"), "canvas_artworks", ["id"], unique=False)
    op.create_index(op.f("ix_canvas_artworks_author_id"), "canvas_artworks", ["author_id"], unique=False)
    op.create_index(op.f("ix_canvas_artworks_created_at"), "canvas_artworks", ["created_at"], unique=False)

    op.create_table(
        "canvas_artwork_collaborators",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("artwork_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("stroke_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["artwork_id"], ["canvas_artworks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artwork_id", "user_id", name="uq_canvas_artwork_user"),
    )
    op.create_index(op.f("ix_canvas_artwork_collaborators_id"), "canvas_artwork_collaborators", ["id"], unique=False)
    op.create_index(op.f("ix_canvas_artwork_collaborators_artwork_id"), "canvas_artwork_collaborators", ["artwork_id"], unique=False)
    op.create_index(op.f("ix_canvas_artwork_collaborators_user_id"), "canvas_artwork_collaborators", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_canvas_artwork_collaborators_user_id"), table_name="canvas_artwork_collaborators")
    op.drop_index(op.f("ix_canvas_artwork_collaborators_artwork_id"), table_name="canvas_artwork_collaborators")
    op.drop_index(op.f("ix_canvas_artwork_collaborators_id"), table_name="canvas_artwork_collaborators")
    op.drop_table("canvas_artwork_collaborators")
    op.drop_index(op.f("ix_canvas_artworks_created_at"), table_name="canvas_artworks")
    op.drop_index(op.f("ix_canvas_artworks_author_id"), table_name="canvas_artworks")
    op.drop_index(op.f("ix_canvas_artworks_id"), table_name="canvas_artworks")
    op.drop_table("canvas_artworks")
