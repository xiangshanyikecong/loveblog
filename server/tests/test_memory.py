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

"""Tests for memory flip-card engine."""
from app.services.cottage_games import memory


def test_memory_match_keeps_turn_and_scores() -> None:
    board = memory.new_board()
    board["tiles"] = [1, 2, 3, 1] + [4] * 12
    board["states"] = [0] * 16

    memory.apply_move(board, memory.BLACK, 0, 0)
    memory.apply_move(board, memory.BLACK, 3, 0)
    assert board["black_score"] == 1
    assert board["turn"] == memory.BLACK


def test_memory_miss_switches_turn() -> None:
    board = memory.new_board()
    board["tiles"] = [1, 2, 3, 4] + [5] * 12
    board["states"] = [0] * 16

    memory.apply_move(board, memory.BLACK, 0, 0)
    memory.apply_move(board, memory.BLACK, 1, 0)
    assert board["turn"] == memory.WHITE
    assert board["black_score"] == 0
