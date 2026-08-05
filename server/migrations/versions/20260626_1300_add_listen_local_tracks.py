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

"""add listen_local_tracks table

Revision ID: 20260626_1300
Revises: 20260621_0900
Create Date: 2026-06-26 13:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260626_1300"
down_revision = "20260621_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "listen_local_tracks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tid", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("artists_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("album", sa.String(length=256), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cover_url", sa.String(length=512), nullable=True),
        sa.Column("audio_url", sa.String(length=512), nullable=False),
        sa.Column("uploaded_by_uid", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_listen_local_tracks_id"), "listen_local_tracks", ["id"], unique=False)
    op.create_index(op.f("ix_listen_local_tracks_tid"), "listen_local_tracks", ["tid"], unique=True)
    op.create_index(
        op.f("ix_listen_local_tracks_uploaded_by_uid"),
        "listen_local_tracks",
        ["uploaded_by_uid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_listen_local_tracks_created_at"),
        "listen_local_tracks",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_listen_local_tracks_created_at"), table_name="listen_local_tracks")
    op.drop_index(op.f("ix_listen_local_tracks_uploaded_by_uid"), table_name="listen_local_tracks")
    op.drop_index(op.f("ix_listen_local_tracks_tid"), table_name="listen_local_tracks")
    op.drop_index(op.f("ix_listen_local_tracks_id"), table_name="listen_local_tracks")
    op.drop_table("listen_local_tracks")
