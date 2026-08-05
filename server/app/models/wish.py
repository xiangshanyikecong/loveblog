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

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WishStatus(str, enum.Enum):
    """Status of a cottage wishlist item.

    Persisted as a plain ``String(16)`` (not a SQL ENUM) so SQLite / Postgres
    migrations stay symmetric and future additions don't need an ``ALTER TYPE``
    round-trip — mirroring ``CheckIn.location_status``.
    """

    pending = "pending"
    completed = "completed"


class Wish(Base):
    """Cottage shared wishlist item (小屋心愿单：两人想一起做的事).

    The wishlist is a single list shared by both partners. Ownership is
    intentionally shared: either partner may create, edit, complete / reopen
    and delete any wish. ``author_id`` records who proposed it and
    ``completed_by_id`` records who marked it done.
    """

    __tablename__ = "wishes"
    __table_args__ = (
        # Offline-replay dedup.
        UniqueConstraint("author_id", "client_idempotency_key", name="uq_wish_author_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    wid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Free-form short category label (旅行 / 美食 / 礼物 / 体验 / 其他 ...). Stored as
    # a plain string so the frontend can evolve the preset list without a
    # backend enum migration.
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # One of WishStatus values, persisted as the string value (not the enum
    # member) for SQLite / Postgres symmetry.
    status: Mapped[str] = mapped_column(
        String(16), default=WishStatus.pending.value, nullable=False, index=True
    )
    # Higher value sorts first within the same status — lets a couple pin the
    # wishes they care about most to the top.
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Offline-replay dedup key supplied by the Android SyncEngine.
    client_idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Two distinct FKs to users → disambiguate with explicit foreign_keys.
    author = relationship("User", foreign_keys=[author_id])
    completed_by = relationship("User", foreign_keys=[completed_by_id])
