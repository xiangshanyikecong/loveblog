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

"""add chat enhancement tables and future message fields

Revision ID: 20260620_1500
Revises: 20260620_1400
Create Date: 2026-06-20 17:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260620_1500"
down_revision = "20260620_1400"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = {column["name"] for column in insp.get_columns("chat_messages")}
    indexes = {index["name"] for index in insp.get_indexes("chat_messages")}
    tables = set(insp.get_table_names())

    if "visible_at" not in columns:
        op.add_column("chat_messages", sa.Column("visible_at", sa.DateTime(timezone=True), nullable=True))
        op.execute("UPDATE chat_messages SET visible_at = created_at WHERE visible_at IS NULL")
        op.alter_column("chat_messages", "visible_at", nullable=False)
    if "released_at" not in columns:
        op.add_column("chat_messages", sa.Column("released_at", sa.DateTime(timezone=True), nullable=True))
        op.execute("UPDATE chat_messages SET released_at = created_at WHERE released_at IS NULL")
    if "ix_chat_messages_visible_at" not in indexes:
        op.create_index(op.f("ix_chat_messages_visible_at"), "chat_messages", ["visible_at"], unique=False)
    if "ix_chat_messages_released_at" not in indexes:
        op.create_index(op.f("ix_chat_messages_released_at"), "chat_messages", ["released_at"], unique=False)

    if "chat_message_favorites" not in tables:
        op.create_table(
            "chat_message_favorites",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("message_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "message_id", name="uq_chat_message_favorites_user_message"),
        )
        op.create_index(op.f("ix_chat_message_favorites_id"), "chat_message_favorites", ["id"], unique=False)
        op.create_index(op.f("ix_chat_message_favorites_user_id"), "chat_message_favorites", ["user_id"], unique=False)
        op.create_index(
            op.f("ix_chat_message_favorites_message_id"),
            "chat_message_favorites",
            ["message_id"],
            unique=False,
        )

    if "chat_pinned_quotes" not in tables:
        op.create_table(
            "chat_pinned_quotes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("message_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_chat_pinned_quotes_user"),
        )
        op.create_index(op.f("ix_chat_pinned_quotes_id"), "chat_pinned_quotes", ["id"], unique=False)
        op.create_index(op.f("ix_chat_pinned_quotes_user_id"), "chat_pinned_quotes", ["user_id"], unique=False)
        op.create_index(op.f("ix_chat_pinned_quotes_message_id"), "chat_pinned_quotes", ["message_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = {column["name"] for column in insp.get_columns("chat_messages")}
    indexes = {index["name"] for index in insp.get_indexes("chat_messages")}
    tables = set(insp.get_table_names())

    if "chat_pinned_quotes" in tables:
        op.drop_index(op.f("ix_chat_pinned_quotes_message_id"), table_name="chat_pinned_quotes")
        op.drop_index(op.f("ix_chat_pinned_quotes_user_id"), table_name="chat_pinned_quotes")
        op.drop_index(op.f("ix_chat_pinned_quotes_id"), table_name="chat_pinned_quotes")
        op.drop_table("chat_pinned_quotes")

    if "chat_message_favorites" in tables:
        op.drop_index(op.f("ix_chat_message_favorites_message_id"), table_name="chat_message_favorites")
        op.drop_index(op.f("ix_chat_message_favorites_user_id"), table_name="chat_message_favorites")
        op.drop_index(op.f("ix_chat_message_favorites_id"), table_name="chat_message_favorites")
        op.drop_table("chat_message_favorites")

    if "ix_chat_messages_released_at" in indexes:
        op.drop_index(op.f("ix_chat_messages_released_at"), table_name="chat_messages")
    if "ix_chat_messages_visible_at" in indexes:
        op.drop_index(op.f("ix_chat_messages_visible_at"), table_name="chat_messages")
    if "released_at" in columns:
        op.drop_column("chat_messages", "released_at")
    if "visible_at" in columns:
        op.drop_column("chat_messages", "visible_at")
