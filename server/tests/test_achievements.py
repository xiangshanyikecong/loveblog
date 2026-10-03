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

"""Tests for the couple achievements / level system (小屋·成就/等级)."""
import unittest
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401 — register tables on Base.metadata
    Article,
    Capsule,
    ChatMessage,
    CheckIn,
    GameMatch,
    MoodCheckin,
    SiteSetting,
    User,
    Wish,
)
from app.models.user import UserRole
from app.api.v1.cottage_achievements import achievements_overview
from app.services.achievements import (
    _day_streak,
    collect_stats,
    couple_level,
    love_points,
)


class AchievementsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.a = self._partner("alice", UserRole.partner_a)
        self.b = self._partner("bob", UserRole.partner_b)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    # ── helpers ────────────────────────────────────────────────────────────

    def _partner(self, username: str, role: UserRole) -> User:
        user = User(username=username, nickname=username, role=role, password_hash="hash")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    # ── pure logic ─────────────────────────────────────────────────────────

    def test_day_streak_tolerates_today_gap(self) -> None:
        today = date(2026, 10, 3)
        days = {today - timedelta(days=1), today - timedelta(days=2)}
        self.assertEqual(_day_streak(days, today), 2)
        # Today present extends it.
        self.assertEqual(_day_streak(days | {today}, today), 3)
        # Two-day gap breaks it entirely.
        self.assertEqual(
            _day_streak({today - timedelta(days=3)}, today), 0
        )

    def test_level_progression(self) -> None:
        level = couple_level(0)
        self.assertEqual((level.level, level.title), (1, "初识"))
        self.assertEqual(level.progress_percent, 0)

        level = couple_level(150)
        self.assertEqual((level.level, level.title), (2, "心动"))
        self.assertEqual(level.next_level_title, "怦然")
        self.assertEqual(level.progress_percent, 25)  # 100→300 span

        level = couple_level(99999)
        self.assertEqual(level.title, "白首不离")
        self.assertIsNone(level.next_level_points)
        self.assertEqual(level.progress_percent, 100)

    def test_points_damp_high_volume_signals(self) -> None:
        stats = collect_stats(self.db)  # all-zero except structural keys
        zero = love_points(stats)
        self.assertEqual(zero, 0)
        stats.update(chat_messages=999)
        self.assertEqual(love_points(stats), 999 // 2)

    # ── stats + badges against seeded data ─────────────────────────────────

    def test_collect_stats_and_badge_tiers(self) -> None:
        today = date.today()
        now = datetime.now(timezone.utc)
        self.db.add(
            SiteSetting(love_start_date=now - timedelta(days=400))
        )

        # 12 articles → writer silver (10), next gold at 50.
        for index in range(12):
            self.db.add(Article(author_id=self.a.id, title=f"日记 {index}"))

        # Moods today / yesterday / 2 days ago (both partners) → streak 3.
        for offset in range(3):
            self.db.add(
                MoodCheckin(author_id=self.a.id, mood_date=today - timedelta(days=offset), mood="happy")
            )
        self.db.add(
            MoodCheckin(author_id=self.b.id, mood_date=today, mood="loved")
        )

        # Check-ins today and yesterday → streak 2, count 2.
        for offset in range(2):
            self.db.add(
                CheckIn(
                    author_id=self.b.id,
                    location_status="omitted",
                    created_at=now - timedelta(days=offset),
                )
            )

        # 5 completed + 2 pending wishes.
        for index in range(5):
            self.db.add(
                Wish(
                    author_id=self.a.id,
                    title=f"一起去 {index}",
                    status="completed",
                    completed_at=now,
                    completed_by_id=self.a.id,
                )
            )
        for index in range(2):
            self.db.add(Wish(author_id=self.b.id, title=f"想买 {index}", status="pending"))

        # 3 game matches.
        for index in range(3):
            self.db.add(
                GameMatch(black_id=self.a.id, white_id=self.b.id, winner_id=self.a.id)
            )

        # A recalled message and a system message must not count.
        self.db.add(ChatMessage(sender_id=self.a.id, content="hi"))
        self.db.add(ChatMessage(sender_id=self.b.id, content="gone", recalled_at=now))
        self.db.add(ChatMessage(sender_id=self.b.id, content="sys", type="system"))

        self.db.commit()

        stats = collect_stats(self.db)
        self.assertEqual(stats["love_days"], 400)
        self.assertEqual(stats["articles"], 12)
        self.assertEqual(stats["moods"], 4)
        self.assertEqual(stats["mood_streak_days"], 3)
        self.assertEqual(stats["checkins"], 2)
        self.assertEqual(stats["checkin_streak_days"], 2)
        self.assertEqual(stats["wishes_completed"], 5)
        self.assertEqual(stats["wishes_total"], 7)
        self.assertEqual(stats["games_played"], 3)
        self.assertEqual(stats["chat_messages"], 1)

        response = achievements_overview(db=self.db, current_user=self.a)
        by_code = {badge.code: badge for badge in response.badges}
        self.assertEqual(by_code["writer"].tier, "silver")
        self.assertEqual(by_code["writer"].next_target, 50)
        self.assertTrue(by_code["writer"].achieved)
        self.assertEqual(by_code["mood_streak"].tier, "bronze")
        self.assertEqual(by_code["days"].tier, "silver")  # 400 days ≥ 365
        self.assertFalse(by_code["gamer"].achieved)  # 3 < 5
        self.assertEqual(by_code["gamer"].current, 3)
        self.assertEqual(len(response.badges), 11)
        # Level sanity: 800 (days) + 180 (articles) + 8 + 4 + 9 + 50 ≈ 1051 → 热恋 (Lv4).
        self.assertGreater(response.level.points, 900)
        self.assertEqual(response.level.level, 4)
        self.assertEqual(response.level.title, "热恋")

    def test_visitor_forbidden(self) -> None:
        visitor = User(
            username="guest", nickname="guest", role=UserRole.visitor, password_hash="hash"
        )
        self.db.add(visitor)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            achievements_overview(db=self.db, current_user=visitor)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
