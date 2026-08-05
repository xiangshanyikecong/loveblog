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

"""Redis-backed room state for cottage 你画我猜 (draw & guess).

This is *not* a board game, so it deliberately does not implement the
gomoku/tictactoe engine contract and is not registered in
:mod:`app.services.cottage_games.room`. It owns its own Redis namespace
(``cottage_draw:*``) and is fully isolated: a bug here can at worst corrupt a
single draw-and-guess session.

The live drawing strokes are *relayed* over the WebSocket (never stored); only
the lightweight game state — whose turn it is to draw, the secret word, the
round number, the scores and the per-round guesses — lives in Redis so both
partners (and a reconnecting client) agree on it.

Secret-word handling: :meth:`DrawRoom.to_snapshot` redacts the word while a
round is in progress (guessers only ever see the masked length). The drawer is
told the word out-of-band via a private ``YOUR_WORD`` frame, so the broadcast
STATE never leaks the answer.
"""
from __future__ import annotations

import json
import logging
import random
import time
import uuid
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.services.cottage_games.common import IllegalMove

logger = logging.getLogger(__name__)

GAME_KEY = "draw"
ROOM_KEY = "cottage_draw:room"
LOCK_KEY = "cottage_draw:lock"

LOCK_TTL_MS = 3000
_LOCK_WAIT_MS = 2000
_LOCK_RETRY_MS = 25

PHASE_WAITING = "waiting"
PHASE_DRAWING = "drawing"
PHASE_ROUND_END = "round_end"
PHASE_FINISHED = "finished"

DEFAULT_TOTAL_ROUNDS = 6
DEFAULT_ROUND_DURATION_SEC = 90
MAX_GUESSES_KEPT = 60

# Drawer reward when the partner guesses correctly.
DRAWER_POINTS = 5

# Couple-flavoured default word bank (易画好猜，偏向恋爱/生活场景).
WORD_BANK: list[str] = [
    "太阳", "月亮", "星星", "彩虹", "爱心", "玫瑰", "戒指", "礼物",
    "蛋糕", "气球", "雨伞", "奶茶", "咖啡", "西瓜", "草莓", "冰淇淋",
    "小猫", "小狗", "蝴蝶", "兔子", "熊猫", "企鹅", "海豚", "恐龙",
    "房子", "汽车", "飞机", "轮船", "自行车", "火车", "热气球", "火箭",
    "雪人", "圣诞树", "灯笼", "风筝", "钟表", "眼镜", "帽子", "雨靴",
    "拥抱", "亲吻", "牵手", "约会", "求婚", "婚纱", "情书", "拍照",
    "电视", "电脑", "手机", "钢琴", "吉他", "麦克风", "篮球", "足球",
    "苹果", "香蕉", "葡萄", "披萨", "汉堡", "寿司", "棒棒糖", "甜甜圈",
]


class DrawRoomUnavailable(Exception):
    """Redis (the room's backing store) is unreachable."""


def _now_ms() -> int:
    return int(time.time() * 1000)


def normalize_word(text: str) -> str:
    """Loose match: drop whitespace and case so "Small Cat" == "smallcat"."""
    return "".join((text or "").split()).strip().lower()


def mask_for(word: str) -> str:
    """A length hint like ``_ _ _`` (one underscore per character)."""
    return " ".join("_" for _ in (word or ""))


