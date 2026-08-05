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

"""Link Link / 连连看 rules engine.

Partners alternate removing identical, connectable tile pairs from a rectangular
grid. A pair may connect with a path of at most two right-angle bends through
empty cells (classic 连连看 rules). Most pairs cleared wins.
"""
from __future__ import annotations

import random
from typing import Any

from app.services.cottage_games.common import IllegalMove

EMPTY = 0
BLACK = 1
WHITE = 2

DEFAULT_COLS = 8
DEFAULT_ROWS = 6
# The generic room layer / WS handler read ``engine.DEFAULT_SIZE`` (e.g. as the
# default for ``board.get("size", engine.DEFAULT_SIZE)`` and ``normalize_size``).
# Link Link is a fixed rectangular board, so we alias it to the column count;
# omitting it makes every linklink snapshot/new-game raise AttributeError.
DEFAULT_SIZE = DEFAULT_COLS
PAIR_COUNT = 24  # DEFAULT_COLS * DEFAULT_ROWS // 2

PHASE_PLAYING = "playing"
PHASE_FINISHED = "finished"


def normalize_size(size: Any = DEFAULT_COLS) -> int:
    return DEFAULT_COLS


def _coerce_coord(value: Any) -> int:
    if isinstance(value, bool):
        raise IllegalMove("坐标不合法")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise IllegalMove("坐标不合法") from exc


def _index(cols: int, x: int, y: int) -> int:
    return y * cols + x


def _board_dict(cells: list[int], cols: int, rows: int) -> dict[str, Any]:
    return {"cols": cols, "rows": rows, "cells": cells}


def _is_solvable(cells: list[int], cols: int, rows: int) -> bool:
    """Backtracking check: every tile pair can be cleared under link rules."""
    cells = list(cells)

    def solve() -> bool:
        if all(v == EMPTY for v in cells):
            return True
        for i, value in enumerate(cells):
            if value == EMPTY:
                continue
            x1, y1 = i % cols, i // cols
            for j in range(i + 1, len(cells)):
                if cells[j] != value:
                    continue
                x2, y2 = j % cols, j // cols
                if not _can_connect(_board_dict(cells, cols, rows), x1, y1, x2, y2):
                    continue
                cells[i] = EMPTY
                cells[j] = EMPTY
                if solve():
                    return True
                cells[i] = value
                cells[j] = value
            return False
        return True

    return solve()


def _generate_solvable_tiles(cols: int, rows: int, pair_count: int) -> list[int]:
    """Shuffle until solvable; fall back to a deterministic adjacent-pair layout."""
    for _ in range(200):
        tiles = list(range(1, pair_count + 1)) * 2
        random.shuffle(tiles)
        if _is_solvable(tiles, cols, rows):
            return tiles
    tiles: list[int] = []
    tile_id = 1
    for y in range(rows):
        for x in range(0, cols, 2):
            tiles.extend([tile_id, tile_id])
            tile_id += 1
            if tile_id > pair_count:
                tile_id = 1
    return tiles


def new_board(size: int = DEFAULT_COLS) -> dict[str, Any]:
    cols = DEFAULT_COLS
    rows = DEFAULT_ROWS
    tiles = _generate_solvable_tiles(cols, rows, PAIR_COUNT)
    return {
        "size": cols,
        "cols": cols,
        "rows": rows,
        "cells": tiles,
        "turn": BLACK,
        "phase": PHASE_PLAYING,
        "winner": EMPTY,
        "win_line": [],
        "last_move": None,
        "move_count": 0,
        "black_score": 0,
        "white_score": 0,
        "pending": None,
        "end_reason": None,
    }


def in_bounds(cols: int, rows: int, x: int, y: int) -> bool:
    return 0 <= x < cols and 0 <= y < rows


def _score_key(color: int) -> str:
    return "black_score" if color == BLACK else "white_score"


def _cell(board: dict[str, Any], x: int, y: int) -> int:
    cols = board["cols"]
    rows = board["rows"]
    if not in_bounds(cols, rows, x, y):
        return EMPTY
    return int(board["cells"][_index(cols, x, y)] or 0)


def _is_passable(board: dict[str, Any], x: int, y: int, ax: int, ay: int, bx: int, by: int) -> bool:
    if (x, y) in ((ax, ay), (bx, by)):
        return True
    return _cell(board, x, y) == EMPTY


