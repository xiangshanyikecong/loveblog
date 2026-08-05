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

"""Pure Gomoku (五子棋) rules engine.

No I/O, no framework imports — just functions over plain dicts/lists so the
whole thing is trivially unit-testable and deterministic. The Redis room layer
(:mod:`app.services.cottage_games.room`) is the only caller that adds state
persistence and player/seat bookkeeping on top of this.

Board encoding
--------------
- ``cells`` is a flat ``list[int]`` of length ``size * size`` indexed by
  ``y * size + x`` (row-major), with values ``EMPTY`` / ``BLACK`` / ``WHITE``.
- ``turn`` / ``winner`` are kept as ints internally; the room layer converts
  them to the ``"black"`` / ``"white"`` / ``"draw"`` strings used on the wire.

Rules: free-style Gomoku — first player to get five (or more) in a row in any
of the four directions wins. Black moves first. No overline / forbidden-move
restrictions (keeps it friendly for a couple).
"""
from __future__ import annotations

from typing import Any

from app.services.cottage_games.common import IllegalMove

EMPTY = 0
BLACK = 1
WHITE = 2

DEFAULT_SIZE = 15
MIN_SIZE = 9
MAX_SIZE = 19
WIN_COUNT = 5

# Phase values for a board.
PHASE_PLAYING = "playing"
PHASE_FINISHED = "finished"

# Four scan directions (the opposite directions are covered by scanning both
# ways from the last move): horizontal, vertical, and the two diagonals.
_DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1))


def normalize_size(size: Any) -> int:
    try:
        size = int(size)
    except (TypeError, ValueError):
        return DEFAULT_SIZE
    if size < MIN_SIZE or size > MAX_SIZE:
        return DEFAULT_SIZE
    return size


def new_board(size: int = DEFAULT_SIZE) -> dict[str, Any]:
    """Create a fresh, empty board with Black to move."""
    size = normalize_size(size)
    return {
        "size": size,
        "cells": [EMPTY] * (size * size),
        "turn": BLACK,
        "phase": PHASE_PLAYING,
        "winner": EMPTY,  # EMPTY=none, BLACK/WHITE=winner, "draw" set as string
        "win_line": [],
        "last_move": None,
        "move_count": 0,
    }


def in_bounds(size: int, x: int, y: int) -> bool:
    return 0 <= x < size and 0 <= y < size


def _index(size: int, x: int, y: int) -> int:
    return y * size + x


def cell_at(board: dict[str, Any], x: int, y: int) -> int:
    size = board["size"]
    if not in_bounds(size, x, y):
        return EMPTY
    return board["cells"][_index(size, x, y)]


def _coerce_coord(value: Any) -> int:
    if isinstance(value, bool):  # bool is an int subclass — reject explicitly
        raise IllegalMove("坐标不合法")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise IllegalMove("坐标不合法") from exc


def apply_move(board: dict[str, Any], color: int, x: Any, y: Any) -> dict[str, Any]:
    """Place ``color`` at ``(x, y)``, mutating and returning ``board``.

    Raises :class:`IllegalMove` if the board is finished, it is not ``color``'s
    turn, the coordinates are out of bounds, or the cell is occupied.
    """
    if board.get("phase") != PHASE_PLAYING:
        raise IllegalMove("对局已结束")
    if color not in (BLACK, WHITE):
        raise IllegalMove("落子方不合法")
    if color != board["turn"]:
        raise IllegalMove("还没轮到你落子")

    x = _coerce_coord(x)
    y = _coerce_coord(y)
    size = board["size"]
    if not in_bounds(size, x, y):
        raise IllegalMove("超出棋盘范围")

    idx = _index(size, x, y)
    if board["cells"][idx] != EMPTY:
        raise IllegalMove("该位置已经有棋子了")

    board["cells"][idx] = color
    board["last_move"] = {"x": x, "y": y, "color": color}
    board["move_count"] += 1

    line = _winning_line(board, x, y, color)
    if line:
        board["phase"] = PHASE_FINISHED
        board["winner"] = color
        board["win_line"] = line
    elif board["move_count"] >= size * size:
        board["phase"] = PHASE_FINISHED
        board["winner"] = "draw"
        board["win_line"] = []
    else:
        board["turn"] = WHITE if color == BLACK else BLACK
    return board


def _winning_line(board: dict[str, Any], x: int, y: int, color: int) -> list[list[int]]:
    """Return the full contiguous run (>= 5) through ``(x, y)``, else ``[]``."""
    size = board["size"]
    cells = board["cells"]
    for dx, dy in _DIRECTIONS:
        run = [[x, y]]
        nx, ny = x + dx, y + dy
        while in_bounds(size, nx, ny) and cells[_index(size, nx, ny)] == color:
            run.append([nx, ny])
            nx, ny = nx + dx, ny + dy
        nx, ny = x - dx, y - dy
        while in_bounds(size, nx, ny) and cells[_index(size, nx, ny)] == color:
            run.insert(0, [nx, ny])
            nx, ny = nx - dx, ny - dy
        if len(run) >= WIN_COUNT:
            return run
    return []


def force_winner(board: dict[str, Any], color: int) -> dict[str, Any]:
    """End the game immediately with ``color`` as winner (e.g. surrender)."""
    board["phase"] = PHASE_FINISHED
    board["winner"] = color
    board["win_line"] = []
    return board


def color_name(color: Any) -> str | None:
    if color == BLACK:
        return "black"
    if color == WHITE:
        return "white"
    if color == "draw":
        return "draw"
    return None


def opponent(color: int) -> int:
    return WHITE if color == BLACK else BLACK
