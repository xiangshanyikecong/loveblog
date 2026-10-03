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

"""Couple achievements & level computation (小屋·成就/情侣等级).

Deliberately STATELESS: badges and the couple level are derived on the fly
from the couple's existing activity tables (articles, albums, moments,
capsules, check-ins, moods, chat, game matches, wishes, listen history and
the configured love start date). No new write path, no replay/repair job,
and a fresh deploy instantly reflects all history. The query set is ~15
cheap COUNTs — fine to run per request at couple scale.

Streaks use the *couple-union* of days (either partner's activity keeps the
streak alive). Mood days are client-supplied calendar days; check-in days
are the server-side UTC date of ``created_at``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.album import Album, AlbumMedia
from app.models.article import Article
from app.models.capsule import Capsule
from app.models.chat_message import ChatMessage, ChatMessageType
from app.models.checkin import CheckIn
from app.models.game_match import GameMatch
from app.models.listen_history import ListenHistoryEntry
from app.models.moment import Moment
from app.models.mood import MoodCheckin
from app.models.site_setting import SiteSetting
from app.models.wish import Wish, WishStatus
from app.schemas.achievements import AchievementsResponse, BadgeProgress, CoupleLevel

TIER_NAMES = ("bronze", "silver", "gold")


@dataclass(frozen=True, slots=True)
class BadgeDef:
    code: str
    name: str
    icon: str
    category: str
    stat: str
    unit: str
    # (bronze, silver, gold) thresholds.
    thresholds: tuple[int, int, int]
    description_template: str

    def describe(self, target: int) -> str:
        return self.description_template.format(target=target, unit=self.unit)


BADGES: tuple[BadgeDef, ...] = (
    BadgeDef("writer", "笔耕不辍", "✍️", "record", "articles", "篇", (1, 10, 50), "累计写下 {target} {unit}日记"),
    BadgeDef("photographer", "光影记录", "📷", "record", "albums", "本", (1, 5, 20), "创建 {target} {unit}相册"),
    BadgeDef("moments", "日常碎片", "🌤️", "record", "moments", "条", (1, 30, 200), "发布 {target} {unit}碎碎念"),
    BadgeDef("capsules", "时间胶囊", "⏳", "record", "capsules", "枚", (1, 5, 15), "埋下 {target} {unit}时间胶囊"),
    BadgeDef("checkin_streak", "报备不断", "📍", "habit", "checkin_streak_days", "天", (3, 14, 60), "连续 {target} {unit}有报备"),
    BadgeDef("mood_streak", "心心相印", "💗", "habit", "mood_streak_days", "天", (3, 14, 60), "连续 {target} {unit}记录心情"),
    BadgeDef("chat", "碎碎念念", "💬", "interact", "chat_messages", "条", (100, 1000, 10000), "悄悄话累计 {target} {unit}"),
    BadgeDef("gamer", "棋逢对手", "♟️", "interact", "games_played", "局", (5, 25, 100), "一起玩累计 {target} {unit}"),
    BadgeDef("wish", "心想事成", "🌟", "interact", "wishes_completed", "个", (1, 5, 20), "完成 {target} {unit}共同心愿"),
    BadgeDef("listener", "耳鬓厮磨", "🎧", "interact", "songs_played", "首", (10, 100, 500), "一起听了 {target} {unit}歌"),
    BadgeDef("days", "长长久久", "💞", "time", "love_days", "天", (100, 365, 1000), "在一起满 {target} {unit}"),
)

# (points threshold, title). Level = index + 1.
LEVELS: tuple[tuple[int, str], ...] = (
    (0, "初识"),
    (100, "心动"),
    (300, "怦然"),
    (700, "热恋"),
    (1500, "甜蜜日常"),
    (3000, "默契满满"),
    (6000, "灵魂伴侣"),
    (10000, "白首不离"),
)


def _count(query) -> int:
    return int(query.scalar() or 0)


def _day_streak(days: set[date], today: date) -> int:
    """Longest run of consecutive days ending today (or yesterday, so a couple
    that hasn't done today's activity yet before midnight doesn't lose it)."""
    cursor = today if today in days else date.fromordinal(today.toordinal() - 1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor = date.fromordinal(cursor.toordinal() - 1)
    return streak


def _as_date(value) -> date | None:
    """Normalize a DB-returned day value to ``date``.

    ``func.date()`` returns ``datetime.date`` on PostgreSQL but a plain
    ``"YYYY-MM-DD"`` string on SQLite; normalize so streak math works on both.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def collect_stats(db: Session) -> dict[str, int]:
    setting = db.query(SiteSetting).first()
    love_days = 0
    if setting is not None and setting.love_start_date is not None:
        start = setting.love_start_date
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        love_days = max(0, (datetime.now(timezone.utc) - start).days)

    today = date.today()

    checkin_days = {
        day
        for day in (
            _as_date(row[0])
            for row in db.query(func.date(CheckIn.created_at))
            .filter(CheckIn.deleted_at.is_(None))
            .all()
        )
        if day is not None
    }
    mood_days = {
        day
        for day in (row[0] for row in db.query(MoodCheckin.mood_date).distinct().all())
        if day is not None
    }

    return {
        "love_days": love_days,
        "articles": _count(
            db.query(func.count(Article.id)).filter(Article.deleted_at.is_(None))
        ),
        "albums": _count(
            db.query(func.count(Album.id)).filter(Album.deleted_at.is_(None))
        ),
        "moments": _count(
            db.query(func.count(Moment.id)).filter(Moment.deleted_at.is_(None))
        ),
        "capsules": _count(
            db.query(func.count(Capsule.id)).filter(Capsule.deleted_at.is_(None))
        ),
        "checkins": _count(
            db.query(func.count(CheckIn.id)).filter(CheckIn.deleted_at.is_(None))
        ),
        "checkin_streak_days": _day_streak(checkin_days, today),
        "moods": _count(db.query(func.count(MoodCheckin.id))),
        "mood_streak_days": _day_streak(mood_days, today),
        "chat_messages": _count(
            db.query(func.count(ChatMessage.id)).filter(
                ChatMessage.deleted_at.is_(None),
                ChatMessage.recalled_at.is_(None),
                ChatMessage.type != ChatMessageType.system.value,
            )
        ),
        "games_played": _count(db.query(func.count(GameMatch.id))),
        "wishes_total": _count(
            db.query(func.count(Wish.id)).filter(Wish.deleted_at.is_(None))
        ),
        "wishes_completed": _count(
            db.query(func.count(Wish.id)).filter(
                Wish.deleted_at.is_(None),
                Wish.status == WishStatus.completed.value,
            )
        ),
        "songs_played": _count(db.query(func.count(ListenHistoryEntry.id))),
        "album_media": _count(db.query(func.count(AlbumMedia.id))),
    }


def love_points(stats: dict[str, int]) -> int:
    """Weighted activity score → couple level.

    Longevity dominates early (it accrues passively), creation (articles /
    albums / capsules / wishes) is worth the most per item, high-volume
    signals (chat, songs) are damped so raw spam can't farm levels.
    """
    return (
        min(stats["love_days"], 1000) * 2
        + stats["articles"] * 15
        + stats["albums"] * 10
        + stats["moments"] * 3
        + stats["capsules"] * 8
        + stats["checkins"] * 2
        + stats["moods"] * 2
        + stats["chat_messages"] // 2
        + stats["games_played"] * 3
        + stats["wishes_completed"] * 10
        + stats["songs_played"]
    )


def couple_level(points: int) -> CoupleLevel:
    level_index = 0
    for index, (threshold, _title) in enumerate(LEVELS):
        if points >= threshold:
            level_index = index
    threshold, title = LEVELS[level_index]
    next_points, next_title = (None, None)
    if level_index + 1 < len(LEVELS):
        next_points, next_title = LEVELS[level_index + 1]
    if next_points is None:
        progress = 100
    else:
        span = next_points - threshold
        progress = 0 if span <= 0 else min(100, round((points - threshold) * 100 / span))
    return CoupleLevel(
        level=level_index + 1,
        title=title,
        points=points,
        next_level_points=next_points,
        next_level_title=next_title,
        progress_percent=progress,
    )


def badge_progresses(stats: dict[str, int]) -> list[BadgeProgress]:
    items: list[BadgeProgress] = []
    for badge in BADGES:
        current = int(stats.get(badge.stat, 0))
        achieved_tier = "none"
        next_target: int | None = None
        for tier_name, target in zip(TIER_NAMES, badge.thresholds):
            if current >= target:
                achieved_tier = tier_name
            elif next_target is None:
                next_target = target
        items.append(
            BadgeProgress(
                code=badge.code,
                name=badge.name,
                description=badge.describe(next_target if next_target is not None else badge.thresholds[-1]),
                icon=badge.icon,
                category=badge.category,
                tier=achieved_tier,
                achieved=achieved_tier != "none",
                current=current,
                next_target=next_target,
            )
        )
    return items


def build_achievements_response(db: Session) -> AchievementsResponse:
    stats = collect_stats(db)
    return AchievementsResponse(
        generated_at=datetime.now(timezone.utc),
        stats=stats,
        level=couple_level(love_points(stats)),
        badges=badge_progresses(stats),
    )
