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

"""add performance indexes for chat queries

Revision ID: 20260719_1000
Revises: 20260718_1600
"""
from alembic import op


revision = "20260719_1000"
down_revision = "20260718_1600"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_chat_messages_read_at", "chat_messages", ["read_at"])
    op.create_index("ix_chat_messages_deleted_at", "chat_messages", ["deleted_at"])
    op.create_index(
        "ix_chat_message_favorites_created_at",
        "chat_message_favorites",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_message_favorites_created_at", table_name="chat_message_favorites")
    op.drop_index("ix_chat_messages_deleted_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_read_at", table_name="chat_messages")
