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

"""Memory flip-card (记忆翻牌) rules engine.

Two partners take turns flipping pairs on a small grid. A successful match
scores for the active player and grants another turn; a miss passes play to the
opponent. Highest score when all pairs are matched wins (draw on tie).

Board encoding:
- ``tiles``: shuffled pair ids (1..N) laid on the grid
- ``states``: per-cell 0=face-down, 1=temporarily face-up, 2=matched
"""
from __future__ import annotations

import random
from typing import Any

from app.services.cottage_games.common import IllegalMove

EMPTY = 0
BLACK = 1
WHITE = 2

DEFAULT_SIZE = 4
PAIR_COUNT = 8
ICONS = ["🌸", "🎵", "⭐", "🍰", "🦋", "🌙", "💫", "🎀"]

PHASE_PLAYING = "playing"
PHASE_FINISHED = "finished"

STATE_DOWN = 0
STATE_UP = 1
STATE_MATCHED = 2


def normalize_size(size: Any = DEFAULT_SIZE) -> int:
    return DEFAULT_SIZE


def _index(size: int, x: int, y: int) -> int:
    return y * size + x


def _coerce_coord(value: Any) -> int:
    if isinstance(value, bool):
        raise IllegalMove("坐标不合法")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise IllegalMove("坐标不合法") from exc


def new_board(size: int = DEFAULT_SIZE) -> dict[str, Any]:
    size = normalize_size(size)
    tiles = list(range(1, PAIR_COUNT + 1)) * 2
    random.shuffle(tiles)
    return {
        "size": size,
        "cols": size,
        "rows": size,
        "tiles": tiles,
        "states": [STATE_DOWN] * (size * size),
        "icons": ICONS[:PAIR_COUNT],
        "cells": tiles[:],  # wire-compat mirror of face values for clients
        "turn": BLACK,
        "phase": PHASE_PLAYING,
        "winner": EMPTY,
        "win_line": [],
        "last_move": None,
        "move_count": 0,
        "black_score": 0,
        "white_score": 0,
        "pending": None,
        # Two just-flipped non-matching tiles kept face-up so BOTH players can
        # see them; flipped back on the next move via _resolve_mismatch().
        "mismatch": None,
        "end_reason": None,
    }


def in_bounds(size: int, x: int, y: int) -> bool:
    return 0 <= x < size and 0 <= y < size


def _score_key(color: int) -> str:
    return "black_score" if color == BLACK else "white_score"


def _all_matched(board: dict[str, Any]) -> bool:
    return all(s == STATE_MATCHED for s in board["states"])


def _finish_if_done(board: dict[str, Any]) -> None:
    if not _all_matched(board):
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


def _resolve_mismatch(board: dict[str, Any]) -> None:
    """Flip a previously-revealed, non-matching pair back to face-down.

    The losing turn's two tiles are kept face-up (so the partner can memorise
    them); they're turned back here at the start of the next move.
    """
    mismatch = board.get("mismatch")
    if not mismatch:
        return
    states = board["states"]
    for i in mismatch:
        if 0 <= i < len(states) and states[i] == STATE_UP:
            states[i] = STATE_DOWN
    board["mismatch"] = None


def apply_move(board: dict[str, Any], color: int, x: Any, y: Any) -> dict[str, Any]:
    if board.get("phase") != PHASE_PLAYING:
        raise IllegalMove("对局已结束")
    if color not in (BLACK, WHITE):
        raise IllegalMove("玩家不合法")
    if color != board["turn"]:
        raise IllegalMove("还没轮到你")

    x = _coerce_coord(x)
    y = _coerce_coord(y)
    size = board["size"]
    if not in_bounds(size, x, y):
        raise IllegalMove("超出棋盘范围")

    # Flip back the previous turn's mismatched pair (kept face-up so the partner
    # could memorise it) before applying this move.
    _resolve_mismatch(board)

    idx = _index(size, x, y)
    state = board["states"][idx]
    if state == STATE_MATCHED:
        raise IllegalMove("这张牌已经配对成功了")
    if state == STATE_UP:
        raise IllegalMove("这张牌已经翻开")

    pending = board.get("pending")
    board["states"][idx] = STATE_UP
    board["last_move"] = {"x": x, "y": y, "color": color}
    board["move_count"] += 1

    if pending is None:
        board["pending"] = [x, y]
        return board

    px, py = pending
    if px == x and py == y:
        raise IllegalMove("不能重复选择同一张牌")

    pidx = _index(size, px, py)
    if board["tiles"][idx] == board["tiles"][pidx]:
        board["states"][idx] = STATE_MATCHED
        board["states"][pidx] = STATE_MATCHED
        board[_score_key(color)] = int(board.get(_score_key(color)) or 0) + 1
        board["pending"] = None
        _finish_if_done(board)
        if board.get("phase") != PHASE_FINISHED:
            board["turn"] = color
    else:
        # Keep BOTH tiles face-up and hand the turn over. The partner sees the
        # two faces in the broadcast STATE and they are flipped back on the next
        # applied move (via _resolve_mismatch).
        board["mismatch"] = [idx, pidx]
        board["pending"] = None
        board["turn"] = WHITE if color == BLACK else BLACK

    return board


def force_winner(board: dict[str, Any], color: int) -> dict[str, Any]:
    board["phase"] = PHASE_FINISHED
    board["winner"] = color
    board["end_reason"] = "surrender"
    return board


def redact_public_snapshot(snap: dict[str, Any], board: dict[str, Any]) -> None:
    """Mask face-down tiles so clients can't read the answer key.

    Only revealed cells (temporarily face-up or matched) expose their face id;
    every other position is sent as 0. The generic room layer calls this hook
    (when present on the engine) while building the client snapshot, so the full
    tile layout never leaves the server.
    """
    states = board.get("states") or []
    tiles = board.get("tiles") or []
    masked = [
        (tiles[i] if i < len(states) and states[i] in (STATE_UP, STATE_MATCHED) else 0)
        for i in range(len(tiles))
    ]
    if "tiles" in snap:
        snap["tiles"] = masked
    if "cells" in snap:
        snap["cells"] = masked


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
