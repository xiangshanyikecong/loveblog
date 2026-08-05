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

"""add cottage chat_messages + mood_checkins tables

Revision ID: 20260613_1200
Revises: 20260613_1100
Create Date: 2026-06-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260613_1200"
down_revision = "20260613_1100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mid", sa.String(length=36), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False, server_default=sa.text("'text'")),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("media_url", sa.Text(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_messages_id"), "chat_messages", ["id"], unique=False)
    op.create_index(op.f("ix_chat_messages_mid"), "chat_messages", ["mid"], unique=True)
    op.create_index(op.f("ix_chat_messages_sender_id"), "chat_messages", ["sender_id"], unique=False)
    op.create_index(op.f("ix_chat_messages_created_at"), "chat_messages", ["created_at"], unique=False)

    op.create_table(
        "mood_checkins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mid", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("mood_date", sa.Date(), nullable=False),
        sa.Column("mood", sa.String(length=32), nullable=False),
        sa.Column("emoji", sa.String(length=16), nullable=True),
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
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("author_id", "mood_date", name="uq_mood_author_date"),
    )
    op.create_index(op.f("ix_mood_checkins_id"), "mood_checkins", ["id"], unique=False)
    op.create_index(op.f("ix_mood_checkins_mid"), "mood_checkins", ["mid"], unique=True)
    op.create_index(op.f("ix_mood_checkins_author_id"), "mood_checkins", ["author_id"], unique=False)
    op.create_index(op.f("ix_mood_checkins_mood_date"), "mood_checkins", ["mood_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mood_checkins_mood_date"), table_name="mood_checkins")
    op.drop_index(op.f("ix_mood_checkins_author_id"), table_name="mood_checkins")
    op.drop_index(op.f("ix_mood_checkins_mid"), table_name="mood_checkins")
    op.drop_index(op.f("ix_mood_checkins_id"), table_name="mood_checkins")
    op.drop_table("mood_checkins")

    op.drop_index(op.f("ix_chat_messages_created_at"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_sender_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_mid"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
