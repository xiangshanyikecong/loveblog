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

"""Unit tests for the 你画我猜 (draw & guess) room logic.

Uses a tiny in-memory Redis stand-in (only the few ops ``DrawRoom`` needs) so
the round flow, scoring, drawer rotation and finish/winner logic are exercised
without a live Redis.
"""

from __future__ import annotations

import time
import unittest

from app.services.cottage_games import draw
from app.services.cottage_games.common import IllegalMove


class FakeRedis:
    """Minimal Redis: get / set (nx, px, ex) / delete over a dict."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, nx=False, px=None, ex=None):
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    def delete(self, *keys):
        for k in keys:
            self._store.pop(k, None)
        return True


class DrawRoomTests(unittest.TestCase):
    def setUp(self) -> None:
        self.r = FakeRedis()
        self.room = draw.DrawRoom()
        self.a = "uid-a"
        self.b = "uid-b"

    def test_new_game_starts_first_round_with_requester_drawing(self) -> None:
        snap = self.room.new_game(self.r, requester_uid=self.a, partner_uid=self.b, total_rounds=4)
        self.assertEqual(snap["phase"], draw.PHASE_DRAWING)
        self.assertEqual(snap["drawer_uid"], self.a)
        self.assertEqual(snap["round"], 1)
        self.assertEqual(snap["total_rounds"], 4)
        # The answer is never in the broadcast snapshot mid-round…
        self.assertIsNone(snap["revealed_word"])
        self.assertGreater(snap["word_len"], 0)
        # …but the drawer can fetch it privately.
        self.assertTrue(self.room.current_word(self.r))

    def test_drawer_cannot_guess(self) -> None:
        self.room.new_game(self.r, requester_uid=self.a, partner_uid=self.b)
        with self.assertRaises(IllegalMove):
            self.room.record_guess(self.r, uid=self.a, text="whatever")

    def test_correct_guess_scores_and_ends_round(self) -> None:
        self.room.new_game(self.r, requester_uid=self.a, partner_uid=self.b)
        word = self.room.current_word(self.r)
        snap, correct = self.room.record_guess(self.r, uid=self.b, text=word)
        self.assertTrue(correct)
        self.assertEqual(snap["phase"], draw.PHASE_ROUND_END)
        self.assertEqual(snap["round_winner_uid"], self.b)
        self.assertEqual(snap["revealed_word"], word)
        # Guesser earns points, drawer earns the fixed reward.
        self.assertGreater(snap["scores"][self.b], 0)
        self.assertEqual(snap["scores"][self.a], draw.DRAWER_POINTS)

    def test_wrong_guess_keeps_round_going(self) -> None:
        self.room.new_game(self.r, requester_uid=self.a, partner_uid=self.b)
        word = self.room.current_word(self.r)
        wrong = "definitely-not-" + (word or "x")
        snap, correct = self.room.record_guess(self.r, uid=self.b, text=wrong)
        self.assertFalse(correct)
        self.assertEqual(snap["phase"], draw.PHASE_DRAWING)
        self.assertIsNone(snap["revealed_word"])

    def test_next_round_swaps_drawer(self) -> None:
        self.room.new_game(self.r, requester_uid=self.a, partner_uid=self.b, total_rounds=4)
        word = self.room.current_word(self.r)
        self.room.record_guess(self.r, uid=self.b, text=word)
        snap = self.room.next_round(self.r, uid=self.a)
        self.assertEqual(snap["phase"], draw.PHASE_DRAWING)
        self.assertEqual(snap["round"], 2)
        self.assertEqual(snap["drawer_uid"], self.b)  # swapped

    def test_game_finishes_after_last_round_with_winner(self) -> None:
        self.room.new_game(self.r, requester_uid=self.a, partner_uid=self.b, total_rounds=2)
        # Round 1: b guesses (b + a both score)
        w1 = self.room.current_word(self.r)
        self.room.record_guess(self.r, uid=self.b, text=w1)
        self.room.next_round(self.r, uid=self.a)  # -> round 2, drawer = b
        # Round 2: a guesses
        w2 = self.room.current_word(self.r)
        self.room.record_guess(self.r, uid=self.a, text=w2)
        final = self.room.next_round(self.r, uid=self.b)
        self.assertEqual(final["phase"], draw.PHASE_FINISHED)
        self.assertIn(final["winner_uid"], (self.a, self.b, None))
        # Word is cleared once finished.
        self.assertIsNone(self.room.current_word(self.r))

    def test_timeout_requires_elapsed_deadline(self) -> None:
        self.room.new_game(self.r, requester_uid=self.a, partner_uid=self.b)
        with self.assertRaises(IllegalMove):
            self.room.timeout_round(self.r, uid=self.a)  # deadline not reached

    def test_timeout_ends_round_after_deadline(self) -> None:
        self.room.new_game(self.r, requester_uid=self.a, partner_uid=self.b, round_duration_sec=30)
        # Force the deadline into the past.
        data = self.room.load(self.r)
        data["round_deadline_ms"] = int(time.time() * 1000) - 1000
        self.room._save_raw(self.r, data)
        snap = self.room.timeout_round(self.r, uid=self.a)
        self.assertEqual(snap["phase"], draw.PHASE_ROUND_END)
        self.assertIsNone(snap["round_winner_uid"])
        self.assertTrue(snap["revealed_word"])


if __name__ == "__main__":
    unittest.main()
