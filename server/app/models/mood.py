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
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MoodCheckin(Base):
    """A daily mood check-in (小屋·心情打卡).

    Reuses the "报备" paradigm: one entry per partner per day. Re-submitting
    the same day overwrites the entry (upsert), enforced by the
    ``(author_id, mood_date)`` unique constraint. ``mood`` is a short string
    key (e.g. ``happy`` / ``loved`` / ``sad``) and ``emoji`` is the display
    glyph, both chosen from a frontend palette so new moods need no migration.
    """

    __tablename__ = "mood_checkins"
    __table_args__ = (
        UniqueConstraint("author_id", "mood_date", name="uq_mood_author_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # The local calendar day this mood is for (sent by the client so it
    # respects the couple's local timezone rather than server UTC).
    mood_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Short mood key from the frontend palette.
    mood: Mapped[str] = mapped_column(String(32), nullable=False)
    # Display glyph for the mood (e.g. an emoji).
    emoji: Mapped[str | None] = mapped_column(String(16), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    author = relationship("User", foreign_keys=[author_id])
