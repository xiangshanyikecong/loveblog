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

"""Pure Reversi / Othello (黑白棋) rules engine.

Same shape and contract as the other cottage engines (no I/O, plain
dicts/lists) so the generic Redis room layer can drive it unchanged. Two extra
wrinkles compared with gomoku/tic-tac-toe:

- A move is only legal if it *brackets* (flips) one or more opponent discs.
- A player with no legal move is skipped (a "pass"); when neither side can
  move the game ends and the majority of discs wins (tie = draw).

The engine exposes the player-to-move's legal placements as ``board["legal_moves"]``
so the client can render hints without re-implementing the flip rules. Board
encoding mirrors the other engines: ``cells`` is a flat ``list[int]`` of length
``size * size`` indexed by ``y * size + x`` with ``EMPTY`` / ``BLACK`` / ``WHITE``.
"""
from __future__ import annotations

from typing import Any

from app.services.cottage_games.common import IllegalMove

EMPTY = 0
BLACK = 1
WHITE = 2

DEFAULT_SIZE = 8

PHASE_PLAYING = "playing"
PHASE_FINISHED = "finished"

_DIRECTIONS = (
    (1, 0), (-1, 0), (0, 1), (0, -1),
    (1, 1), (1, -1), (-1, 1), (-1, -1),
)


def normalize_size(size: Any = DEFAULT_SIZE) -> int:
    # Reversi is always 8×8.
    return DEFAULT_SIZE


def in_bounds(size: int, x: int, y: int) -> bool:
    return 0 <= x < size and 0 <= y < size


def _index(size: int, x: int, y: int) -> int:
    return y * size + x


def cell_at(board: dict[str, Any], x: int, y: int) -> int:
    size = board["size"]
    if not in_bounds(size, x, y):
        return EMPTY
    return board["cells"][_index(size, x, y)]


def opponent(color: int) -> int:
    return WHITE if color == BLACK else BLACK


def color_name(color: Any) -> str | None:
    if color == BLACK:
        return "black"
    if color == WHITE:
        return "white"
    if color == "draw":
        return "draw"
    return None


def new_board(size: int = DEFAULT_SIZE) -> dict[str, Any]:
    """Create the standard Othello opening position (Black to move)."""
    n = DEFAULT_SIZE
    cells = [EMPTY] * (n * n)
    c = n // 2
    cells[_index(n, c - 1, c - 1)] = WHITE
    cells[_index(n, c, c)] = WHITE
    cells[_index(n, c - 1, c)] = BLACK
    cells[_index(n, c, c - 1)] = BLACK
    board = {
        "size": n,
        "cells": cells,
        "turn": BLACK,
        "phase": PHASE_PLAYING,
        "winner": EMPTY,
        "win_line": [],
        "last_move": None,
        "move_count": 0,
    }
    board["legal_moves"] = legal_moves(board, BLACK)
    return board


def _coerce_coord(value: Any) -> int:
    if isinstance(value, bool):  # bool is an int subclass — reject explicitly
        raise IllegalMove("坐标不合法")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise IllegalMove("坐标不合法") from exc


def _flips_for(board: dict[str, Any], color: int, x: int, y: int) -> list[list[int]]:
    """Discs that would be flipped by placing ``color`` at ``(x, y)`` ([] if illegal)."""
    size = board["size"]
    cells = board["cells"]
    if not in_bounds(size, x, y) or cells[_index(size, x, y)] != EMPTY:
        return []
    opp = opponent(color)
    flips: list[list[int]] = []
    for dx, dy in _DIRECTIONS:
        line: list[list[int]] = []
        nx, ny = x + dx, y + dy
        while in_bounds(size, nx, ny) and cells[_index(size, nx, ny)] == opp:
            line.append([nx, ny])
            nx, ny = nx + dx, ny + dy
        if line and in_bounds(size, nx, ny) and cells[_index(size, nx, ny)] == color:
            flips.extend(line)
    return flips


def legal_moves(board: dict[str, Any], color: int) -> list[list[int]]:
    """All empty cells where ``color`` could legally place a disc."""
    size = board["size"]
    out: list[list[int]] = []
    for y in range(size):
        for x in range(size):
            if board["cells"][_index(size, x, y)] == EMPTY and _flips_for(board, color, x, y):
                out.append([x, y])
    return out


def count_discs(board: dict[str, Any]) -> tuple[int, int]:
    """Return ``(black, white)`` disc counts."""
    black = sum(1 for v in board["cells"] if v == BLACK)
    white = sum(1 for v in board["cells"] if v == WHITE)
    return black, white


def _finish(board: dict[str, Any]) -> None:
    black, white = count_discs(board)
    if black > white:
        board["winner"] = BLACK
    elif white > black:
        board["winner"] = WHITE
    else:
        board["winner"] = "draw"
    board["phase"] = PHASE_FINISHED
    board["end_reason"] = "count"
    board["win_line"] = []
    board["legal_moves"] = []


def apply_move(board: dict[str, Any], color: int, x: Any, y: Any) -> dict[str, Any]:
    """Place ``color`` at ``(x, y)`` (flipping brackets), mutate and return board.

    Handles the automatic pass: if after the move the opponent has no legal
    reply but the mover does, it stays the mover's turn. If neither can move the
    game ends with the disc majority winning.
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
    if board["cells"][_index(size, x, y)] != EMPTY:
        raise IllegalMove("该位置已经有棋子了")

    flips = _flips_for(board, color, x, y)
    if not flips:
        raise IllegalMove("这里夹不到对方的子，不能落子")

    board["cells"][_index(size, x, y)] = color
    for fx, fy in flips:
        board["cells"][_index(size, fx, fy)] = color
    board["last_move"] = {"x": x, "y": y, "color": color}
    board["move_count"] += 1

    opp = opponent(color)
    if legal_moves(board, opp):
        board["turn"] = opp
    elif legal_moves(board, color):
        board["turn"] = color  # opponent has to pass
    else:
        _finish(board)
        return board

    board["legal_moves"] = legal_moves(board, board["turn"])
    return board


def force_winner(board: dict[str, Any], color: int) -> dict[str, Any]:
    """End the game immediately with ``color`` as winner (e.g. surrender)."""
    board["phase"] = PHASE_FINISHED
    board["winner"] = color
    board["win_line"] = []
    board["legal_moves"] = []
    return board
