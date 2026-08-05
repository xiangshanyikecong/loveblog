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

"""add end-to-end-encrypted vault tables (vault_meta, vault_entries)

Revision ID: 20260620_1230
Revises: 20260620_1220
Create Date: 2026-06-20 14:00:00.000000

Creates the storage for the cottage 加密保险箱 (true E2EE vault):

- ``vault_meta``    — singleton (id=1) holding the couple's KDF params + a
                      passphrase verifier blob. No key / passphrase is stored.
- ``vault_entries`` — individual notes stored as opaque AES-GCM ciphertext.

The server is a *blind store*: every payload is encrypted in the browser, so
these tables never contain readable plaintext.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260620_1230"
down_revision = "20260620_1220"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())

    if "vault_meta" not in existing:
        op.create_table(
            "vault_meta",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("salt", sa.String(length=128), nullable=False),
            sa.Column("kdf", sa.String(length=32), nullable=False, server_default=sa.text("'PBKDF2'")),
            sa.Column("kdf_hash", sa.String(length=32), nullable=False, server_default=sa.text("'SHA-256'")),
            sa.Column("iterations", sa.Integer(), nullable=False, server_default=sa.text("210000")),
            sa.Column("algo", sa.String(length=32), nullable=False, server_default=sa.text("'AES-GCM'")),
            sa.Column("verifier_iv", sa.String(length=64), nullable=False),
            sa.Column("verifier_cipher", sa.String(length=512), nullable=False),
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
            sa.PrimaryKeyConstraint("id"),
        )

    if "vault_entries" not in existing:
        op.create_table(
            "vault_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("vid", sa.String(length=36), nullable=False),
            sa.Column("author_id", sa.Integer(), nullable=False),
            sa.Column("iv", sa.String(length=64), nullable=False),
            sa.Column("ciphertext", sa.Text(), nullable=False),
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
            sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_vault_entries_id"), "vault_entries", ["id"], unique=False)
        op.create_index(op.f("ix_vault_entries_vid"), "vault_entries", ["vid"], unique=True)
        op.create_index(op.f("ix_vault_entries_author_id"), "vault_entries", ["author_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_vault_entries_author_id"), table_name="vault_entries")
    op.drop_index(op.f("ix_vault_entries_vid"), table_name="vault_entries")
    op.drop_index(op.f("ix_vault_entries_id"), table_name="vault_entries")
    op.drop_table("vault_entries")
    op.drop_table("vault_meta")
