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

"""Redis-backed room state for cottage 一起看 (watch-together).

Two Redis keys make up the room:

- ``cottage_watch:current`` (Hash)   — current playback state
- ``cottage_watch:event_seq`` (String) — monotonically increasing counter

The room holds a single shared video at a time (the source both partners
loaded). Playback position is synthesized live on read the same way the
listen-together room does: while playing, the head advances by
``(now - started_at) * rate`` on top of the stored ``position_ms``.

Concurrency note: reads and mutations share a short-lived Redis lease so a
reconnect cannot observe a newly incremented ``event_seq`` with the previous
hash contents and then discard the matching broadcast as already seen.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import logging
import time
from typing import Any
import uuid

from redis import Redis

ROOM_CURRENT = "cottage_watch:current"
ROOM_EVENT_SEQ = "cottage_watch:event_seq"
ROOM_STATE_LOCK = "cottage_watch:state_lock"
STATE_LOCK_TTL_MS = 10_000
STATE_LOCK_WAIT_MS = 5_000

logger = logging.getLogger(__name__)

_RELEASE_LOCK_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

# Mutating events a client may send. LOAD swaps the current source; the rest
# move the shared playback head.
WATCH_EVENT_TYPES = frozenset({"LOAD", "PLAY", "PAUSE", "SEEK", "RATE"})

_MIN_RATE = 0.25
_MAX_RATE = 4.0


def _release_lock(redis_client: Redis, token: str) -> None:
    try:
        redis_client.eval(_RELEASE_LOCK_LUA, 1, ROOM_STATE_LOCK, token)
    except AttributeError:
        if redis_client.get(ROOM_STATE_LOCK) == token:
            redis_client.delete(ROOM_STATE_LOCK)


@contextmanager
def _state_lock(redis_client: Redis) -> Iterator[None]:
    token = uuid.uuid4().hex
    deadline = time.monotonic() + (STATE_LOCK_WAIT_MS / 1000)
    while not redis_client.set(
        ROOM_STATE_LOCK, token, nx=True, px=STATE_LOCK_TTL_MS
    ):
        if time.monotonic() >= deadline:
            raise TimeoutError("watch room state lock timed out")
        time.sleep(0.005)
    try:
        yield
    finally:
        try:
            _release_lock(redis_client, token)
        except Exception:
            logger.warning("[cottage-watch] failed to release state lock", exc_info=True)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _coerce_rate(value: Any) -> float:
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return 1.0
    return min(_MAX_RATE, max(_MIN_RATE, rate))


def next_event_seq(redis_client: Redis) -> int:
    return int(redis_client.incr(ROOM_EVENT_SEQ))


def get_current_position_ms(state: dict[str, str]) -> int:
    """Compute the live playback head from the persisted state.

    While paused, the head is fixed at ``position_ms``. While playing, it
    advances by ``(now - started_at) * rate``.
    """
    if not state:
        return 0
    paused = state.get("paused", "1") == "1"
    base_position = int(state.get("position_ms", "0") or "0")
    if paused:
        return base_position
    started_at = int(state.get("started_at_ms", "0") or "0")
    if started_at == 0:
        return base_position
    rate = _coerce_rate(state.get("rate", "1"))
    return base_position + int(max(0, _now_ms() - started_at) * rate)


def _get_state_unlocked(redis_client: Redis) -> dict[str, Any]:
    """Snapshot the room for the route layer."""
    raw = redis_client.hgetall(ROOM_CURRENT) or {}
    event_seq = int(redis_client.get(ROOM_EVENT_SEQ) or 0)

    if raw and raw.get("source_url"):
        current = {
            "source_wsid": raw.get("source_wsid") or None,
            "source_url": raw.get("source_url") or None,
            "source_title": raw.get("source_title") or None,
            "source_kind": raw.get("source_kind") or None,
            "paused": raw.get("paused", "1") == "1",
            "position_ms": get_current_position_ms(raw),
            "rate": _coerce_rate(raw.get("rate", "1")),
            "started_by": raw.get("started_by") or None,
            "event_seq": int(raw.get("event_seq") or 0),
            "server_ts_ms": _now_ms(),
        }
    else:
        current = {
            "source_wsid": None,
            "source_url": None,
            "source_title": None,
            "source_kind": None,
            "paused": True,
            "position_ms": 0,
            "rate": 1.0,
            "started_by": None,
            "event_seq": event_seq,
            "server_ts_ms": _now_ms(),
        }
    return {"current": current, "event_seq": event_seq}


def get_state(redis_client: Redis) -> dict[str, Any]:
    with _state_lock(redis_client):
        return _get_state_unlocked(redis_client)


def _apply_event_unlocked(
    redis_client: Redis,
    type_: str,
    payload: dict[str, Any],
    origin_uid: str,
) -> dict[str, Any]:
    """Mutate the room based on an incoming event and return the broadcast
    envelope (new event_seq, origin_uid, server_ts_ms)."""
    seq = next_event_seq(redis_client)
    now = _now_ms()
    broadcast_payload = dict(payload)

    if type_ == "LOAD":
        redis_client.hset(
            ROOM_CURRENT,
            mapping={
                "source_wsid": str(payload.get("source_wsid") or ""),
                "source_url": str(payload.get("source_url") or ""),
                "source_title": str(payload.get("source_title") or ""),
                "source_kind": str(payload.get("source_kind") or ""),
                "started_by": origin_uid,
                "started_at_ms": str(now),
                "position_ms": str(int(payload.get("position_ms", 0) or 0)),
                "paused": "1",
                "rate": "1",
                "event_seq": str(seq),
            },
        )
    elif type_ == "PLAY":
        redis_client.hset(
            ROOM_CURRENT,
            mapping={
                "position_ms": str(int(payload.get("position_ms", 0) or 0)),
                "paused": "0",
                "started_at_ms": str(now),
                "event_seq": str(seq),
            },
        )
    elif type_ == "PAUSE":
        redis_client.hset(
            ROOM_CURRENT,
            mapping={
                "position_ms": str(int(payload.get("position_ms", 0) or 0)),
                "paused": "1",
                "started_at_ms": str(now),
                "event_seq": str(seq),
            },
        )
    elif type_ == "SEEK":
        redis_client.hset(
            ROOM_CURRENT,
            mapping={
                "position_ms": str(int(payload.get("position_ms", 0) or 0)),
                "started_at_ms": str(now),
                "event_seq": str(seq),
            },
        )
    elif type_ == "RATE":
        rate = _coerce_rate(payload.get("rate", 1))
        broadcast_payload["rate"] = rate
        redis_client.hset(
            ROOM_CURRENT,
            mapping={
                "rate": str(rate),
                "position_ms": str(int(payload.get("position_ms", 0) or 0)),
                "started_at_ms": str(now),
                "event_seq": str(seq),
            },
        )

    return {
        "type": type_,
        "payload": broadcast_payload,
        "event_seq": seq,
        "origin_uid": origin_uid,
        "server_ts_ms": now,
    }


def apply_event(
    redis_client: Redis,
    type_: str,
    payload: dict[str, Any],
    origin_uid: str,
) -> dict[str, Any]:
    with _state_lock(redis_client):
        return _apply_event_unlocked(redis_client, type_, payload, origin_uid)


def clear_room(redis_client: Redis) -> None:
    """Drop the current source (used when its WatchSource is deleted)."""
    with _state_lock(redis_client):
        redis_client.delete(ROOM_CURRENT)
