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

"""add cottage 一起玩 game_matches table

Revision ID: 20260614_0000
Revises: 20260613_1200
Create Date: 2026-06-14 00:00:00.000000

Purely additive: creates one new table for cottage two-person game results.
It touches no existing table, so it is safe to roll back (drop table) with zero
impact on existing data.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260614_0000"
down_revision = "20260613_1200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gmid", sa.String(length=36), nullable=False),
        sa.Column("game_key", sa.String(length=32), nullable=False, server_default=sa.text("'gomoku'")),
        sa.Column("black_id", sa.Integer(), nullable=False),
        sa.Column("white_id", sa.Integer(), nullable=False),
        sa.Column("winner_id", sa.Integer(), nullable=True),
        sa.Column("is_draw", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("end_reason", sa.String(length=16), nullable=False, server_default=sa.text("'five'")),
        sa.Column("move_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["black_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["white_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["winner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_game_matches_id"), "game_matches", ["id"], unique=False)
    op.create_index(op.f("ix_game_matches_gmid"), "game_matches", ["gmid"], unique=True)
    op.create_index(op.f("ix_game_matches_game_key"), "game_matches", ["game_key"], unique=False)
    op.create_index(op.f("ix_game_matches_black_id"), "game_matches", ["black_id"], unique=False)
    op.create_index(op.f("ix_game_matches_white_id"), "game_matches", ["white_id"], unique=False)
    op.create_index(op.f("ix_game_matches_winner_id"), "game_matches", ["winner_id"], unique=False)
    op.create_index(op.f("ix_game_matches_created_at"), "game_matches", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_game_matches_created_at"), table_name="game_matches")
    op.drop_index(op.f("ix_game_matches_winner_id"), table_name="game_matches")
    op.drop_index(op.f("ix_game_matches_white_id"), table_name="game_matches")
    op.drop_index(op.f("ix_game_matches_black_id"), table_name="game_matches")
    op.drop_index(op.f("ix_game_matches_game_key"), table_name="game_matches")
    op.drop_index(op.f("ix_game_matches_gmid"), table_name="game_matches")
    op.drop_index(op.f("ix_game_matches_id"), table_name="game_matches")
    op.drop_table("game_matches")
