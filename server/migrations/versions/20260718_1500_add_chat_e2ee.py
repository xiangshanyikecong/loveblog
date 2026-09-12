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

"""add end-to-end encrypted chat columns + chat_keys table

Revision ID: 20260718_1500
Revises: 20260718_1300
"""
from alembic import op
import sqlalchemy as sa


revision = "20260718_1500"
down_revision = "20260718_1300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.add_column(
            sa.Column("is_encrypted", sa.Boolean(), nullable=False, server_default=sa.text("false"))
        )
        batch_op.add_column(sa.Column("iv", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("ciphertext", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("algo", sa.String(length=16), nullable=True))
    op.create_index(
        op.f("ix_chat_messages_is_encrypted"), "chat_messages", ["is_encrypted"], unique=False
    )

    op.create_table(
        "chat_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("salt", sa.String(length=128), nullable=False),
        sa.Column("kdf", sa.String(length=32), nullable=False, server_default="PBKDF2"),
        sa.Column("kdf_hash", sa.String(length=32), nullable=False, server_default="SHA-256"),
        sa.Column("iterations", sa.Integer(), nullable=False, server_default="210000"),
        sa.Column("algo", sa.String(length=32), nullable=False, server_default="AES-GCM"),
        sa.Column("verifier_iv", sa.String(length=64), nullable=False),
        sa.Column("verifier_cipher", sa.String(length=512), nullable=False),
        sa.Column("verifier_hash", sa.String(length=128), nullable=False),
        sa.Column("needs_re_encrypt", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_chat_keys_user"),
    )
    op.create_index(op.f("ix_chat_keys_id"), "chat_keys", ["id"], unique=False)
    op.create_index(op.f("ix_chat_keys_user_id"), "chat_keys", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_keys_user_id"), table_name="chat_keys")
    op.drop_index(op.f("ix_chat_keys_id"), table_name="chat_keys")
    op.drop_table("chat_keys")
    op.drop_index(op.f("ix_chat_messages_is_encrypted"), table_name="chat_messages")
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_column("algo")
        batch_op.drop_column("ciphertext")
        batch_op.drop_column("iv")
        batch_op.drop_column("is_encrypted")
