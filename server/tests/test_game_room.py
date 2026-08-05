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

"""Tests for the generic Redis-backed GameRoom layer.

Uses a tiny in-memory fake Redis (the real client only matters in production),
so these run without a Redis server. Covers both games to prove the engine is
fully decoupled from the room/seat/turn bookkeeping.
"""
import time
import unittest

from redis.exceptions import RedisError

from app.services.cottage_games import gomoku, reversi, room, tictactoe
from app.services.cottage_games.common import IllegalMove


class FakeRedis:
    """Minimal subset of the redis-py API used by GameRoom (decode_responses
    semantics: stored/returned values are plain ``str``)."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._expiry: dict[str, float] = {}

    def _expired(self, key: str) -> bool:
        exp = self._expiry.get(key)
        if exp is not None and time.monotonic() >= exp:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return True
        return False

    def get(self, key):
        if self._expired(key):
            return None
        return self._store.get(key)

    def set(self, key, value, nx=False, px=None):
        if nx:
            if not self._expired(key) and key in self._store:
                return None
        self._store[key] = str(value)
        if px is not None:
            self._expiry[key] = time.monotonic() + (px / 1000)
        else:
            self._expiry.pop(key, None)
        return True

    def delete(self, key):
        self._store.pop(key, None)
        self._expiry.pop(key, None)
        return 1


class BoomRedis:
    """Every command raises, to exercise the RoomUnavailable degradation."""

    def get(self, *_a, **_k):
        raise RedisError("down")

    def set(self, *_a, **_k):
        raise RedisError("down")

    def delete(self, *_a, **_k):
        raise RedisError("down")


A = "uid-a"
B = "uid-b"


class GomokuRoomTests(unittest.TestCase):
    def setUp(self):
        self.r = FakeRedis()
        self.room = room.GameRoom(gomoku, "gomoku")

    def test_empty_snapshot_is_waiting(self):
        snap = self.room.get_snapshot(self.r)
        self.assertEqual(snap["phase"], "waiting")
        self.assertEqual(snap["game_key"], "gomoku")
        self.assertEqual(snap["size"], 15)
        self.assertIsNone(snap["turn_uid"])

    def test_new_game_seats_requester_black(self):
        snap = self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        self.assertEqual(snap["phase"], "playing")
        self.assertEqual(snap["black_uid"], A)
        self.assertEqual(snap["white_uid"], B)
        self.assertEqual(snap["turn_uid"], A)  # black moves first

    def test_new_game_alternates_colors(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        snap2 = self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        self.assertEqual(snap2["black_uid"], B)  # colors swapped
        self.assertEqual(snap2["white_uid"], A)

    def test_move_turn_enforced(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        # White (B) cannot move first.
        with self.assertRaises(IllegalMove):
            self.room.apply_move(self.r, uid=B, x=0, y=0)
        snap = self.room.apply_move(self.r, uid=A, x=0, y=0)
        self.assertEqual(snap["turn_uid"], B)
        self.assertEqual(snap["move_count"], 1)

    def test_non_player_cannot_move(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        with self.assertRaises(IllegalMove):
            self.room.apply_move(self.r, uid="stranger", x=5, y=5)

    def test_full_game_black_wins(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        # Black plays a horizontal five on row 0; white plays harmlessly on row 5.
        for i in range(4):
            self.room.apply_move(self.r, uid=A, x=i, y=0)
            self.room.apply_move(self.r, uid=B, x=i, y=5)
        snap = self.room.apply_move(self.r, uid=A, x=4, y=0)
        self.assertEqual(snap["phase"], "finished")
        self.assertEqual(snap["winner"], "black")
        self.assertEqual(snap["end_reason"], "five")
        self.assertEqual(len(snap["win_line"]), 5)

    def test_surrender_gives_opponent_win(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        snap = self.room.surrender(self.r, uid=A)  # A (black) resigns
        self.assertEqual(snap["phase"], "finished")
        self.assertEqual(snap["winner"], "white")
        self.assertEqual(snap["end_reason"], "surrender")

    def test_requires_two_players(self):
        with self.assertRaises(IllegalMove):
            self.room.new_game(self.r, requester_uid=A, partner_uid=A)


class TicTacToeRoomTests(unittest.TestCase):
    def setUp(self):
        self.r = FakeRedis()
        self.room = room.GameRoom(tictactoe, "tictactoe")

    def test_new_game_is_3x3(self):
        snap = self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        self.assertEqual(snap["game_key"], "tictactoe")
        self.assertEqual(snap["size"], 3)
        self.assertEqual(len(snap["cells"]), 9)
        self.assertEqual(snap["turn_uid"], A)

    def test_black_top_row_win(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        self.room.apply_move(self.r, uid=A, x=0, y=0)
        self.room.apply_move(self.r, uid=B, x=0, y=1)
        self.room.apply_move(self.r, uid=A, x=1, y=0)
        self.room.apply_move(self.r, uid=B, x=1, y=1)
        snap = self.room.apply_move(self.r, uid=A, x=2, y=0)
        self.assertEqual(snap["phase"], "finished")
        self.assertEqual(snap["winner"], "black")
        self.assertEqual(len(snap["win_line"]), 3)

    def test_isolated_namespace(self):
        # Two rooms must not clobber each other's Redis key.
        g = room.GameRoom(gomoku, "gomoku")
        t = room.GameRoom(tictactoe, "tictactoe")
        g.new_game(self.r, requester_uid=A, partner_uid=B)
        t.new_game(self.r, requester_uid=B, partner_uid=A)
        self.assertEqual(g.get_snapshot(self.r)["size"], 15)
        self.assertEqual(t.get_snapshot(self.r)["size"], 3)


class ReversiRoomTests(unittest.TestCase):
    def setUp(self):
        self.r = FakeRedis()
        self.room = room.GameRoom(reversi, "reversi")

    def test_new_game_snapshot(self):
        snap = self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        self.assertEqual(snap["game_key"], "reversi")
        self.assertEqual(snap["size"], 8)
        self.assertEqual(len(snap["cells"]), 64)
        self.assertEqual(snap["turn_uid"], A)
        # The opening position offers Black exactly four legal placements.
        self.assertEqual(len(snap["legal_moves"]), 4)

    def test_move_flips_and_passes_turn(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        snap = self.room.apply_move(self.r, uid=A, x=3, y=2)
        self.assertEqual(snap["turn_uid"], B)  # white to move
        self.assertEqual(snap["last_move"], {"x": 3, "y": 2, "color": 1})

    def test_illegal_move_rejected(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        with self.assertRaises(IllegalMove):
            self.room.apply_move(self.r, uid=A, x=0, y=0)  # no bracket

    def test_surrender_sets_reason(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        snap = self.room.surrender(self.r, uid=A)
        self.assertEqual(snap["winner"], "white")
        self.assertEqual(snap["end_reason"], "surrender")


class UndoTests(unittest.TestCase):
    def setUp(self):
        self.r = FakeRedis()
        self.room = room.GameRoom(gomoku, "gomoku")

    def test_request_then_accept_reverts(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        self.room.apply_move(self.r, uid=A, x=7, y=7)
        snap = self.room.request_undo(self.r, uid=A)
        self.assertEqual(snap["undo_request_by"], A)
        snap = self.room.respond_undo(self.r, uid=B, accept=True)
        self.assertIsNone(snap["undo_request_by"])
        self.assertEqual(snap["move_count"], 0)
        self.assertEqual(snap["turn_uid"], A)  # requester moves again
        self.assertTrue(all(c == 0 for c in snap["cells"]))

    def test_request_then_reject_keeps_board(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        self.room.apply_move(self.r, uid=A, x=7, y=7)
        self.room.request_undo(self.r, uid=A)
        snap = self.room.respond_undo(self.r, uid=B, accept=False)
        self.assertIsNone(snap["undo_request_by"])
        self.assertEqual(snap["move_count"], 1)
        self.assertEqual(snap["turn_uid"], B)

    def test_only_last_mover_can_request(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        self.room.apply_move(self.r, uid=A, x=7, y=7)
        # It is now B's turn; the last mover was A, so B cannot request.
        with self.assertRaises(IllegalMove):
            self.room.request_undo(self.r, uid=B)

    def test_cannot_request_with_no_moves(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        with self.assertRaises(IllegalMove):
            self.room.request_undo(self.r, uid=A)

    def test_new_move_clears_pending_request(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        self.room.apply_move(self.r, uid=A, x=7, y=7)
        self.room.request_undo(self.r, uid=A)
        snap = self.room.apply_move(self.r, uid=B, x=0, y=0)
        self.assertIsNone(snap["undo_request_by"])

    def test_requester_cannot_self_respond(self):
        self.room.new_game(self.r, requester_uid=A, partner_uid=B)
        self.room.apply_move(self.r, uid=A, x=7, y=7)
        self.room.request_undo(self.r, uid=A)
        with self.assertRaises(IllegalMove):
            self.room.respond_undo(self.r, uid=A, accept=True)


class DegradationTests(unittest.TestCase):
    def test_redis_down_raises_room_unavailable(self):
        gr = room.GameRoom(gomoku, "gomoku")
        with self.assertRaises(room.RoomUnavailable):
            gr.get_snapshot(BoomRedis())


class BackCompatTests(unittest.TestCase):
    """The original module-level gomoku helpers must still work."""

    def test_module_level_delegates(self):
        r = FakeRedis()
        snap = room.new_game(r, requester_uid=A, partner_uid=B)
        self.assertEqual(snap["black_uid"], A)
        snap = room.apply_move(r, uid=A, x=7, y=7)
        self.assertEqual(snap["move_count"], 1)
        self.assertEqual(room.get_snapshot(r)["turn_uid"], B)


if __name__ == "__main__":
    unittest.main()
