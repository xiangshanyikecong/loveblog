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

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CottageTap(Base):
    """A lightweight "tap" between partners (小屋·轻触回应).

    Append-only signal log backing the watch / widget "敲一敲" interaction:
    sending a tap records one row here (for history + client catch-up) and
    fans out through the regular notification delivery pipeline, so it rides
    the existing web-push / FCM channels instead of needing its own socket.
    """

    __tablename__ = "cottage_taps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # One of "tap" (敲一敲) | "heartbeat" (心跳/想你), persisted as a plain
    # string (not a SQL ENUM) so SQLite / Postgres migrations stay symmetric.
    kind: Mapped[str] = mapped_column(String(16), default="tap", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])
