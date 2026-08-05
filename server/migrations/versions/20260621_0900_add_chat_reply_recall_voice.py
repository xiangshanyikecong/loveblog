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

"""add chat reply, recall and voice metadata

Revision ID: 20260621_0900
Revises: 20260620_1500
Create Date: 2026-06-21 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260621_0900"
down_revision = "20260620_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = {column["name"] for column in insp.get_columns("chat_messages")}
    indexes = {index["name"] for index in insp.get_indexes("chat_messages")}

    if "audio_duration_sec" not in columns:
        op.add_column("chat_messages", sa.Column("audio_duration_sec", sa.Integer(), nullable=True))
    if "reply_to_message_id" not in columns:
        op.add_column("chat_messages", sa.Column("reply_to_message_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_chat_messages_reply_to_message_id",
            "chat_messages",
            "chat_messages",
            ["reply_to_message_id"],
            ["id"],
        )
    if "recalled_at" not in columns:
        op.add_column("chat_messages", sa.Column("recalled_at", sa.DateTime(timezone=True), nullable=True))
    if "ix_chat_messages_reply_to_message_id" not in indexes:
        op.create_index(
            op.f("ix_chat_messages_reply_to_message_id"),
            "chat_messages",
            ["reply_to_message_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = {column["name"] for column in insp.get_columns("chat_messages")}
    indexes = {index["name"] for index in insp.get_indexes("chat_messages")}
    foreign_keys = {fk["name"] for fk in insp.get_foreign_keys("chat_messages")}

    if "ix_chat_messages_reply_to_message_id" in indexes:
        op.drop_index(op.f("ix_chat_messages_reply_to_message_id"), table_name="chat_messages")
    if "fk_chat_messages_reply_to_message_id" in foreign_keys:
        op.drop_constraint("fk_chat_messages_reply_to_message_id", "chat_messages", type_="foreignkey")
    if "recalled_at" in columns:
        op.drop_column("chat_messages", "recalled_at")
    if "reply_to_message_id" in columns:
        op.drop_column("chat_messages", "reply_to_message_id")
    if "audio_duration_sec" in columns:
        op.drop_column("chat_messages", "audio_duration_sec")