class DrawRoom:
    def __init__(self) -> None:
        self.room_key = ROOM_KEY
        self.lock_key = LOCK_KEY

    # -- lock helpers (token-guarded, mirrors GameRoom) ---------------------

    def _acquire_lock(self, redis_client: Redis) -> str | None:
        token = uuid.uuid4().hex
        deadline = _now_ms() + _LOCK_WAIT_MS
        while True:
            try:
                if redis_client.set(self.lock_key, token, nx=True, px=LOCK_TTL_MS):
                    return token
            except RedisError as exc:
                raise DrawRoomUnavailable("游戏服务暂不可用") from exc
            if _now_ms() >= deadline:
                return None
            time.sleep(_LOCK_RETRY_MS / 1000)

    def _release_lock(self, redis_client: Redis, token: str) -> None:
        try:
            if redis_client.get(self.lock_key) == token:
                redis_client.delete(self.lock_key)
        except RedisError:
            logger.warning("[cottage-draw] failed to release lock (non-fatal)")

    # -- raw load / save ----------------------------------------------------

    def _load_raw(self, redis_client: Redis) -> dict[str, Any] | None:
        try:
            raw = redis_client.get(self.room_key)
        except RedisError as exc:
            raise DrawRoomUnavailable("游戏服务暂不可用") from exc
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
            raise DrawRoomUnavailable("游戏服务暂不可用") from exc

    def _empty_room(self) -> dict[str, Any]:
        return {
            "game_key": GAME_KEY,
            "phase": PHASE_WAITING,
            "a_uid": None,
            "b_uid": None,
            "drawer_uid": None,
            "round": 0,
            "total_rounds": DEFAULT_TOTAL_ROUNDS,
            "word": None,
            "scores": {},
            "round_started_ms": None,
            "round_deadline_ms": None,
            "round_duration_sec": DEFAULT_ROUND_DURATION_SEC,
            "guesses": [],
            "round_winner_uid": None,
            "revealed_word": None,
            "used_words": [],
            "started_by": None,
            "ended_at_ms": None,
            "winner_uid": None,
            "seq": 0,
        }

    # -- snapshot -----------------------------------------------------------

    def to_snapshot(self, data: dict[str, Any] | None) -> dict[str, Any]:
        """Broadcast-safe public snapshot — never includes the live secret word.

        During a round the answer is redacted (only ``word_len`` / ``word_mask``
        ship). When the round ends or the game finishes, ``revealed_word`` holds
        the answer for the recap UI.
        """
        if not data:
            data = self._empty_room()
        phase = data.get("phase", PHASE_WAITING)
        word = data.get("word") or ""
        in_round = phase == PHASE_DRAWING
        return {
            "game_key": GAME_KEY,
            "phase": phase,
            "a_uid": data.get("a_uid"),
            "b_uid": data.get("b_uid"),
            "drawer_uid": data.get("drawer_uid"),
            "round": int(data.get("round", 0)),
            "total_rounds": int(data.get("total_rounds", DEFAULT_TOTAL_ROUNDS)),
            "scores": data.get("scores", {}),
            "word_len": len(word) if word else 0,
            "word_mask": mask_for(word) if (word and in_round) else "",
            # Only reveal the answer once the round is over.
            "revealed_word": data.get("revealed_word") if phase in (PHASE_ROUND_END, PHASE_FINISHED) else None,
            "round_started_ms": data.get("round_started_ms"),
            "round_deadline_ms": data.get("round_deadline_ms"),
            "round_duration_sec": int(data.get("round_duration_sec", DEFAULT_ROUND_DURATION_SEC)),
            "guesses": data.get("guesses", []),
            "round_winner_uid": data.get("round_winner_uid"),
            "winner_uid": data.get("winner_uid"),
            "seq": int(data.get("seq", 0)),
            "server_ts_ms": _now_ms(),
        }

    def get_snapshot(self, redis_client: Redis) -> dict[str, Any]:
        return self.to_snapshot(self._load_raw(redis_client))

    def current_word(self, redis_client: Redis) -> str | None:
        data = self._load_raw(redis_client)
        return (data or {}).get("word") if data else None

    # -- helpers ------------------------------------------------------------

    def _pick_word(self, used: list[str], bank: list[str] | None = None) -> str:
        pool = [w for w in (bank or WORD_BANK) if w not in (used or [])]
        if not pool:
            pool = list(bank or WORD_BANK)
        return random.choice(pool)

    def _start_round(
        self,
        data: dict[str, Any],
        *,
        drawer_uid: str,
        round_no: int,
    ) -> dict[str, Any]:
        word = self._pick_word(data.get("used_words") or [])
        used = list(data.get("used_words") or [])
        used.append(word)
        now = _now_ms()
        duration = int(data.get("round_duration_sec", DEFAULT_ROUND_DURATION_SEC))
        data.update(
            {
                "phase": PHASE_DRAWING,
                "drawer_uid": drawer_uid,
                "round": round_no,
                "word": word,
                "used_words": used,
                "round_started_ms": now,
                "round_deadline_ms": now + duration * 1000,
                "guesses": [],
                "round_winner_uid": None,
                "revealed_word": None,
            }
        )
        return data

    # -- mutations ----------------------------------------------------------

    def new_game(
        self,
        redis_client: Redis,
        *,
        requester_uid: str,
        partner_uid: str,
        total_rounds: int = DEFAULT_TOTAL_ROUNDS,
        round_duration_sec: int = DEFAULT_ROUND_DURATION_SEC,
    ) -> dict[str, Any]:
        if not partner_uid or partner_uid == requester_uid:
            raise IllegalMove("需要两位伴侣账号才能开始游戏")

        total_rounds = max(2, min(int(total_rounds or DEFAULT_TOTAL_ROUNDS), 20))
        round_duration_sec = max(30, min(int(round_duration_sec or DEFAULT_ROUND_DURATION_SEC), 300))

        token = self._acquire_lock(redis_client)
        if token is None:
            raise IllegalMove("操作太频繁，请稍后再试")
        try:
            data = self._empty_room()
            data["a_uid"] = requester_uid
            data["b_uid"] = partner_uid
            data["started_by"] = requester_uid
            data["total_rounds"] = total_rounds
            data["round_duration_sec"] = round_duration_sec
            data["scores"] = {requester_uid: 0, partner_uid: 0}
            data = self._start_round(data, drawer_uid=requester_uid, round_no=1)
            data["seq"] = 1
            self._save_raw(redis_client, data)
            return self.to_snapshot(data)
        finally:
            self._release_lock(redis_client, token)

    def record_guess(self, redis_client: Redis, *, uid: str, text: str) -> tuple[dict[str, Any], bool]:
        text = (text or "").strip()
        if not text:
            raise IllegalMove("猜测内容不能为空")
        if len(text) > 50:
            raise IllegalMove("猜测内容太长了")

        token = self._acquire_lock(redis_client)
        if token is None:
            raise IllegalMove("操作太频繁，请稍后再试")
        try:
            data = self._load_raw(redis_client)
            if not data or data.get("phase") != PHASE_DRAWING:
                raise IllegalMove("当前没有进行中的回合")
            if uid not in (data.get("a_uid"), data.get("b_uid")):
                raise IllegalMove("你不是本局玩家")
            if uid == data.get("drawer_uid"):
                raise IllegalMove("画画的人不能猜哦")

            now = _now_ms()
            correct = normalize_word(text) == normalize_word(data.get("word") or "")
            guesses = data.get("guesses") or []
            guesses.append({"uid": uid, "text": text, "correct": correct, "ts_ms": now})
            data["guesses"] = guesses[-MAX_GUESSES_KEPT:]

            if correct:
                deadline = int(data.get("round_deadline_ms") or now)
                started = int(data.get("round_started_ms") or now)
                duration_ms = max(1, deadline - started)
                remaining = max(0, deadline - now)
                # 1..10 points, more for a faster guess.
                guesser_points = 1 + int(round(9 * (remaining / duration_ms)))
                scores = data.get("scores") or {}
                drawer_uid = data.get("drawer_uid")
                scores[uid] = scores.get(uid, 0) + guesser_points
                if drawer_uid:
                    scores[drawer_uid] = scores.get(drawer_uid, 0) + DRAWER_POINTS
                data["scores"] = scores
                data["round_winner_uid"] = uid
                data["revealed_word"] = data.get("word")
                data["phase"] = PHASE_ROUND_END

            data["seq"] = int(data.get("seq", 0)) + 1
            self._save_raw(redis_client, data)
            return self.to_snapshot(data), correct
        finally:
            self._release_lock(redis_client, token)

    def timeout_round(self, redis_client: Redis, *, uid: str) -> dict[str, Any]:
        """End the current round when the timer has elapsed with no winner."""
        token = self._acquire_lock(redis_client)
        if token is None:
            raise IllegalMove("操作太频繁，请稍后再试")
        try:
            data = self._load_raw(redis_client)
            if not data or data.get("phase") != PHASE_DRAWING:
                # Already advanced by the other client — return current state.
                return self.to_snapshot(data)
            if uid not in (data.get("a_uid"), data.get("b_uid")):
                raise IllegalMove("你不是本局玩家")
            now = _now_ms()
            if now < int(data.get("round_deadline_ms") or 0):
                raise IllegalMove("回合还没结束")
            data["revealed_word"] = data.get("word")
            data["round_winner_uid"] = None
            data["phase"] = PHASE_ROUND_END
            data["seq"] = int(data.get("seq", 0)) + 1
            self._save_raw(redis_client, data)
            return self.to_snapshot(data)
        finally:
            self._release_lock(redis_client, token)

    def next_round(self, redis_client: Redis, *, uid: str) -> dict[str, Any]:
        """Advance from ``round_end`` to the next round, swapping the drawer.

        When the last round is done the game enters ``finished`` and the winner
        (higher score, or tie) is recorded on the room for the caller to persist.
        """
        token = self._acquire_lock(redis_client)
        if token is None:
            raise IllegalMove("操作太频繁，请稍后再试")
        try:
            data = self._load_raw(redis_client)
            if not data or data.get("phase") != PHASE_ROUND_END:
                raise IllegalMove("当前回合还没有结束")
            if uid not in (data.get("a_uid"), data.get("b_uid")):
                raise IllegalMove("你不是本局玩家")

            current_round = int(data.get("round", 0))
            total = int(data.get("total_rounds", DEFAULT_TOTAL_ROUNDS))
            if current_round >= total:
                data["phase"] = PHASE_FINISHED
                data["ended_at_ms"] = _now_ms()
                data["word"] = None
                scores = data.get("scores") or {}
                a_uid, b_uid = data.get("a_uid"), data.get("b_uid")
                sa, sb = scores.get(a_uid, 0), scores.get(b_uid, 0)
                if sa == sb:
                    data["winner_uid"] = None
                else:
                    data["winner_uid"] = a_uid if sa > sb else b_uid
            else:
                next_drawer = data.get("b_uid") if data.get("drawer_uid") == data.get("a_uid") else data.get("a_uid")
                data = self._start_round(data, drawer_uid=next_drawer, round_no=current_round + 1)
            data["seq"] = int(data.get("seq", 0)) + 1
            self._save_raw(redis_client, data)
            return self.to_snapshot(data)
        finally:
            self._release_lock(redis_client, token)

    def end_game(self, redis_client: Redis, *, uid: str) -> dict[str, Any]:
        """Abort the current game early (either partner). The partner with the
        higher score still wins; a tie stays a tie."""
        token = self._acquire_lock(redis_client)
        if token is None:
            raise IllegalMove("操作太频繁，请稍后再试")
        try:
            data = self._load_raw(redis_client)
            if not data or data.get("phase") in (PHASE_FINISHED, PHASE_WAITING):
                raise IllegalMove("当前没有进行中的游戏")
            if uid not in (data.get("a_uid"), data.get("b_uid")):
                raise IllegalMove("你不是本局玩家")
            scores = data.get("scores") or {}
            a_uid, b_uid = data.get("a_uid"), data.get("b_uid")
            sa, sb = scores.get(a_uid, 0), scores.get(b_uid, 0)
            data["phase"] = PHASE_FINISHED
            data["ended_at_ms"] = _now_ms()
            data["word"] = None
            data["winner_uid"] = None if sa == sb else (a_uid if sa > sb else b_uid)
            data["seq"] = int(data.get("seq", 0)) + 1
            self._save_raw(redis_client, data)
            return self.to_snapshot(data)
        finally:
            self._release_lock(redis_client, token)

    def describe_finished(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        if data and data.get("phase") == PHASE_FINISHED:
            return data
        return None

    def load(self, redis_client: Redis) -> dict[str, Any] | None:
        return self._load_raw(redis_client)


draw_room = DrawRoom()
