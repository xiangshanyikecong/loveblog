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

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SplitType(str, enum.Enum):
    """How a ledger entry is shared between the two partners.

    Persisted as a plain ``String(16)`` for SQLite / Postgres symmetry.

    - ``aa``        — split evenly; the non-payer owes the payer half.
    - ``treat``     — the payer treats; nobody owes anything.
    - ``owed_full`` — the payer fronted the whole cost; the other owes it all.
    """

    aa = "aa"
    treat = "treat"
    owed_full = "owed_full"


class LedgerEntry(Base):
    """A shared expense record (小屋·情侣账本 / AA 记账).

    A single ledger shared by both partners. Amounts are stored in **cents**
    (integer) to avoid floating-point drift. ``payer_id`` is who actually paid;
    ``split_type`` drives the "who owes whom" net balance. ``author_id`` records
    who logged the entry (may differ from the payer). Soft-deletable.
    """

    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    leid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    payer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Amount in cents (分). Always non-negative.
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # Free-form short category label (餐饮 / 交通 / 购物 ...). Stored as a plain
    # string so the frontend can evolve the preset list without a migration.
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # One of SplitType values, persisted as the string value.
    split_type: Mapped[str] = mapped_column(
        String(16), default=SplitType.aa.value, nullable=False
    )
    # Local calendar day the money was spent (client-supplied for the couple's
    # local timezone rather than server UTC).
    spent_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
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

    author = relationship("User", foreign_keys=[author_id])
    payer = relationship("User", foreign_keys=[payer_id])
