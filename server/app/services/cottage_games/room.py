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

"""Redis-backed room state for cottage 一起玩 two-person games.

A :class:`GameRoom` binds a pure rules engine (e.g. :mod:`gomoku` or
:mod:`tictactoe`) to its own isolated Redis namespace. The whole room lives in a
single JSON string key so a read-modify-write swaps the entire snapshot
atomically *enough* for two players; to be safe against the rare double-tab race
every mutation is additionally guarded with a short Redis lock
(``SET key val NX PX``). Reads are lock-free.

Keys (per game, under the isolated ``cottage_game:`` namespace):

- ``cottage_game:<game>:room``  (String, JSON) — the full room snapshot
- ``cottage_game:<game>:lock``  (String)       — short-lived mutation lock

If Redis is unavailable, callers get a :class:`RoomUnavailable` so the feature
degrades to "游戏暂不可用" instead of taking anything else down.

Backward compatibility: the module-level ``new_game`` / ``apply_move`` /
``surrender`` / ``get_snapshot`` / ``to_snapshot`` helpers delegate to the
shared :data:`gomoku_room` instance so existing gomoku callers keep working
unchanged.
"""
from __future__ import annotations

import copy
import json
import logging
import time
import uuid
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.services.cottage_games import gomoku, linklink, memory, reversi, tictactoe

logger = logging.getLogger(__name__)

LOCK_TTL_MS = 3000
_LOCK_WAIT_MS = 2000
_LOCK_RETRY_MS = 25

# How many prior board states to keep for 悔棋 (take-back). Boards are small
# JSON; a couple only ever needs the last move or two, but a small stack lets
# them undo a few times in a row.
HISTORY_MAX = 20

# Room phases (superset of board phases — adds the pre-game "waiting").
PHASE_WAITING = "waiting"
PHASE_PLAYING = "playing"
PHASE_FINISHED = "finished"

# Kept for backward compatibility with the original gomoku-only module.
GAME_KEY = "gomoku"


class RoomUnavailable(Exception):
    """Redis (the room's backing store) is unreachable."""


def _now_ms() -> int:
    return int(time.time() * 1000)


