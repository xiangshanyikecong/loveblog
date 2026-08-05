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

"""Unit tests for the pure Gomoku rules engine (no Redis / FastAPI needed)."""
import unittest

from app.services.cottage_games import gomoku
from app.services.cottage_games.gomoku import BLACK, EMPTY, WHITE, IllegalMove


def _blank(size: int) -> dict:
    """Construct a board dict directly (bypassing normalize_size) so tests can
    use tiny boards for deterministic draw scenarios."""
    return {
        "size": size,
        "cells": [EMPTY] * (size * size),
        "turn": BLACK,
        "phase": gomoku.PHASE_PLAYING,
        "winner": EMPTY,
        "win_line": [],
        "last_move": None,
        "move_count": 0,
    }


class NewBoardTests(unittest.TestCase):
    def test_defaults(self):
        board = gomoku.new_board()
        self.assertEqual(board["size"], 15)
        self.assertEqual(len(board["cells"]), 225)
        self.assertEqual(board["turn"], BLACK)
        self.assertEqual(board["phase"], "playing")
        self.assertEqual(board["move_count"], 0)

    def test_size_clamped(self):
        # Out-of-range sizes fall back to the default.
        self.assertEqual(gomoku.new_board(3)["size"], 15)
        self.assertEqual(gomoku.new_board(99)["size"], 15)
        self.assertEqual(gomoku.new_board(19)["size"], 19)
        self.assertEqual(gomoku.normalize_size("abc"), 15)


class MoveTests(unittest.TestCase):
    def test_basic_move_and_turn_switch(self):
        board = gomoku.new_board()
        gomoku.apply_move(board, BLACK, 7, 7)
        self.assertEqual(gomoku.cell_at(board, 7, 7), BLACK)
        self.assertEqual(board["turn"], WHITE)
        self.assertEqual(board["move_count"], 1)
        self.assertEqual(board["last_move"], {"x": 7, "y": 7, "color": BLACK})

    def test_reject_occupied(self):
        board = gomoku.new_board()
        gomoku.apply_move(board, BLACK, 5, 5)
        with self.assertRaises(IllegalMove):
            gomoku.apply_move(board, WHITE, 5, 5)

    def test_reject_wrong_turn(self):
        board = gomoku.new_board()
        with self.assertRaises(IllegalMove):
            gomoku.apply_move(board, WHITE, 0, 0)  # Black moves first

    def test_reject_out_of_bounds(self):
        board = gomoku.new_board()
        with self.assertRaises(IllegalMove):
            gomoku.apply_move(board, BLACK, 15, 0)
        with self.assertRaises(IllegalMove):
            gomoku.apply_move(board, BLACK, -1, 0)

    def test_reject_bool_coords(self):
        board = gomoku.new_board()
        with self.assertRaises(IllegalMove):
            gomoku.apply_move(board, BLACK, True, 0)

    def test_reject_move_after_finished(self):
        board = gomoku.new_board()
        # Black plays (0,0)..(4,0); White plays a harmless column far away.
        for i in range(4):
            gomoku.apply_move(board, BLACK, i, 0)
            gomoku.apply_move(board, WHITE, i, 5)
        gomoku.apply_move(board, BLACK, 4, 0)  # winning 5th
        self.assertEqual(board["phase"], "finished")
        with self.assertRaises(IllegalMove):
            gomoku.apply_move(board, WHITE, 6, 6)


class WinTests(unittest.TestCase):
    def _play_five_in_row(self, coords):
        board = gomoku.new_board()
        bx, by = coords[0]
        for i in range(4):
            gomoku.apply_move(board, BLACK, *coords[i])
            gomoku.apply_move(board, WHITE, 10 + i, 14)  # decoy white moves
        gomoku.apply_move(board, BLACK, *coords[4])
        return board

    def test_horizontal_win(self):
        board = self._play_five_in_row([(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)])
        self.assertEqual(board["phase"], "finished")
        self.assertEqual(board["winner"], BLACK)
        self.assertEqual(len(board["win_line"]), 5)

    def test_vertical_win(self):
        board = self._play_five_in_row([(2, 0), (2, 1), (2, 2), (2, 3), (2, 4)])
        self.assertEqual(board["winner"], BLACK)

    def test_diagonal_win(self):
        board = self._play_five_in_row([(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)])
        self.assertEqual(board["winner"], BLACK)

    def test_anti_diagonal_win(self):
        board = self._play_five_in_row([(0, 4), (1, 3), (2, 2), (3, 1), (4, 0)])
        self.assertEqual(board["winner"], BLACK)

    def test_no_win_with_four(self):
        board = gomoku.new_board()
        for i in range(4):
            gomoku.apply_move(board, BLACK, i, 0)
            gomoku.apply_move(board, WHITE, i, 5)
        self.assertEqual(board["phase"], "playing")
        self.assertEqual(board["winner"], EMPTY)


class DrawTests(unittest.TestCase):
    def test_full_4x4_is_draw(self):
        # On a 4x4 board five-in-a-row is impossible, so a full board draws.
        board = _blank(4)
        for y in range(4):
            for x in range(4):
                gomoku.apply_move(board, board["turn"], x, y)
        self.assertEqual(board["phase"], "finished")
        self.assertEqual(board["winner"], "draw")
        self.assertEqual(board["move_count"], 16)


class HelperTests(unittest.TestCase):
    def test_color_name(self):
        self.assertEqual(gomoku.color_name(BLACK), "black")
        self.assertEqual(gomoku.color_name(WHITE), "white")
        self.assertEqual(gomoku.color_name("draw"), "draw")
        self.assertIsNone(gomoku.color_name(EMPTY))

    def test_opponent(self):
        self.assertEqual(gomoku.opponent(BLACK), WHITE)
        self.assertEqual(gomoku.opponent(WHITE), BLACK)

    def test_force_winner(self):
        board = gomoku.new_board()
        gomoku.force_winner(board, WHITE)
        self.assertEqual(board["phase"], "finished")
        self.assertEqual(board["winner"], WHITE)


if __name__ == "__main__":
    unittest.main()
