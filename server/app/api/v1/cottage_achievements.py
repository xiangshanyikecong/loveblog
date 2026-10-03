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

"""Couple achievements & level endpoints (小屋·成就/情侣等级)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.achievements import AchievementsResponse
from app.services.achievements import build_achievements_response

router = APIRouter(prefix="/cottage/achievements", tags=["cottage-achievements"])


@router.get("", response_model=AchievementsResponse)
def achievements_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AchievementsResponse:
    ensure_partner(current_user)
    return build_achievements_response(db)
