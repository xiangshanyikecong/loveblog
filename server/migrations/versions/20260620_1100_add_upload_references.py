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

"""add upload_references table

Revision ID: 20260620_1100
Revises: 20260620_1000
Create Date: 2026-06-20 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260620_1100"
down_revision = "20260620_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "upload_references" in insp.get_table_names():
        return

    op.create_table(
        "upload_references",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=255), nullable=False),
        sa.Column("content_kind", sa.String(length=32), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("visibility", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("content_is_encrypted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ref_is_encrypted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("partner_can_edit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "file_path", "content_kind", "content_id", "slot", name="uq_upload_reference_target"
        ),
    )
    op.create_index(op.f("ix_upload_references_id"), "upload_references", ["id"], unique=False)
    op.create_index(op.f("ix_upload_references_file_path"), "upload_references", ["file_path"], unique=False)
    op.create_index(
        op.f("ix_upload_references_content_kind"), "upload_references", ["content_kind"], unique=False
    )
    op.create_index(
        op.f("ix_upload_references_content_id"), "upload_references", ["content_id"], unique=False
    )
    op.create_index(
        op.f("ix_upload_references_owner_user_id"), "upload_references", ["owner_user_id"], unique=False
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "upload_references" not in insp.get_table_names():
        return

    op.drop_index(op.f("ix_upload_references_owner_user_id"), table_name="upload_references")
    op.drop_index(op.f("ix_upload_references_content_id"), table_name="upload_references")
    op.drop_index(op.f("ix_upload_references_content_kind"), table_name="upload_references")
    op.drop_index(op.f("ix_upload_references_file_path"), table_name="upload_references")
    op.drop_index(op.f("ix_upload_references_id"), table_name="upload_references")
    op.drop_table("upload_references")
