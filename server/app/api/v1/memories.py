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

"""On-this-day memories endpoints (回到那一天)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.memories import (
    MemoryAlbumItem,
    MemoryArticleItem,
    MemorySongItem,
    MemoryTotals,
    MemoryYearGroup,
    OnThisDayResponse,
)
from app.services.memories import collect_on_this_day

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("/on-this-day", response_model=OnThisDayResponse)
def on_this_day(
    date: Annotated[
        str | None,
        Query(description="ISO date (YYYY-MM-DD) to look back from; defaults to today"),
    ] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OnThisDayResponse:
    """List what the couple wrote / uploaded / played on this month-day in past years."""
    ensure_partner(current_user)

    if date is None or not date.strip():
        target = datetime.now(timezone.utc).date()
    else:
        try:
            target = datetime.strptime(date.strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invalid date, expected YYYY-MM-DD",
            ) from exc

    result = collect_on_this_day(db, today=target)

    years = [
        MemoryYearGroup(
            year=group.year,
            articles=[
                MemoryArticleItem(
                    aid=article.aid,
                    title=article.title,
                    excerpt=article.excerpt,
                    created_at=article.created_at.isoformat(),
                )
                for article in group.articles
            ],
            albums=[
                MemoryAlbumItem(
                    alb_id=album.alb_id,
                    title=album.title,
                    cover_url=album.cover_url,
                    created_at=album.created_at.isoformat(),
                )
                for album in group.albums
            ],
            songs=[
                MemorySongItem(
                    song_id=song.song_id,
                    name=song.name,
                    artists=song.artists,
                    cover_url=song.cover_url,
                    played_at=song.played_at.isoformat(),
                )
                for song in group.songs
            ],
            totals=MemoryTotals(
                articles=group.totals.articles,
                albums=group.totals.albums,
                songs=group.totals.songs,
            ),
        )
        for group in result.years
    ]

    return OnThisDayResponse(
        date=target.isoformat(),
        years=years,
        totals=MemoryTotals(
            articles=result.totals.articles,
            albums=result.totals.albums,
            songs=result.totals.songs,
        ),
    )
