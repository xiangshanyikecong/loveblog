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

"""Redis-backed room state for cottage-listen-together.

Three Redis keys make up the room:

- ``cottage_listen:current`` (Hash) — current playback state
- ``cottage_listen:queue`` (List)  — upcoming songs (JSON strings with metadata)
- ``cottage_listen:event_seq`` (String) — monotonically increasing counter

Concurrency note: :func:`apply_event` and :func:`get_state` share a short-lived
Redis lease. The lease serializes the multiple Redis keys into one logical
state so reconnect snapshots cannot combine a new ``event_seq`` with stale
``current`` or ``queue`` data.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import json
import logging
import secrets
import time
from typing import Any
import uuid

from redis import Redis

from app.services.listen_together import history as listen_history

logger = logging.getLogger(__name__)

ROOM_CURRENT = "cottage_listen:current"
ROOM_QUEUE = "cottage_listen:queue"
ROOM_EVENT_SEQ = "cottage_listen:event_seq"
ROOM_NEXT_LOCK = "cottage_listen:next_lock"
ROOM_STATE_LOCK = "cottage_listen:state_lock"
NEXT_LOCK_TTL_MS = 2000
STATE_LOCK_TTL_MS = 30_000
STATE_LOCK_WAIT_MS = 5_000

_QUEUE_REMOVE_LUA = """
local current = redis.call('LINDEX', KEYS[1], tonumber(ARGV[1]))
if not current or current ~= ARGV[2] then
  return 0
end
redis.call('LSET', KEYS[1], tonumber(ARGV[1]), ARGV[3])
redis.call('LREM', KEYS[1], 1, ARGV[3])
return 1
"""

_RELEASE_LOCK_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


def _release_lock(redis_client: Redis, key: str, token: str) -> None:
    """Release only the lock generation owned by this caller."""
    try:
        redis_client.eval(_RELEASE_LOCK_LUA, 1, key, token)
    except AttributeError:
        # Small in-memory fakes used by unit tests do not implement EVAL.
        if redis_client.get(key) == token:
            redis_client.delete(key)


@contextmanager
def _state_lock(redis_client: Redis) -> Iterator[None]:
    """Serialize the multi-key room state into a coherent snapshot.

    Redis guarantees atomicity per command, not across the hash, list and
    sequence keys that form this room. Without this lock, reconnect could read
    a newly incremented event sequence alongside the previous current/queue,
    then permanently discard the matching broadcast as already seen.
    """
    token = uuid.uuid4().hex
    deadline = time.monotonic() + (STATE_LOCK_WAIT_MS / 1000)
    while not redis_client.set(
        ROOM_STATE_LOCK, token, nx=True, px=STATE_LOCK_TTL_MS
    ):
        if time.monotonic() >= deadline:
            raise TimeoutError("listen room state lock timed out")
        time.sleep(0.005)
    try:
        yield
    finally:
        try:
            _release_lock(redis_client, ROOM_STATE_LOCK, token)
        except Exception:
            # The lease has a TTL, so an unavailable Redis cannot leave this
            # room locked forever. Do not mask the actual room operation.
            logger.warning("[cottage-listen] failed to release state lock", exc_info=True)


def _queue_item_song_id(item: str) -> str:
    try:
        parsed = json.loads(item)
        return str(parsed.get("song_id")) if isinstance(parsed, dict) else str(parsed)
    except (json.JSONDecodeError, ValueError, TypeError):
        return str(item)


def _atomic_remove_queue_item(redis_client: Redis, *, index: int, expected: str) -> bool:
    """Compare-and-remove one list element without replacing the whole queue."""
    marker = f"__love_removed__:{secrets.token_hex(16)}"
    try:
        return bool(redis_client.eval(_QUEUE_REMOVE_LUA, 1, ROOM_QUEUE, index, expected, marker))
    except AttributeError:
        # Small in-memory fakes used by unit tests do not implement EVAL.
        items = list(redis_client.lrange(ROOM_QUEUE, 0, -1) or [])
        if not (0 <= index < len(items)) or items[index] != expected:
            return False
        items.pop(index)
        redis_client.delete(ROOM_QUEUE)
        if items:
            redis_client.rpush(ROOM_QUEUE, *items)
        return True


def _now_ms() -> int:
    return int(time.time() * 1000)


def next_event_seq(redis_client: Redis) -> int:
    return int(redis_client.incr(ROOM_EVENT_SEQ))


def _record_play_best_effort(
    *,
    song_id: str,
    song_meta: dict[str, Any] | None,
    started_by_uid: str,
) -> None:
    try:
        listen_history.record_play(
            song_id=song_id,
            song_meta=song_meta,
            started_by_uid=started_by_uid,
        )
    except Exception:
        # Redis is the room's realtime source of truth. A history database
        # outage must not suppress the broadcast after state already changed.
        logger.warning("[cottage-listen] failed to record play history", exc_info=True)


def _release_next_lock(redis_client: Redis, token: str) -> None:
    try:
        _release_lock(redis_client, ROOM_NEXT_LOCK, token)
    except Exception:
        logger.warning("[cottage-listen] failed to release NEXT lock", exc_info=True)


def _current_song_matches_expected(redis_client: Redis, expected_song_id: Any) -> bool:
    if expected_song_id is None:
        return True
    current = redis_client.hgetall(ROOM_CURRENT) or {}
    return str(current.get("song_id") or "") == str(expected_song_id)


def get_current_position_ms(state: dict[str, str]) -> int:
    """Compute the current playback head from the persisted state.

    Used by GET /state to synthesize a 'live' position. While paused, the
    head is fixed at ``position_ms``. While playing, it advances by
    (now - started_at_ms) on top of ``position_ms``. Both fields are stored
    as strings in the Hash; we coerce here.
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
    return base_position + max(0, _now_ms() - started_at)


