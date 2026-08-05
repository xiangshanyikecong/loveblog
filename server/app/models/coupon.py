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
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CouponStatus(str, enum.Enum):
    """Status of a love coupon (甜蜜兑换券).

    Persisted as a plain ``String(16)`` (not a SQL ENUM) so SQLite / Postgres
    migrations stay symmetric and future additions don't need an ``ALTER TYPE``
    round-trip — mirroring ``Wish.status`` / ``CheckIn.location_status``.
    """

    active = "active"
    redeemed = "redeemed"


class Coupon(Base):
    """A love coupon one partner gifts to the other (小屋·甜蜜兑换券).

    The author *issues* a coupon (e.g. 「一次免做家务券」「一个抱抱券」) for
    their partner. Only the counterpart (``author_id != redeemer``) may redeem
    it. ``author_id`` records who gave it and ``redeemed_by_id`` records who
    cashed it in. Soft-deletable, mirroring the other cottage modules.
    """

    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cpid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Short display glyph (emoji) chosen from a frontend palette so new icons
    # need no migration.
    icon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # One of CouponStatus values, persisted as the string value.
    status: Mapped[str] = mapped_column(
        String(16), default=CouponStatus.active.value, nullable=False, index=True
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_by_id: Mapped[int | None] = mapped_column(
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

    # Two distinct FKs to users → disambiguate with explicit foreign_keys.
    author = relationship("User", foreign_keys=[author_id])
    redeemed_by = relationship("User", foreign_keys=[redeemed_by_id])
