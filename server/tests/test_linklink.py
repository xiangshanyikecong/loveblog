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

"""Tests for linklink engine."""
import pytest

from app.services.cottage_games import linklink
from app.services.cottage_games.common import IllegalMove


def test_linklink_removes_connectable_pair() -> None:
    board = linklink.new_board()
    board["cols"] = 4
    board["rows"] = 2
    board["cells"] = [1, 1, 2, 2, 3, 3, 4, 4]

    linklink.apply_move(board, linklink.BLACK, 0, 0)
    linklink.apply_move(board, linklink.BLACK, 1, 0)
    assert board["cells"][0] == 0
    assert board["cells"][1] == 0
    assert board["black_score"] == 1
    assert board["turn"] == linklink.WHITE


def test_linklink_new_board_is_solvable() -> None:
    board = linklink.new_board()
    assert linklink._is_solvable(board["cells"], board["cols"], board["rows"])


def test_linklink_rejects_unconnectable_pair() -> None:
    board = linklink.new_board()
    board["cols"] = 3
    board["rows"] = 2
    board["cells"] = [1, 2, 1, 2, 3, 3]

    linklink.apply_move(board, linklink.BLACK, 0, 0)
    try:
        linklink.apply_move(board, linklink.BLACK, 0, 1)
        raised = False
    except IllegalMove:
        raised = True
    assert raised
