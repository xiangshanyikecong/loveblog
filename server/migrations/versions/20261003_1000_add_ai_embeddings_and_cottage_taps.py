# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""add ai article embeddings and cottage taps

Revision ID: 20261003_1000
Revises: 20260912_1300
"""
from alembic import op
import sqlalchemy as sa


revision = "20261003_1000"
down_revision = "20260912_1300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "article_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("vector_json", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "model", name="uq_article_embedding_article_model"),
    )
    op.create_index(op.f("ix_article_embeddings_id"), "article_embeddings", ["id"], unique=False)
    op.create_index(op.f("ix_article_embeddings_article_id"), "article_embeddings", ["article_id"], unique=False)

    op.create_table(
        "cottage_taps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tid", sa.String(length=36), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="tap"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tid", name="uq_cottage_tap_tid"),
    )
    op.create_index(op.f("ix_cottage_taps_id"), "cottage_taps", ["id"], unique=False)
    op.create_index(op.f("ix_cottage_taps_sender_id"), "cottage_taps", ["sender_id"], unique=False)
    op.create_index(op.f("ix_cottage_taps_recipient_id"), "cottage_taps", ["recipient_id"], unique=False)
    op.create_index(op.f("ix_cottage_taps_created_at"), "cottage_taps", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cottage_taps_created_at"), table_name="cottage_taps")
    op.drop_index(op.f("ix_cottage_taps_recipient_id"), table_name="cottage_taps")
    op.drop_index(op.f("ix_cottage_taps_sender_id"), table_name="cottage_taps")
    op.drop_index(op.f("ix_cottage_taps_id"), table_name="cottage_taps")
    op.drop_table("cottage_taps")
    op.drop_index(op.f("ix_article_embeddings_article_id"), table_name="article_embeddings")
    op.drop_index(op.f("ix_article_embeddings_id"), table_name="article_embeddings")
    op.drop_table("article_embeddings")
