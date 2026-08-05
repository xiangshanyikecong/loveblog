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

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GameMatch(Base):
    """A finished cottage 一起玩 match (战绩).

    Lightweight, append-only record written when a game ends. Enables a simple
    win/streak board later without coupling to the live (Redis) room. Like the
    other cottage models the ``game_key`` is a plain ``String`` (not a SQL
    ENUM) so new games don't need an ``ALTER TYPE`` round-trip.
    """

    __tablename__ = "game_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    gmid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    game_key: Mapped[str] = mapped_column(String(32), default="gomoku", nullable=False, index=True)
    black_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    white_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # NULL winner = draw. Otherwise the FK of the winning player.
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    is_draw: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # One of "five" | "surrender" | "draw".
    end_reason: Mapped[str] = mapped_column(String(16), default="five", nullable=False)
    move_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    black = relationship("User", foreign_keys=[black_id])
    white = relationship("User", foreign_keys=[white_id])
    winner = relationship("User", foreign_keys=[winner_id])