def _get_state_unlocked(redis_client: Redis) -> dict[str, Any]:
    """Snapshot the room.

    Returns a dict shaped for direct consumption by the route layer.
    Empty room:
        {"current": {song_id: None, ...}, "queue": [], "event_seq": 0}
    """
    import json

    raw_current = redis_client.hgetall(ROOM_CURRENT) or {}
    raw_queue = list(redis_client.lrange(ROOM_QUEUE, 0, -1) or [])
    event_seq = int(redis_client.get(ROOM_EVENT_SEQ) or 0)

    # Parse queue items - they can be either JSON strings (new format) or plain song_ids (legacy)
    queue = []
    for item in raw_queue:
        try:
            # Try to parse as JSON first (new format with metadata)
            parsed = json.loads(item)
            if isinstance(parsed, dict):
                queue.append(parsed)
            else:
                # If it's just a string song_id wrapped in JSON
                queue.append({"song_id": str(parsed), "name": "", "artists": []})
        except ValueError:
            # Legacy format: plain song_id string (json.JSONDecodeError ⊂ ValueError)
            queue.append({"song_id": str(item), "name": "", "artists": []})

    if raw_current and raw_current.get("song_id"):
        # Try to parse stored song_meta
        song_meta_dict = None
        if raw_current.get("song_meta"):
            try:
                song_meta_dict = json.loads(raw_current["song_meta"])
            except (TypeError, ValueError):
                # Corrupt/legacy song_meta — fall back to None and continue.
                song_meta_dict = None

        current = {
            "song_id": raw_current.get("song_id"),
            "song_meta": song_meta_dict,  # May be None if not stored or parse failed
            "started_by": raw_current.get("started_by"),
            "started_at_ms": int(raw_current.get("started_at_ms") or 0),
            "position_ms": get_current_position_ms(raw_current),
            "paused": raw_current.get("paused", "0") == "1",
            "event_seq": int(raw_current.get("event_seq") or 0),
            "server_ts_ms": _now_ms(),
        }
    else:
        current = {
            "song_id": None,
            "song_meta": None,
            "started_by": None,
            "started_at_ms": 0,
            "position_ms": 0,
            "paused": True,
            "event_seq": event_seq,
            "server_ts_ms": _now_ms(),
        }

    return {"current": current, "queue": queue, "event_seq": event_seq}


