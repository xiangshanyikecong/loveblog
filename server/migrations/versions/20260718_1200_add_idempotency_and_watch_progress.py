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

"""add idempotency keys to chat/moments/checkins/wishes + watch progress fields

Revision ID: 20260718_1200
Revises: 20260717_1000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260718_1200"
down_revision = "20260717_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotency-Key columns on the four create-endpoint tables that the
    # Android offline SyncEngine writes to. Each one is paired with a unique
    # (author_id, client_idempotency_key) constraint so a retried POST that
    # lands twice on the server (after a 2xx lost in transit) returns the
    # original row instead of duplicating it.
    for table_name, constraint_name in [
        ("chat_messages", "uq_chat_message_sender_idempotency"),
        ("moments", "uq_moment_author_idempotency"),
        ("checkins", "uq_checkin_author_idempotency"),
        ("wishes", "uq_wish_author_idempotency"),
    ]:
        author_col = "sender_id" if table_name == "chat_messages" else "author_id"
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(
                sa.Column("client_idempotency_key", sa.String(length=128), nullable=True)
            )
            batch_op.create_unique_constraint(
                constraint_name,
                [author_col, "client_idempotency_key"],
            )

    # Watch-together progress / bookmarks.
    with op.batch_alter_table("watch_sources") as batch_op:
        batch_op.add_column(
            sa.Column("last_position_ms", sa.BigInteger(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("bookmarks_json", sa.Text(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("watch_sources") as batch_op:
        batch_op.drop_column("bookmarks_json")
        batch_op.drop_column("last_viewed_at")
        batch_op.drop_column("last_position_ms")

    for table_name, constraint_name, author_col in [
        ("chat_messages", "uq_chat_message_sender_idempotency", "sender_id"),
        ("moments", "uq_moment_author_idempotency", "author_id"),
        ("checkins", "uq_checkin_author_idempotency", "author_id"),
        ("wishes", "uq_wish_author_idempotency", "author_id"),
    ]:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="unique")
            batch_op.drop_column("client_idempotency_key")
