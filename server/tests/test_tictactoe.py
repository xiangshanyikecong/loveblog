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

"""Unit tests for the pure Tic-Tac-Toe rules engine (no Redis / FastAPI)."""
import unittest

from app.services.cottage_games import tictactoe
from app.services.cottage_games.common import IllegalMove
from app.services.cottage_games.tictactoe import BLACK, EMPTY, WHITE


class NewBoardTests(unittest.TestCase):
    def test_defaults(self):
        board = tictactoe.new_board()
        self.assertEqual(board["size"], 3)
        self.assertEqual(len(board["cells"]), 9)
        self.assertEqual(board["turn"], BLACK)
        self.assertEqual(board["phase"], "playing")
        self.assertEqual(board["move_count"], 0)

    def test_size_is_fixed(self):
        # Tic-tac-toe ignores any requested size — always 3×3.
        self.assertEqual(tictactoe.new_board(15)["size"], 3)
        self.assertEqual(tictactoe.normalize_size(99), 3)
        self.assertEqual(tictactoe.normalize_size("abc"), 3)


class MoveTests(unittest.TestCase):
    def test_basic_move_and_turn_switch(self):
        board = tictactoe.new_board()
        tictactoe.apply_move(board, BLACK, 1, 1)
        self.assertEqual(tictactoe.cell_at(board, 1, 1), BLACK)
        self.assertEqual(board["turn"], WHITE)
        self.assertEqual(board["last_move"], {"x": 1, "y": 1, "color": BLACK})

    def test_reject_occupied(self):
        board = tictactoe.new_board()
        tictactoe.apply_move(board, BLACK, 0, 0)
        with self.assertRaises(IllegalMove):
            tictactoe.apply_move(board, WHITE, 0, 0)

    def test_reject_wrong_turn(self):
        board = tictactoe.new_board()
        with self.assertRaises(IllegalMove):
            tictactoe.apply_move(board, WHITE, 0, 0)  # Black moves first

    def test_reject_out_of_bounds(self):
        board = tictactoe.new_board()
        with self.assertRaises(IllegalMove):
            tictactoe.apply_move(board, BLACK, 3, 0)
        with self.assertRaises(IllegalMove):
            tictactoe.apply_move(board, BLACK, -1, 0)

    def test_reject_bool_coords(self):
        board = tictactoe.new_board()
        with self.assertRaises(IllegalMove):
            tictactoe.apply_move(board, BLACK, True, 0)


class WinTests(unittest.TestCase):
    def test_horizontal_win(self):
        board = tictactoe.new_board()
        # B(0,0) W(0,1) B(1,0) W(1,1) B(2,0) -> top row for black
        tictactoe.apply_move(board, BLACK, 0, 0)
        tictactoe.apply_move(board, WHITE, 0, 1)
        tictactoe.apply_move(board, BLACK, 1, 0)
        tictactoe.apply_move(board, WHITE, 1, 1)
        tictactoe.apply_move(board, BLACK, 2, 0)
        self.assertEqual(board["phase"], "finished")
        self.assertEqual(board["winner"], BLACK)
        self.assertEqual(len(board["win_line"]), 3)

    def test_diagonal_win(self):
        board = tictactoe.new_board()
        tictactoe.apply_move(board, BLACK, 0, 0)
        tictactoe.apply_move(board, WHITE, 1, 0)
        tictactoe.apply_move(board, BLACK, 1, 1)
        tictactoe.apply_move(board, WHITE, 2, 0)
        tictactoe.apply_move(board, BLACK, 2, 2)
        self.assertEqual(board["winner"], BLACK)

    def test_no_win_after_finished(self):
        board = tictactoe.new_board()
        tictactoe.apply_move(board, BLACK, 0, 0)
        tictactoe.apply_move(board, WHITE, 0, 1)
        tictactoe.apply_move(board, BLACK, 1, 0)
        tictactoe.apply_move(board, WHITE, 1, 1)
        tictactoe.apply_move(board, BLACK, 2, 0)  # black wins
        with self.assertRaises(IllegalMove):
            tictactoe.apply_move(board, WHITE, 2, 2)


class DrawTests(unittest.TestCase):
    def test_full_board_draw(self):
        # A classic cat's game:
        #  B W B
        #  B W W
        #  W B B
        board = tictactoe.new_board()
        moves = [
            (BLACK, 0, 0), (WHITE, 1, 0), (BLACK, 2, 0),
            (WHITE, 1, 1), (BLACK, 0, 1), (WHITE, 2, 1),
            (BLACK, 1, 2), (WHITE, 0, 2), (BLACK, 2, 2),
        ]
        for color, x, y in moves:
            tictactoe.apply_move(board, color, x, y)
        self.assertEqual(board["phase"], "finished")
        self.assertEqual(board["winner"], "draw")
        self.assertEqual(board["move_count"], 9)


class HelperTests(unittest.TestCase):
    def test_color_name(self):
        self.assertEqual(tictactoe.color_name(BLACK), "black")
        self.assertEqual(tictactoe.color_name(WHITE), "white")
        self.assertEqual(tictactoe.color_name("draw"), "draw")
        self.assertIsNone(tictactoe.color_name(EMPTY))

    def test_opponent(self):
        self.assertEqual(tictactoe.opponent(BLACK), WHITE)
        self.assertEqual(tictactoe.opponent(WHITE), BLACK)

    def test_force_winner(self):
        board = tictactoe.new_board()
        tictactoe.force_winner(board, WHITE)
        self.assertEqual(board["phase"], "finished")
        self.assertEqual(board["winner"], WHITE)


if __name__ == "__main__":
    unittest.main()
