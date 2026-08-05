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

"""Unit tests for the pure Reversi / Othello rules engine."""
import unittest

from app.services.cottage_games import reversi
from app.services.cottage_games.common import IllegalMove
from app.services.cottage_games.reversi import BLACK, EMPTY, WHITE


def _empty_board():
    return {
        "size": 8,
        "cells": [EMPTY] * 64,
        "turn": BLACK,
        "phase": reversi.PHASE_PLAYING,
        "winner": EMPTY,
        "win_line": [],
        "last_move": None,
        "move_count": 0,
        "legal_moves": [],
    }


def _set(board, x, y, v):
    board["cells"][y * 8 + x] = v


class NewBoardTests(unittest.TestCase):
    def test_standard_opening(self):
        board = reversi.new_board()
        self.assertEqual(board["size"], 8)
        self.assertEqual(reversi.cell_at(board, 3, 3), WHITE)
        self.assertEqual(reversi.cell_at(board, 4, 4), WHITE)
        self.assertEqual(reversi.cell_at(board, 3, 4), BLACK)
        self.assertEqual(reversi.cell_at(board, 4, 3), BLACK)
        self.assertEqual(board["turn"], BLACK)
        self.assertEqual(reversi.count_discs(board), (2, 2))

    def test_initial_legal_moves(self):
        board = reversi.new_board()
        moves = {tuple(m) for m in board["legal_moves"]}
        self.assertEqual(moves, {(3, 2), (2, 3), (5, 4), (4, 5)})

    def test_size_is_fixed(self):
        self.assertEqual(reversi.normalize_size(15), 8)
        self.assertEqual(reversi.new_board(3)["size"], 8)


class MoveTests(unittest.TestCase):
    def test_opening_move_flips_and_switches(self):
        board = reversi.new_board()
        reversi.apply_move(board, BLACK, 3, 2)
        self.assertEqual(reversi.cell_at(board, 3, 2), BLACK)
        self.assertEqual(reversi.cell_at(board, 3, 3), BLACK)  # flipped
        self.assertEqual(board["turn"], WHITE)
        self.assertEqual(reversi.count_discs(board), (4, 1))

    def test_reject_non_bracketing(self):
        board = reversi.new_board()
        with self.assertRaises(IllegalMove):
            reversi.apply_move(board, BLACK, 0, 0)

    def test_reject_occupied(self):
        board = reversi.new_board()
        with self.assertRaises(IllegalMove):
            reversi.apply_move(board, BLACK, 3, 3)

    def test_reject_wrong_turn(self):
        board = reversi.new_board()
        with self.assertRaises(IllegalMove):
            reversi.apply_move(board, WHITE, 2, 4)

    def test_reject_out_of_bounds(self):
        board = reversi.new_board()
        with self.assertRaises(IllegalMove):
            reversi.apply_move(board, BLACK, 8, 0)


class PassTests(unittest.TestCase):
    def test_opponent_passes_keeps_turn(self):
        # Black at (0,0); White at (1,0) and (1,1). Black plays (2,0): flips
        # (1,0); afterwards White has no legal reply but Black does -> turn stays.
        board = _empty_board()
        _set(board, 0, 0, BLACK)
        _set(board, 1, 0, WHITE)
        _set(board, 1, 1, WHITE)
        reversi.apply_move(board, BLACK, 2, 0)
        self.assertEqual(board["phase"], "playing")
        self.assertEqual(board["turn"], BLACK)
        self.assertEqual(reversi.cell_at(board, 1, 0), BLACK)
        self.assertEqual(reversi.cell_at(board, 1, 1), WHITE)


class FinishTests(unittest.TestCase):
    def test_full_board_counts_winner(self):
        board = _empty_board()
        for i in range(64):
            board["cells"][i] = BLACK
        _set(board, 6, 7, WHITE)
        _set(board, 7, 7, EMPTY)
        board["move_count"] = 62
        reversi.apply_move(board, BLACK, 7, 7)
        self.assertEqual(board["phase"], "finished")
        self.assertEqual(board["winner"], BLACK)
        self.assertEqual(board["end_reason"], "count")
        self.assertEqual(reversi.count_discs(board), (64, 0))

    def test_force_winner(self):
        board = reversi.new_board()
        reversi.force_winner(board, WHITE)
        self.assertEqual(board["phase"], "finished")
        self.assertEqual(board["winner"], WHITE)
        self.assertEqual(board["legal_moves"], [])


class HelperTests(unittest.TestCase):
    def test_color_name(self):
        self.assertEqual(reversi.color_name(BLACK), "black")
        self.assertEqual(reversi.color_name(WHITE), "white")
        self.assertEqual(reversi.color_name("draw"), "draw")
        self.assertIsNone(reversi.color_name(EMPTY))

    def test_opponent(self):
        self.assertEqual(reversi.opponent(BLACK), WHITE)
        self.assertEqual(reversi.opponent(WHITE), BLACK)


if __name__ == "__main__":
    unittest.main()