def get_state(redis_client: Redis) -> dict[str, Any]:
    with _state_lock(redis_client):
        return _get_state_unlocked(redis_client)


def _apply_event_unlocked(
    redis_client: Redis,
    type_: str,
    payload: dict[str, Any],
    origin_uid: str,
) -> dict[str, Any] | None:
    """Mutate the room based on an incoming event and return the broadcast
    envelope (with new event_seq, origin_uid, server_ts_ms).
    """
    import json

    next_lock_token = None
    expected_song_id = payload.get("expected_song_id") if type_ == "NEXT" else None
    if expected_song_id is not None:
        next_lock_token = uuid.uuid4().hex
        if not redis_client.set(ROOM_NEXT_LOCK, next_lock_token, nx=True, px=NEXT_LOCK_TTL_MS):
            return None
        if not _current_song_matches_expected(redis_client, expected_song_id):
            _release_next_lock(redis_client, next_lock_token)
            return None

    try:
        seq = next_event_seq(redis_client)
        now = _now_ms()

        # This will be the payload we broadcast (may be enriched with metadata)
        broadcast_payload = dict(payload)

        if type_ == "PLAY":
            position_ms = int(payload.get("position_ms", 0) or 0)
            song_id = str(payload.get("song_id") or "")
            # Store song_meta in Redis if provided (for better state recovery)
            song_meta_json = ""
            if payload.get("song_meta"):
                try:
                    song_meta_json = json.dumps(payload["song_meta"])
                    # Ensure broadcast includes the metadata
                    broadcast_payload["song_meta"] = payload["song_meta"]
                except (TypeError, ValueError) as exc:
                    # Non-serializable meta: keep the empty fallback but leave a trace
                    # instead of silently swallowing the error.
                    logger.warning("Failed to serialize song_meta for room broadcast: %s", exc)
            redis_client.hset(
                ROOM_CURRENT,
                mapping={
                    "song_id": song_id,
                    "song_meta": song_meta_json,  # Store as JSON string
                    "started_by": origin_uid,
                    "started_at_ms": str(now),
                    "position_ms": str(position_ms),
                    "paused": "0",
                    "event_seq": str(seq),
                },
            )
            _record_play_best_effort(
                song_id=song_id,
                song_meta=payload.get("song_meta") if isinstance(payload.get("song_meta"), dict) else None,
                started_by_uid=origin_uid,
            )
        elif type_ == "PAUSE":
            position_ms = int(payload.get("position_ms", 0) or 0)
            redis_client.hset(
                ROOM_CURRENT,
                mapping={
                    "position_ms": str(position_ms),
                    "paused": "1",
                    "started_at_ms": str(now),
                    "event_seq": str(seq),
                },
            )
        elif type_ == "SEEK":
            position_ms = int(payload.get("position_ms", 0) or 0)
            redis_client.hset(
                ROOM_CURRENT,
                mapping={
                    "position_ms": str(position_ms),
                    "started_at_ms": str(now),
                    "event_seq": str(seq),
                },
            )
        elif type_ == "NEXT":
            # Pop head of queue, set as current.
            next_song_raw = redis_client.lpop(ROOM_QUEUE)
            if next_song_raw:
                # Try to parse as JSON (new format with metadata)
                song_id = None
                song_meta_json = ""
                song_meta_dict = None
                try:
                    next_song_data = json.loads(next_song_raw)
                    if isinstance(next_song_data, dict):
                        song_id = str(next_song_data.get("song_id", ""))
                        song_meta_json = json.dumps(next_song_data)
                        song_meta_dict = next_song_data
                    else:
                        # Legacy: just a song_id string
                        song_id = str(next_song_data)
                except ValueError:
                    # Legacy format: plain song_id (json.JSONDecodeError is a ValueError)
                    song_id = str(next_song_raw)

                if song_id:
                    redis_client.hset(
                        ROOM_CURRENT,
                        mapping={
                            "song_id": song_id,
                            "song_meta": song_meta_json,
                            "started_by": origin_uid,
                            "started_at_ms": str(now),
                            "position_ms": "0",
                            "paused": "0",
                            "event_seq": str(seq),
                        },
                    )
                    # Include the song metadata in the broadcast payload.
                    broadcast_payload["song_id"] = song_id
                    if song_meta_dict:
                        broadcast_payload["song_meta"] = song_meta_dict
                    _record_play_best_effort(
                        song_id=song_id,
                        song_meta=song_meta_dict,
                        started_by_uid=origin_uid,
                    )
                else:
                    redis_client.delete(ROOM_CURRENT)
            else:
                # Queue empty, clear current.
                redis_client.delete(ROOM_CURRENT)
        elif type_ == "PREV":
            # Without history we restart the current song from 0.
            redis_client.hset(
                ROOM_CURRENT,
                mapping={
                    "started_at_ms": str(now),
                    "position_ms": "0",
                    "paused": "0",
                    "event_seq": str(seq),
                },
            )
        elif type_ == "QUEUE_APPEND":
            song_id = str(payload.get("song_id") or "")
            if song_id:
                # Store the full song metadata as JSON.
                song_data = payload.get("song_meta", {})
                if not song_data or not isinstance(song_data, dict):
                    # Fallback: create minimal metadata.
                    song_data = {"song_id": song_id, "name": "", "artists": []}
                else:
                    # Ensure song_id is in the metadata.
                    song_data["song_id"] = song_id

                try:
                    song_json = json.dumps(song_data)
                    redis_client.rpush(ROOM_QUEUE, song_json)
                    # Ensure broadcast includes the full metadata.
                    broadcast_payload["song_meta"] = song_data
                except Exception:
                    # Fallback to legacy format if JSON serialization fails.
                    redis_client.rpush(ROOM_QUEUE, song_id)
        elif type_ == "QUEUE_REMOVE":
            song_id = str(payload.get("song_id") or "")
            raw_index = payload.get("index")
            removed_index: int | None = None

            if raw_index is not None:
                try:
                    item_index = int(raw_index)
                except (TypeError, ValueError):
                    return None

                items = list(redis_client.lrange(ROOM_QUEUE, 0, -1) or [])
                if not (0 <= item_index < len(items)):
                    return None

                expected = items[item_index]
                if song_id and _queue_item_song_id(expected) != song_id:
                    return None
                if not _atomic_remove_queue_item(
                    redis_client,
                    index=item_index,
                    expected=expected,
                ):
                    return None
                removed_index = item_index
            elif song_id:
                # Older clients did not send an index. Preserve their behavior
                # by removing the first matching entry, but broadcast its index
                # so current clients remove the same queue instance.
                for _ in range(3):
                    items = list(redis_client.lrange(ROOM_QUEUE, 0, -1) or [])
                    match = next(
                        (
                            (item_index, raw)
                            for item_index, raw in enumerate(items)
                            if _queue_item_song_id(raw) == song_id
                        ),
                        None,
                    )
                    if match is None:
                        break
                    if _atomic_remove_queue_item(
                        redis_client,
                        index=match[0],
                        expected=match[1],
                    ):
                        removed_index = match[0]
                        break

                if removed_index is None:
                    return None
            else:
                return None

            broadcast_payload["index"] = removed_index
        elif type_ == "QUEUE_CLEAR":
            redis_client.delete(ROOM_QUEUE)
        # LOGIN_OK / LOGOUT / COOKIE_EXPIRED are passthrough — they don't mutate
        # current/queue, only the partners' login state which is computed live.

        return {
            "type": type_,
            "payload": broadcast_payload,  # Use enriched payload
            "event_seq": seq,
            "origin_uid": origin_uid,
            "server_ts_ms": now,
        }
    finally:
        if next_lock_token is not None:
            _release_next_lock(redis_client, next_lock_token)


def apply_event(
    redis_client: Redis,
    type_: str,
    payload: dict[str, Any],
    origin_uid: str,
) -> dict[str, Any] | None:
    with _state_lock(redis_client):
        return _apply_event_unlocked(redis_client, type_, payload, origin_uid)
