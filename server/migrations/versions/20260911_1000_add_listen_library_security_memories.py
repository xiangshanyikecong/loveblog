# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""add listen library (liked tracks + custom playlists), TOTP, login devices, memory push log

Revision ID: 20260911_1000
Revises: 20260719_1000
Create Date: 2026-09-11 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260911_1000"
down_revision = "20260719_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Listen library: per-user liked tracks ("我喜欢") ──────────────────────
    op.create_table(
        "listen_liked_tracks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lid", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("song_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("artists_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("album", sa.String(length=256), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cover_url", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lid"),
        sa.UniqueConstraint("user_id", "song_id", name="uq_listen_liked_user_song"),
    )
    op.create_index(op.f("ix_listen_liked_tracks_id"), "listen_liked_tracks", ["id"], unique=False)
    op.create_index(
        op.f("ix_listen_liked_tracks_user_id"), "listen_liked_tracks", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_listen_liked_tracks_song_id"), "listen_liked_tracks", ["song_id"], unique=False
    )
    op.create_index(
        op.f("ix_listen_liked_tracks_created_at"), "listen_liked_tracks", ["created_at"], unique=False
    )

    # ── Listen library: couple-built custom playlists ("我们的歌单") ───────────
    op.create_table(
        "listen_playlists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pid", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.String(length=512), nullable=True),
        sa.Column("created_by_uid", sa.String(length=36), nullable=False),
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
        sa.UniqueConstraint("pid"),
    )
    op.create_index(op.f("ix_listen_playlists_id"), "listen_playlists", ["id"], unique=False)
    op.create_index(
        op.f("ix_listen_playlists_created_by_uid"), "listen_playlists", ["created_by_uid"], unique=False
    )
    op.create_index(
        op.f("ix_listen_playlists_updated_at"), "listen_playlists", ["updated_at"], unique=False
    )

    op.create_table(
        "listen_playlist_tracks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ptid", sa.String(length=36), nullable=False),
        sa.Column("playlist_id", sa.Integer(), nullable=False),
        sa.Column("song_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("artists_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("album", sa.String(length=256), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cover_url", sa.String(length=512), nullable=True),
        sa.Column("added_by_uid", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ptid"),
        sa.UniqueConstraint("playlist_id", "song_id", name="uq_listen_playlist_song"),
    )
    op.create_index(
        op.f("ix_listen_playlist_tracks_id"), "listen_playlist_tracks", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_listen_playlist_tracks_playlist_id"), "listen_playlist_tracks", ["playlist_id"], unique=False
    )
    op.create_index(
        op.f("ix_listen_playlist_tracks_song_id"), "listen_playlist_tracks", ["song_id"], unique=False
    )

    # ── Security: TOTP two-factor authentication on users ────────────────────
    op.add_column("users", sa.Column("totp_secret", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("totp_recovery_codes", sa.Text(), nullable=True))

    # ── Security: login device management ────────────────────────────────────
    op.create_table(
        "login_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("did", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("device_hash", sa.String(length=64), nullable=False),
        sa.Column("device_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("did"),
        sa.UniqueConstraint("user_id", "device_hash", name="uq_login_device_user_hash"),
    )
    op.create_index(op.f("ix_login_devices_id"), "login_devices", ["id"], unique=False)
    op.create_index(op.f("ix_login_devices_user_id"), "login_devices", ["user_id"], unique=False)
    op.create_index(op.f("ix_login_devices_last_login_at"), "login_devices", ["last_login_at"], unique=False)

    # ── Memories: dedup log for "on this day" pushes ─────────────────────────
    op.create_table(
        "memory_push_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date_key", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date_key", name="uq_memory_push_date_key"),
    )


def downgrade() -> None:
    op.drop_table("memory_push_log")
    op.drop_index(op.f("ix_login_devices_last_login_at"), table_name="login_devices")
    op.drop_index(op.f("ix_login_devices_user_id"), table_name="login_devices")
    op.drop_index(op.f("ix_login_devices_id"), table_name="login_devices")
    op.drop_table("login_devices")
    op.drop_column("users", "totp_recovery_codes")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret")
    op.drop_index(op.f("ix_listen_playlist_tracks_song_id"), table_name="listen_playlist_tracks")
    op.drop_index(op.f("ix_listen_playlist_tracks_playlist_id"), table_name="listen_playlist_tracks")
    op.drop_index(op.f("ix_listen_playlist_tracks_id"), table_name="listen_playlist_tracks")
    op.drop_table("listen_playlist_tracks")
    op.drop_index(op.f("ix_listen_playlists_updated_at"), table_name="listen_playlists")
    op.drop_index(op.f("ix_listen_playlists_created_by_uid"), table_name="listen_playlists")
    op.drop_index(op.f("ix_listen_playlists_id"), table_name="listen_playlists")
    op.drop_table("listen_playlists")
    op.drop_index(op.f("ix_listen_liked_tracks_created_at"), table_name="listen_liked_tracks")
    op.drop_index(op.f("ix_listen_liked_tracks_song_id"), table_name="listen_liked_tracks")
    op.drop_index(op.f("ix_listen_liked_tracks_user_id"), table_name="listen_liked_tracks")
    op.drop_index(op.f("ix_listen_liked_tracks_id"), table_name="listen_liked_tracks")
    op.drop_table("listen_liked_tracks")