def _can_connect(board: dict[str, Any], ax: int, ay: int, bx: int, by: int) -> bool:
    cols = board["cols"]
    rows = board["rows"]
    if _cell(board, ax, ay) == EMPTY or _cell(board, bx, by) == EMPTY:
        return False
    if _cell(board, ax, ay) != _cell(board, bx, by):
        return False

    def straight(a: tuple[int, int], b: tuple[int, int]) -> bool:
        x1, y1 = a
        x2, y2 = b
        if x1 == x2:
            step = 1 if y2 >= y1 else -1
            for y in range(y1 + step, y2, step):
                if not _is_passable(board, x1, y, ax, ay, bx, by):
                    return False
            return True
        if y1 == y2:
            step = 1 if x2 >= x1 else -1
            for x in range(x1 + step, x2, step):
                if not _is_passable(board, x, y1, ax, ay, bx, by):
                    return False
            return True
        return False

    a = (ax, ay)
    b = (bx, by)
    if straight(a, b):
        return True

    # one bend
    for corner in ((ax, by), (bx, ay)):
        if _is_passable(board, corner[0], corner[1], ax, ay, bx, by) and straight(a, corner) and straight(corner, b):
            return True

    # two bends — ``c`` is the first turning point reached in a straight line
    # from ``a``; from ``c`` we must then reach ``b`` with at most ONE further
    # bend. Scanning the one-cell border too lets paths route around the edge.
    for cx in range(-1, cols + 1):
        for cy in range(-1, rows + 1):
            c = (cx, cy)
            if c in (a, b):
                continue
            if not _is_passable(board, cx, cy, ax, ay, bx, by):
                continue
            if not straight(a, c):
                continue
            if straight(c, b):
                return True
            for corner in ((cx, by), (bx, cy)):
                if (
                    _is_passable(board, corner[0], corner[1], ax, ay, bx, by)
                    and straight(c, corner)
                    and straight(corner, b)
                ):
                    return True

    return False


def _remaining_pairs(board: dict[str, Any]) -> int:
    return sum(1 for v in board["cells"] if int(v or 0) != EMPTY) // 2


def _finish_if_done(board: dict[str, Any]) -> None:
    if _remaining_pairs(board) > 0:
        return
    black = int(board.get("black_score") or 0)
    white = int(board.get("white_score") or 0)
    board["phase"] = PHASE_FINISHED
    if black > white:
        board["winner"] = BLACK
        board["end_reason"] = "count"
    elif white > black:
        board["winner"] = WHITE
        board["end_reason"] = "count"
    else:
        board["winner"] = "draw"
        board["end_reason"] = "draw"


def apply_move(board: dict[str, Any], color: int, x: Any, y: Any) -> dict[str, Any]:
    if board.get("phase") != PHASE_PLAYING:
        raise IllegalMove("对局已结束")
    if color not in (BLACK, WHITE):
        raise IllegalMove("玩家不合法")
    if color != board["turn"]:
        raise IllegalMove("还没轮到你")

    x = _coerce_coord(x)
    y = _coerce_coord(y)
    cols = board["cols"]
    rows = board["rows"]
    if not in_bounds(cols, rows, x, y):
        raise IllegalMove("超出棋盘范围")

    idx = _index(cols, x, y)
    if int(board["cells"][idx] or 0) == EMPTY:
        raise IllegalMove("这里已经没有方块了")

    pending = board.get("pending")
    board["last_move"] = {"x": x, "y": y, "color": color}

    if pending is None:
        board["pending"] = [x, y]
        return board

    px, py = pending
    if px == x and py == y:
        raise IllegalMove("不能重复选择同一个方块")

    if not _can_connect(board, px, py, x, y):
        board["pending"] = [x, y]
        raise IllegalMove("这两个方块不能相连")

    pidx = _index(cols, px, py)
    board["cells"][idx] = EMPTY
    board["cells"][pidx] = EMPTY
    board["pending"] = None
    board[_score_key(color)] = int(board.get(_score_key(color)) or 0) + 1
    board["move_count"] += 1
    board["turn"] = WHITE if color == BLACK else BLACK
    _finish_if_done(board)
    return board


def force_winner(board: dict[str, Any], color: int) -> dict[str, Any]:
    board["phase"] = PHASE_FINISHED
    board["winner"] = color
    board["end_reason"] = "surrender"
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
