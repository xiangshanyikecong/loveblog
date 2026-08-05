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

"""add capsules and threaded comments

Revision ID: 20260419_0300
Revises: 116080679edb
Create Date: 2026-04-19 03:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260419_0300"
down_revision: Union[str, None] = "116080679edb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "capsules" not in tables:
        op.create_table(
            "capsules",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("uuid", sa.String(length=36), nullable=False),
            sa.Column("author_id", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("open_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_capsules_id"), "capsules", ["id"], unique=False)
        op.create_index(op.f("ix_capsules_uuid"), "capsules", ["uuid"], unique=True)
        op.create_index(op.f("ix_capsules_author_id"), "capsules", ["author_id"], unique=False)

    if "comments" not in tables:
        op.create_table(
            "comments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("cid", sa.String(length=36), nullable=False),
            sa.Column("moment_id", sa.Integer(), nullable=False),
            sa.Column("author_id", sa.Integer(), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("mention_uids_json", sa.Text(), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["moment_id"], ["moments.id"]),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["parent_id"], ["comments.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_comments_id"), "comments", ["id"], unique=False)
        op.create_index(op.f("ix_comments_cid"), "comments", ["cid"], unique=True)
        op.create_index(op.f("ix_comments_moment_id"), "comments", ["moment_id"], unique=False)
        op.create_index(op.f("ix_comments_author_id"), "comments", ["author_id"], unique=False)
        op.create_index(op.f("ix_comments_parent_id"), "comments", ["parent_id"], unique=False)
    else:
        comment_columns = {column["name"] for column in inspector.get_columns("comments")}
        if "parent_id" not in comment_columns:
            op.add_column("comments", sa.Column("parent_id", sa.Integer(), nullable=True))
        if "mention_uids_json" not in comment_columns:
            op.add_column("comments", sa.Column("mention_uids_json", sa.Text(), nullable=True))

        inspector = inspect(bind)
        if not _index_exists(inspector, "comments", op.f("ix_comments_parent_id")):
            op.create_index(op.f("ix_comments_parent_id"), "comments", ["parent_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "comments" in tables:
        for index_name in [
            op.f("ix_comments_parent_id"),
            op.f("ix_comments_author_id"),
            op.f("ix_comments_moment_id"),
            op.f("ix_comments_cid"),
            op.f("ix_comments_id"),
        ]:
            if _index_exists(inspector, "comments", index_name):
                op.drop_index(index_name, table_name="comments")
        op.drop_table("comments")

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "capsules" in tables:
        for index_name in [
            op.f("ix_capsules_author_id"),
            op.f("ix_capsules_uuid"),
            op.f("ix_capsules_id"),
        ]:
            if _index_exists(inspector, "capsules", index_name):
                op.drop_index(index_name, table_name="capsules")
        op.drop_table("capsules")