class GameRoom:
    """One Redis-backed room for a single game engine.

    ``engine`` is any module exposing the gomoku/tictactoe contract:
    ``new_board``, ``apply_move(board, color, x, y)``, ``force_winner``,
    ``color_name``, ``opponent`` and the ``BLACK``/``WHITE``/``EMPTY`` /
    ``DEFAULT_SIZE`` / ``PHASE_FINISHED`` constants.
    """

    def __init__(self, engine: Any, game_key: str) -> None:
        self.engine = engine
        self.game_key = game_key
        self.room_key = f"cottage_game:{game_key}:room"
        self.lock_key = f"cottage_game:{game_key}:lock"

    # -- lock helpers (best-effort, token-guarded) --------------------------

    def _acquire_lock(self, redis_client: Redis) -> str | None:
        token = uuid.uuid4().hex
        deadline = _now_ms() + _LOCK_WAIT_MS
        while True:
            try:
                if redis_client.set(self.lock_key, token, nx=True, px=LOCK_TTL_MS):
                    return token
            except RedisError as exc:
                raise RoomUnavailable("游戏服务暂不可用") from exc
            if _now_ms() >= deadline:
                return None
            time.sleep(_LOCK_RETRY_MS / 1000)

    def _release_lock(self, redis_client: Redis, token: str) -> None:
        # Only delete the lock if we still own it (token match), so we never
        # drop a lock another writer acquired after ours expired.
        try:
            current = redis_client.get(self.lock_key)
            if current == token:
                redis_client.delete(self.lock_key)
        except RedisError:
            logger.warning("[cottage-games] failed to release lock (non-fatal)")

    # -- raw load / save ----------------------------------------------------

    def _load_raw(self, redis_client: Redis) -> dict[str, Any] | None:
        try:
            raw = redis_client.get(self.room_key)
        except RedisError as exc:
            raise RoomUnavailable("游戏服务暂不可用") from exc
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except (TypeError, ValueError):
            return None

    def _save_raw(self, redis_client: Redis, data: dict[str, Any]) -> None:
        try:
            redis_client.set(self.room_key, json.dumps(data, ensure_ascii=False))
        except RedisError as exc:
            raise RoomUnavailable("游戏服务暂不可用") from exc

    def _empty_room(self) -> dict[str, Any]:
        board = self.engine.new_board()
        # Blank board but in the "waiting" phase: no players seated yet.
        return {
            "game_key": self.game_key,
            "phase": PHASE_WAITING,
            "board": board,
            "black_uid": None,
            "white_uid": None,
            "started_by": None,
            "started_at_ms": None,
            "ended_at_ms": None,
            "end_reason": None,
            "history": [],
            "undo_request_by": None,
            "seq": 0,
        }

    # -- snapshot (the shape sent to clients) -------------------------------

    def to_snapshot(self, data: dict[str, Any] | None) -> dict[str, Any]:
        """Build the public, JSON-safe room snapshot for the wire/REST layer."""
        engine = self.engine
        if not data:
            data = self._empty_room()
        board = data.get("board") or engine.new_board()
        winner = board.get("winner", engine.EMPTY)
        turn_uid = None
        if data.get("phase") == PHASE_PLAYING:
            turn_uid = data["black_uid"] if board.get("turn") == engine.BLACK else data["white_uid"]
        snap = {
            "game_key": self.game_key,
            "phase": data.get("phase", PHASE_WAITING),
            "size": board.get("size", engine.DEFAULT_SIZE),
            "cells": board.get("cells", []),
            "turn": engine.color_name(board.get("turn")),
            "turn_uid": turn_uid,
            "winner": engine.color_name(winner) if winner != engine.EMPTY else None,
            "win_line": board.get("win_line", []),
            "legal_moves": board.get("legal_moves", []),
            "last_move": board.get("last_move"),
            "move_count": board.get("move_count", 0),
            "black_uid": data.get("black_uid"),
            "white_uid": data.get("white_uid"),
            "started_by": data.get("started_by"),
            "end_reason": data.get("end_reason"),
            "undo_request_by": data.get("undo_request_by"),
            "seq": int(data.get("seq", 0)),
            "server_ts_ms": _now_ms(),
        }
        for key in (
            "cols",
            "rows",
            "tiles",
            "states",
            "icons",
            "black_score",
            "white_score",
            "pending",
        ):
            if key in board:
                snap[key] = board[key]
        # Let an engine redact secret board fields before the snapshot leaves the
        # server (e.g. memory masks face-down tiles so the answer key never ships).
        redactor = getattr(engine, "redact_public_snapshot", None)
        if callable(redactor):
            redactor(snap, board)
        return snap

    def get_snapshot(self, redis_client: Redis) -> dict[str, Any]:
        return self.to_snapshot(self._load_raw(redis_client))

    def _seat_color(self, data: dict[str, Any], uid: str) -> int | None:
        if uid and uid == data.get("black_uid"):
            return self.engine.BLACK
        if uid and uid == data.get("white_uid"):
            return self.engine.WHITE
        return None

    # -- mutations (lock-guarded) -------------------------------------------

    def new_game(
        self,
        redis_client: Redis,
        *,
        requester_uid: str,
        partner_uid: str,
        size: int | None = None,
    ) -> dict[str, Any]:
        """Start a fresh match. Alternates who plays Black across matches.

        The first match seats the requester as Black (先手); each subsequent
        match swaps the colours so the two partners take turns going first.
        """
        if not partner_uid or partner_uid == requester_uid:
            raise self.engine.IllegalMove("需要两位伴侣账号才能开始对局")

        token = self._acquire_lock(redis_client)
        if token is None:
            raise self.engine.IllegalMove("操作太频繁，请稍后再试")
        try:
            prev = self._load_raw(redis_client)
            prev_black = prev.get("black_uid") if prev else None
            prev_white = prev.get("white_uid") if prev else None
            seq = int(prev.get("seq", 0)) + 1 if prev else 1

            pair = {requester_uid, partner_uid}
            if prev_black and prev_white and {prev_black, prev_white} == pair:
                black_uid, white_uid = prev_white, prev_black  # alternate first move
            else:
                black_uid, white_uid = requester_uid, partner_uid

            board = self.engine.new_board() if size is None else self.engine.new_board(size)
            data = {
                "game_key": self.game_key,
                "phase": PHASE_PLAYING,
                "board": board,
                "black_uid": black_uid,
                "white_uid": white_uid,
                "started_by": requester_uid,
                "started_at_ms": _now_ms(),
                "ended_at_ms": None,
                "end_reason": None,
                "history": [],
                "undo_request_by": None,
                "seq": seq,
            }
            self._save_raw(redis_client, data)
            return self.to_snapshot(data)
        finally:
            self._release_lock(redis_client, token)

    def apply_move(self, redis_client: Redis, *, uid: str, x: Any, y: Any) -> dict[str, Any]:
        """Apply a player's move. Returns the new snapshot.

        Raises :class:`IllegalMove` for any rule / seat / turn violation.
        """
        token = self._acquire_lock(redis_client)
        if token is None:
            raise self.engine.IllegalMove("操作太频繁，请稍后再试")
        try:
            data = self._load_raw(redis_client)
            if not data or data.get("phase") != PHASE_PLAYING:
                raise self.engine.IllegalMove("当前没有进行中的对局")
            color = self._seat_color(data, uid)
            if color is None:
                raise self.engine.IllegalMove("你不是本局玩家")

            # Snapshot the pre-move board first so an accepted 悔棋 can restore
            # it exactly (handles reversi flips, which aren't trivially reversible).
            prev_board = copy.deepcopy(data["board"])
            self.engine.apply_move(data["board"], color, x, y)
            history = data.get("history") or []
            history.append(prev_board)
            data["history"] = history[-HISTORY_MAX:]
            data["undo_request_by"] = None  # a fresh move cancels any pending request
            data["seq"] = int(data.get("seq", 0)) + 1
            if data["board"].get("phase") == self.engine.PHASE_FINISHED:
                data["phase"] = PHASE_FINISHED
                data["ended_at_ms"] = _now_ms()
                # Prefer an engine-supplied reason (e.g. reversi "count"); fall
                # back to the connect-N default so gomoku/tic-tac-toe are unchanged.
                board_reason = data["board"].get("end_reason")
                if board_reason:
                    data["end_reason"] = board_reason
                else:
                    data["end_reason"] = "draw" if data["board"].get("winner") == "draw" else "five"
            self._save_raw(redis_client, data)
            return self.to_snapshot(data)
        finally:
            self._release_lock(redis_client, token)

    def surrender(self, redis_client: Redis, *, uid: str) -> dict[str, Any]:
        """The player ``uid`` resigns; the opponent wins."""
        token = self._acquire_lock(redis_client)
        if token is None:
            raise self.engine.IllegalMove("操作太频繁，请稍后再试")
        try:
            data = self._load_raw(redis_client)
            if not data or data.get("phase") != PHASE_PLAYING:
                raise self.engine.IllegalMove("当前没有进行中的对局")
            color = self._seat_color(data, uid)
            if color is None:
                raise self.engine.IllegalMove("你不是本局玩家")

            self.engine.force_winner(data["board"], self.engine.opponent(color))
            data["phase"] = PHASE_FINISHED
            data["ended_at_ms"] = _now_ms()
            data["end_reason"] = "surrender"
            data["undo_request_by"] = None
            data["seq"] = int(data.get("seq", 0)) + 1
            self._save_raw(redis_client, data)
            return self.to_snapshot(data)
        finally:
            self._release_lock(redis_client, token)

    def request_undo(self, redis_client: Redis, *, uid: str) -> dict[str, Any]:
        """Ask the partner to take back (悔棋) one's own last move.

        Only the player who made the last move may ask, and only while a game is
        in progress. The request is stored on the room so a reconnecting client
        still sees it; the partner confirms via :meth:`respond_undo`.
        """
        token = self._acquire_lock(redis_client)
        if token is None:
            raise self.engine.IllegalMove("操作太频繁，请稍后再试")
        try:
            data = self._load_raw(redis_client)
            if not data or data.get("phase") != PHASE_PLAYING:
                raise self.engine.IllegalMove("当前没有进行中的对局")
            history = data.get("history") or []
            last = data["board"].get("last_move")
            if not history or not last:
                raise self.engine.IllegalMove("还没有可以悔的棋")
            last_mover = (
                data.get("black_uid") if last.get("color") == self.engine.BLACK
                else data.get("white_uid")
            )
            if uid != last_mover:
                raise self.engine.IllegalMove("只能请求悔回自己刚下的那一步")
            if data.get("undo_request_by"):
                raise self.engine.IllegalMove("已有一个悔棋请求在等待回应")
            data["undo_request_by"] = uid
            data["seq"] = int(data.get("seq", 0)) + 1
            self._save_raw(redis_client, data)
            return self.to_snapshot(data)
        finally:
            self._release_lock(redis_client, token)

    def respond_undo(self, redis_client: Redis, *, uid: str, accept: bool) -> dict[str, Any]:
        """The partner accepts/declines a pending 悔棋 request.

        On accept the previous board is restored exactly (one ply back) and it
        becomes the requester's turn again.
        """
        token = self._acquire_lock(redis_client)
        if token is None:
            raise self.engine.IllegalMove("操作太频繁，请稍后再试")
        try:
            data = self._load_raw(redis_client)
            if not data:
                raise self.engine.IllegalMove("当前没有进行中的对局")
            requester = data.get("undo_request_by")
            if not requester:
                raise self.engine.IllegalMove("没有待回应的悔棋请求")
            if uid == requester:
                raise self.engine.IllegalMove("不能回应自己发起的悔棋请求")
            if uid not in (data.get("black_uid"), data.get("white_uid")):
                raise self.engine.IllegalMove("你不是本局玩家")

            if accept:
                history = data.get("history") or []
                if history:
                    data["board"] = history.pop()
                    data["history"] = history
                    data["phase"] = PHASE_PLAYING
                    data["ended_at_ms"] = None
                    data["end_reason"] = None
            data["undo_request_by"] = None
            data["seq"] = int(data.get("seq", 0)) + 1
            self._save_raw(redis_client, data)
            return self.to_snapshot(data)
        finally:
            self._release_lock(redis_client, token)

    def describe_finished(self, redis_client: Redis) -> dict[str, Any] | None:
        """Return the raw room dict if it is in a finished state, for the caller
        to persist a :class:`GameMatch`. Lock-free read."""
        data = self._load_raw(redis_client)
        if data and data.get("phase") == PHASE_FINISHED:
            return data
        return None


