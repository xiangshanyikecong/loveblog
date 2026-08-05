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

"""Cottage footprints map (恋爱足迹地图) routes.

Aggregates the *resolved city text* already captured by the 报备 (check-in)
module into a shared "places we've been" view. This endpoint reads only the
de-identified ``location_text`` column — never any raw IP or latitude /
longitude, which the check-in module never persists in the first place.

Unlike the check-in read endpoints (which hide your own check-ins from you),
the footprints view intentionally aggregates *both* partners' located
check-ins, since the whole point is to look back on the places the couple has
visited together.

Endpoint under ``/v1/cottage/footprints``:

- ``GET /v1/cottage/footprints`` — visited cities + counts + recent timeline
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.checkin import CheckIn, LocationStatus
from app.models.user import User
from app.schemas.footprint import FootprintCity, FootprintRecent, FootprintResponse


router = APIRouter(prefix="/cottage/footprints", tags=["cottage-footprints"])


@router.get("", response_model=FootprintResponse)
def list_footprints(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FootprintResponse:
    ensure_partner(current_user)

    located = (
        CheckIn.deleted_at.is_(None),
        CheckIn.location_status == LocationStatus.resolved.value,
        CheckIn.location_text.isnot(None),
    )

    grouped = (
        db.query(
            CheckIn.location_text.label("city"),
            func.count(CheckIn.id).label("count"),
            func.min(CheckIn.created_at).label("first_at"),
            func.max(CheckIn.created_at).label("last_at"),
        )
        .filter(*located)
        .group_by(CheckIn.location_text)
        .all()
    )

    cities = [
        FootprintCity(
            city=row.city,
            count=int(row.count),
            first_at=row.first_at,
            last_at=row.last_at,
        )
        for row in grouped
    ]
    # Most-visited first, then most-recently visited.
    cities.sort(key=lambda c: (c.count, c.last_at), reverse=True)

    total_checkins = sum(c.count for c in cities)

    recent_rows = (
        db.query(CheckIn)
        .options(joinedload(CheckIn.author))
        .filter(*located)
        .order_by(CheckIn.created_at.desc())
        .limit(12)
        .all()
    )
    recent = [
        FootprintRecent(
            city=row.location_text or "",
            author_nickname=row.author.nickname if row.author else "",
            created_at=row.created_at,
        )
        for row in recent_rows
    ]

    return FootprintResponse(
        cities=cities,
        total_cities=len(cities),
        total_checkins=total_checkins,
        recent=recent,
    )
