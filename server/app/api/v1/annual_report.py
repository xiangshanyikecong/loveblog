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

"""Couple annual report endpoints."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.album import Album, AlbumMedia
from app.models.article import Article
from app.models.capsule import Capsule
from app.models.checkin import CheckIn
from app.models.listen_history import ListenHistoryEntry
from app.models.message import Message
from app.models.site_setting import SiteSetting
from app.models.user import User
from app.models.wish import Wish, WishStatus
from app.schemas.annual_report import (
    AnnualReportResponse,
    AnnualStats,
    MonthlyActivity,
    TopSong,
)

router = APIRouter(prefix="/reports", tags=["reports"])

_TOP_SONGS_LIMIT = 10
_MAX_HIGHLIGHTS = 6


def _count(query) -> int:
    return int(query.scalar() or 0)


def _parse_artists(raw: str | None) -> list[str]:
    try:
        data = json.loads(raw or "[]")
        return [str(a) for a in data if a] if isinstance(data, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _build_highlights(stats: AnnualStats) -> list[str]:
    """Fun Chinese summary lines; only non-zero categories, capped at 6."""
    items: list[str] = []
    if stats.articles:
        items.append(f"这一年你们一共写下了 {stats.articles} 篇日记")
    if stats.albums:
        items.append(f"一起整理了 {stats.albums} 个相册")
    if stats.photos:
        items.append(f"用镜头收藏了 {stats.photos} 张照片")
    if stats.checkins:
        items.append(f"留下了 {stats.checkins} 条小屋报备")
    if stats.messages:
        items.append(f"写下了 {stats.messages} 条留言")
    if stats.songs_played:
        minutes_part = f"，共 {stats.songs_minutes} 分钟" if stats.songs_minutes else ""
        items.append(f"一起听了 {stats.songs_played} 首歌{minutes_part}")
    if stats.capsules_created:
        items.append(f"埋下了 {stats.capsules_created} 个时间胶囊")
    if stats.wishes_completed:
        items.append(f"完成了 {stats.wishes_completed} 个心愿")
    return items[:_MAX_HIGHLIGHTS]


@router.get("/annual", response_model=AnnualReportResponse)
def annual_report(
    year: Annotated[int, Query(ge=1970, le=2100)],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnnualReportResponse:
    """Aggregate the couple's calendar-year (UTC) activity into one report."""
    ensure_partner(current_user)

    start_dt = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    stats = AnnualStats(
        articles=_count(
            db.query(func.count(Article.id)).filter(
                Article.deleted_at.is_(None),
                Article.created_at >= start_dt,
                Article.created_at < end_dt,
            )
        ),
        albums=_count(
            db.query(func.count(Album.id)).filter(
                Album.deleted_at.is_(None),
                Album.created_at >= start_dt,
                Album.created_at < end_dt,
            )
        ),
        photos=_count(
            db.query(func.count(AlbumMedia.id))
            .join(Album, Album.id == AlbumMedia.album_id)
            .filter(
                Album.deleted_at.is_(None),
                AlbumMedia.created_at >= start_dt,
                AlbumMedia.created_at < end_dt,
            )
        ),
        checkins=_count(
            db.query(func.count(CheckIn.id)).filter(
                CheckIn.deleted_at.is_(None),
                CheckIn.created_at >= start_dt,
                CheckIn.created_at < end_dt,
            )
        ),
        messages=_count(
            db.query(func.count(Message.id)).filter(
                Message.is_deleted.is_(False),
                Message.created_at >= start_dt,
                Message.created_at < end_dt,
            )
        ),
        songs_played=_count(
            db.query(func.count(ListenHistoryEntry.id)).filter(
                ListenHistoryEntry.played_at >= start_dt,
                ListenHistoryEntry.played_at < end_dt,
            )
        ),
        songs_minutes=int(
            db.query(func.sum(ListenHistoryEntry.duration_ms))
            .filter(
                ListenHistoryEntry.played_at >= start_dt,
                ListenHistoryEntry.played_at < end_dt,
            )
            .scalar()
            or 0
        )
        // 60000,
        capsules_created=_count(
            db.query(func.count(Capsule.id)).filter(
                Capsule.deleted_at.is_(None),
                Capsule.created_at >= start_dt,
                Capsule.created_at < end_dt,
            )
        ),
        wishes_completed=_count(
            db.query(func.count(Wish.id)).filter(
                Wish.deleted_at.is_(None),
                Wish.status == WishStatus.completed.value,
                Wish.completed_at >= start_dt,
                Wish.completed_at < end_dt,
            )
        ),
    )

    # Monthly activity: one group-by per content kind, merged into 12 buckets.
    articles_by_month = {
        int(row[0]): int(row[1] or 0)
        for row in db.query(
            extract("month", Article.created_at), func.count(Article.id)
        )
        .filter(
            Article.deleted_at.is_(None),
            Article.created_at >= start_dt,
            Article.created_at < end_dt,
        )
        .group_by(extract("month", Article.created_at))
        .all()
    }
    songs_by_month = {
        int(row[0]): int(row[1] or 0)
        for row in db.query(
            extract("month", ListenHistoryEntry.played_at), func.count(ListenHistoryEntry.id)
        )
        .filter(
            ListenHistoryEntry.played_at >= start_dt,
            ListenHistoryEntry.played_at < end_dt,
        )
        .group_by(extract("month", ListenHistoryEntry.played_at))
        .all()
    }
    checkins_by_month = {
        int(row[0]): int(row[1] or 0)
        for row in db.query(extract("month", CheckIn.created_at), func.count(CheckIn.id))
        .filter(
            CheckIn.deleted_at.is_(None),
            CheckIn.created_at >= start_dt,
            CheckIn.created_at < end_dt,
        )
        .group_by(extract("month", CheckIn.created_at))
        .all()
    }

    monthly = [
        MonthlyActivity(
            month=month,
            articles=articles_by_month.get(month, 0),
            songs=songs_by_month.get(month, 0),
            checkins=checkins_by_month.get(month, 0),
        )
        for month in range(1, 13)
    ]

    top_song_rows = (
        db.query(
            ListenHistoryEntry.song_id,
            ListenHistoryEntry.name,
            ListenHistoryEntry.artists_json,
            ListenHistoryEntry.cover_url,
            func.count(ListenHistoryEntry.id),
        )
        .filter(
            ListenHistoryEntry.played_at >= start_dt,
            ListenHistoryEntry.played_at < end_dt,
        )
        .group_by(
            ListenHistoryEntry.song_id,
            ListenHistoryEntry.name,
            ListenHistoryEntry.artists_json,
            ListenHistoryEntry.cover_url,
        )
        .order_by(
            func.count(ListenHistoryEntry.id).desc(),
            ListenHistoryEntry.song_id.asc(),
        )
        .limit(_TOP_SONGS_LIMIT)
        .all()
    )
    top_songs = [
        TopSong(
            song_id=row[0],
            name=row[1] or "",
            artists=_parse_artists(row[2]),
            cover_url=row[3],
            play_count=int(row[4] or 0),
        )
        for row in top_song_rows
    ]

    setting = db.query(SiteSetting).filter(SiteSetting.id == 1).first()
    love_start = setting.love_start_date if setting is not None else None
    couple_since: str | None = None
    days_together = 0
    if love_start is not None:
        start_day = love_start.date()
        couple_since = start_day.isoformat()
        # Past years count up to their Dec 31; the current year up to today.
        end_day = min(date(year, 12, 31), datetime.now(timezone.utc).date())
        days_together = max(0, (end_day - start_day).days)

    return AnnualReportResponse(
        year=year,
        couple_since=couple_since,
        days_together=days_together,
        stats=stats,
        monthly=monthly,
        top_songs=top_songs,
        highlights=_build_highlights(stats),
    )
