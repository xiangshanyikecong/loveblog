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

"""On-this-day memory collection and the daily "回到那一天" push.

Every day at most one push is sent per couple, guarded by ``MemoryPushLog``
(``date_key`` unique): a row for a given day means the tick already ran,
whether or not there was anything to show. That keeps empty days from being
rescanned on every scheduler pass.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.models.album import Album
from app.models.article import Article
from app.models.listen_history import ListenHistoryEntry
from app.models.memory_push_log import MemoryPushLog
from app.services.notifications import create_notification, partner_recipients

logger = logging.getLogger(__name__)

# Display caps: how many items of each kind a single year group exposes.
MAX_ARTICLES_PER_YEAR = 5
MAX_ALBUMS_PER_YEAR = 5
MAX_SONGS_PER_YEAR = 10

MEMORY_PUSH_TYPE = "memory.on_this_day"
MEMORY_PUSH_TITLE = "回到那一天"
MEMORY_PUSH_LINK = "/cottage/memories"
MEMORY_PUSH_SOURCE_TYPE = "memory_on_this_day"


@dataclass(slots=True)
class OnThisDayTotals:
    """True (uncapped) counts of matched items."""

    articles: int = 0
    albums: int = 0
    songs: int = 0


@dataclass(slots=True)
class OnThisDayYear:
    """Everything that happened on this month/day in one past year."""

    year: int
    articles: list[Article] = field(default_factory=list)
    albums: list[Album] = field(default_factory=list)
    songs: list[ListenHistoryEntry] = field(default_factory=list)
    totals: OnThisDayTotals = field(default_factory=OnThisDayTotals)


@dataclass(slots=True)
class OnThisDayResult:
    date: date
    years: list[OnThisDayYear] = field(default_factory=list)
    totals: OnThisDayTotals = field(default_factory=OnThisDayTotals)


def collect_on_this_day(
    db: Session,
    *,
    today: date,
    article_limit: int = MAX_ARTICLES_PER_YEAR,
    album_limit: int = MAX_ALBUMS_PER_YEAR,
    song_limit: int = MAX_SONGS_PER_YEAR,
) -> OnThisDayResult:
    """Gather couple artefacts sharing today's month/day in any *earlier* year.

    Returns one group per year (most recent first). Each group exposes at most
    ``article_limit`` / ``album_limit`` / ``song_limit`` items while
    ``totals`` always carries the true counts.
    """
    articles = (
        db.query(Article)
        .filter(
            Article.deleted_at.is_(None),
            extract("month", Article.created_at) == today.month,
            extract("day", Article.created_at) == today.day,
            extract("year", Article.created_at) < today.year,
        )
        .order_by(Article.created_at.desc())
        .all()
    )
    albums = (
        db.query(Album)
        .filter(
            Album.deleted_at.is_(None),
            extract("month", Album.created_at) == today.month,
            extract("day", Album.created_at) == today.day,
            extract("year", Album.created_at) < today.year,
        )
        .order_by(Album.created_at.desc())
        .all()
    )
    songs = (
        db.query(ListenHistoryEntry)
        .filter(
            extract("month", ListenHistoryEntry.played_at) == today.month,
            extract("day", ListenHistoryEntry.played_at) == today.day,
            extract("year", ListenHistoryEntry.played_at) < today.year,
        )
        .order_by(ListenHistoryEntry.played_at.desc())
        .all()
    )

    years: dict[int, OnThisDayYear] = {}

    def _bucket(year: int) -> OnThisDayYear:
        bucket = years.get(year)
        if bucket is None:
            bucket = OnThisDayYear(year=year)
            years[year] = bucket
        return bucket

    for article in articles:
        bucket = _bucket(article.created_at.year)
        bucket.totals.articles += 1
        if len(bucket.articles) < article_limit:
            bucket.articles.append(article)
    for album in albums:
        bucket = _bucket(album.created_at.year)
        bucket.totals.albums += 1
        if len(bucket.albums) < album_limit:
            bucket.albums.append(album)
    for song in songs:
        bucket = _bucket(song.played_at.year)
        bucket.totals.songs += 1
        if len(bucket.songs) < song_limit:
            bucket.songs.append(song)

    return OnThisDayResult(
        date=today,
        years=[years[key] for key in sorted(years, reverse=True)],
        totals=OnThisDayTotals(
            articles=len(articles),
            albums=len(albums),
            songs=len(songs),
        ),
    )


def _build_push_body(result: OnThisDayResult, *, today: date) -> str:
    """Summarize the matched memories in one sentence, skipping empty kinds."""
    phrases: list[str] = []
    if result.totals.articles:
        phrases.append(f"写下了 {result.totals.articles} 篇日记")
    if result.totals.albums:
        phrases.append(f"上传了 {result.totals.albums} 个相册")
    if result.totals.songs:
        phrases.append(f"一起听了 {result.totals.songs} 首歌")
    if not phrases:
        return ""
    if len(result.years) == 1:
        years_ago = today.year - result.years[0].year
        prefix = f"{years_ago} 年前的今天，你们"
    else:
        prefix = "这些年的今天，你们一共"
    return f"{prefix}{'、'.join(phrases)}。"


def run_memory_push_tick(db: Session, *, today: date) -> int:
    """Send the once-a-day "on this day" notification to both partners.

    Idempotent per calendar day via ``MemoryPushLog.date_key``; the date key
    is recorded even when nothing matched so empty days are not rescanned.
    Returns the number of notifications created this tick.
    """
    date_key = today.isoformat()
    already_ran = (
        db.query(MemoryPushLog.id).filter(MemoryPushLog.date_key == date_key).first()
    )
    if already_ran is not None:
        return 0

    created = 0
    result = collect_on_this_day(db, today=today)
    has_memories = (
        result.totals.articles > 0 or result.totals.albums > 0 or result.totals.songs > 0
    )
    if has_memories:
        body = _build_push_body(result, today=today)
        for recipient in partner_recipients(db):
            item = create_notification(
                db,
                recipient=recipient,
                type=MEMORY_PUSH_TYPE,
                title=MEMORY_PUSH_TITLE,
                body=body,
                link=MEMORY_PUSH_LINK,
                source_type=MEMORY_PUSH_SOURCE_TYPE,
                source_id=date_key,
                dedupe=True,
                queue_delivery=True,
            )
            if item is not None:
                created += 1

    db.add(MemoryPushLog(date_key=date_key))
    db.commit()
    if created:
        logger.info("Memory push for %s created %d notification(s).", date_key, created)
    return created
