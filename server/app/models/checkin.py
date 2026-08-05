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

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LocationStatus(str, enum.Enum):
    """Status of the location field on a CheckIn record.

    Persisted as a plain ``String(32)`` (not SQL ENUM) so SQLite/Postgres
    migrations stay symmetric and future enum additions don't require an
    ``ALTER TYPE`` round-trip.
    """

    resolved = "resolved"
    permission_denied = "permission_denied"
    lookup_failed = "lookup_failed"
    omitted = "omitted"


class CheckIn(Base):
    """Cottage check-in record (一方向另一半的报备).

    Privacy invariant (enforced by schema): this model carries the
    *resolved* city text only. The original IP and original latitude /
    longitude that produced ``location_text`` are read from the request
    transport, used to call the geocoding provider, and then discarded.
    They are never persisted on this row, on any related row, or in any
    log file.
    """

    __tablename__ = "checkins"
    __table_args__ = (
        # Offline-replay dedup.
        UniqueConstraint("author_id", "client_idempotency_key", name="uq_checkin_author_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_urls: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # location_text is the city string returned by the geocoding provider
    # for either the lat/lng reverse-geocode call or the IP fallback. Null
    # whenever location_status != "resolved".
    location_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # location_status is one of LocationStatus values, persisted as the
    # string value (not the enum member) for SQLite/Postgres symmetry.
    location_status: Mapped[str] = mapped_column(String(32), nullable=False)
    # location_provider is the name of the geocoding provider that produced
    # location_text. Only filled when location_status == "resolved" — drives
    # the frontend's "China mainland accuracy may be poor" hint when value
    # is "nominatim".
    location_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
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

    author = relationship("User")