# ---------------------------------------------------------------------------
# Registry + per-game instances
# ---------------------------------------------------------------------------

gomoku_room = GameRoom(gomoku, "gomoku")
tictactoe_room = GameRoom(tictactoe, "tictactoe")
reversi_room = GameRoom(reversi, "reversi")
memory_room = GameRoom(memory, "memory")
linklink_room = GameRoom(linklink, "linklink")

ROOMS: dict[str, GameRoom] = {
    "gomoku": gomoku_room,
    "tictactoe": tictactoe_room,
    "reversi": reversi_room,
    "memory": memory_room,
    "linklink": linklink_room,
}


def get_room(game_key: str) -> GameRoom | None:
    return ROOMS.get(game_key)


# ---------------------------------------------------------------------------
# Backward-compatible module-level helpers (gomoku)
# ---------------------------------------------------------------------------

ROOM_KEY = gomoku_room.room_key
LOCK_KEY = gomoku_room.lock_key


def to_snapshot(data: dict[str, Any] | None) -> dict[str, Any]:
    return gomoku_room.to_snapshot(data)


def get_snapshot(redis_client: Redis) -> dict[str, Any]:
    return gomoku_room.get_snapshot(redis_client)


def new_game(
    redis_client: Redis,
    *,
    requester_uid: str,
    partner_uid: str,
    size: int = gomoku.DEFAULT_SIZE,
) -> dict[str, Any]:
    return gomoku_room.new_game(
        redis_client, requester_uid=requester_uid, partner_uid=partner_uid, size=size
    )


def apply_move(redis_client: Redis, *, uid: str, x: Any, y: Any) -> dict[str, Any]:
    return gomoku_room.apply_move(redis_client, uid=uid, x=x, y=y)


def surrender(redis_client: Redis, *, uid: str) -> dict[str, Any]:
    return gomoku_room.surrender(redis_client, uid=uid)


def describe_finished(redis_client: Redis) -> dict[str, Any] | None:
    return gomoku_room.describe_finished(redis_client)
