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

"""add content versions and notifications

Revision ID: add_versions_notifications
Revises: c0efd7ec594c
Create Date: 2026-04-26 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "add_versions_notifications"
down_revision = "c0efd7ec594c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vid", sa.String(length=36), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("content_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_type", "content_id", "version", name="uq_content_versions_item_version"),
    )
    op.create_index(op.f("ix_content_versions_id"), "content_versions", ["id"], unique=False)
    op.create_index(op.f("ix_content_versions_vid"), "content_versions", ["vid"], unique=True)
    op.create_index(op.f("ix_content_versions_content_type"), "content_versions", ["content_type"], unique=False)
    op.create_index(op.f("ix_content_versions_content_id"), "content_versions", ["content_id"], unique=False)
    op.create_index(op.f("ix_content_versions_actor_id"), "content_versions", ["actor_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nid", sa.String(length=36), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index(op.f("ix_notifications_nid"), "notifications", ["nid"], unique=True)
    op.create_index(op.f("ix_notifications_recipient_id"), "notifications", ["recipient_id"], unique=False)
    op.create_index(op.f("ix_notifications_type"), "notifications", ["type"], unique=False)
    op.create_index(op.f("ix_notifications_source_type"), "notifications", ["source_type"], unique=False)
    op.create_index(op.f("ix_notifications_source_id"), "notifications", ["source_id"], unique=False)
    op.create_index(op.f("ix_notifications_is_read"), "notifications", ["is_read"], unique=False)

    op.add_column("messages", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("messages", "version")
    op.drop_index(op.f("ix_notifications_is_read"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_source_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_source_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_recipient_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_nid"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_content_versions_actor_id"), table_name="content_versions")
    op.drop_index(op.f("ix_content_versions_content_id"), table_name="content_versions")
    op.drop_index(op.f("ix_content_versions_content_type"), table_name="content_versions")
    op.drop_index(op.f("ix_content_versions_vid"), table_name="content_versions")
    op.drop_index(op.f("ix_content_versions_id"), table_name="content_versions")
    op.drop_table("content_versions")
