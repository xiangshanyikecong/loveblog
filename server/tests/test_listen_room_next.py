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

"""Tests for cottage-listen room NEXT idempotency."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
import unittest
from unittest.mock import patch

from app.services.listen_together import room


class FakeRedis:
    """Minimal decode_responses-style Redis subset used by listen room."""

    def __init__(self) -> None:
        self._strings: dict[str, str] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}

    def incr(self, key: str) -> int:
        value = int(self._strings.get(key, "0")) + 1
        self._strings[key] = str(value)
        return value

    def get(self, key: str):
        return self._strings.get(key)

    def set(self, key: str, value, nx: bool = False, px=None):
        if nx and key in self._strings:
            return None
        self._strings[key] = str(value)
        return True

    def delete(self, key: str):
        removed = 0
        for store in (self._strings, self._hashes, self._lists):
            if key in store:
                store.pop(key, None)
                removed += 1
        return removed

    def hgetall(self, key: str):
        return dict(self._hashes.get(key, {}))

    def hset(self, key: str, mapping: dict):
        target = self._hashes.setdefault(key, {})
        target.update({str(k): str(v) for k, v in mapping.items()})
        return len(mapping)

    def rpush(self, key: str, *values):
        target = self._lists.setdefault(key, [])
        target.extend(str(value) for value in values)
        return len(target)

    def lpop(self, key: str):
        target = self._lists.get(key, [])
        if not target:
            return None
        return target.pop(0)

    def lrange(self, key: str, start: int, end: int):
        target = self._lists.get(key, [])
        stop = None if end == -1 else end + 1
        return target[start:stop]


class BlockingRedis(FakeRedis):
    def __init__(self) -> None:
        super().__init__()
        self.write_started = Event()
        self.allow_write = Event()
        self._block_next_hash_write = True

    def hset(self, key: str, mapping: dict):
        if self._block_next_hash_write:
            self._block_next_hash_write = False
            self.write_started.set()
            if not self.allow_write.wait(timeout=2):
                raise TimeoutError("test did not release blocked room write")
        return super().hset(key, mapping)


class ListenRoomNextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.redis = FakeRedis()

    @patch("app.services.listen_together.room.listen_history.record_play")
    def test_auto_next_is_ignored_after_current_song_changes(self, _record_play) -> None:
        room.apply_event(
            self.redis,
            "PLAY",
            {
                "song_id": "song-a",
                "song_meta": {"song_id": "song-a", "name": "A", "artists": []},
            },
            "uid-a",
        )
        room.apply_event(
            self.redis,
            "QUEUE_APPEND",
            {
                "song_id": "song-b",
                "song_meta": {"song_id": "song-b", "name": "B", "artists": []},
            },
            "uid-a",
        )
        room.apply_event(
            self.redis,
            "QUEUE_APPEND",
            {
                "song_id": "song-c",
                "song_meta": {"song_id": "song-c", "name": "C", "artists": []},
            },
            "uid-a",
        )

        first = room.apply_event(
            self.redis,
            "NEXT",
            {"expected_song_id": "song-a"},
            "uid-a",
        )
        second = room.apply_event(
            self.redis,
            "NEXT",
            {"expected_song_id": "song-a"},
            "uid-b",
        )

        self.assertIsNotNone(first)
        self.assertEqual(first["payload"]["song_id"], "song-b")
        self.assertIsNone(second)
        self.assertIsNone(self.redis.get(room.ROOM_NEXT_LOCK))

        state = room.get_state(self.redis)
        self.assertEqual(state["current"]["song_id"], "song-b")
        self.assertEqual([item["song_id"] for item in state["queue"]], ["song-c"])

    @patch("app.services.listen_together.room.listen_history.record_play")
    def test_snapshot_waits_for_in_flight_multi_key_mutation(self, _record_play) -> None:
        redis_client = BlockingRedis()
        with ThreadPoolExecutor(max_workers=2) as executor:
            mutation = executor.submit(
                room.apply_event,
                redis_client,
                "PLAY",
                {
                    "song_id": "song-a",
                    "song_meta": {"song_id": "song-a", "name": "A", "artists": []},
                },
                "uid-a",
            )
            self.assertTrue(redis_client.write_started.wait(timeout=1))

            snapshot = executor.submit(room.get_state, redis_client)
            time.sleep(0.05)
            self.assertFalse(snapshot.done())

            redis_client.allow_write.set()
            event = mutation.result(timeout=1)
            state = snapshot.result(timeout=1)

        self.assertEqual(state["event_seq"], event["event_seq"])
        self.assertEqual(state["current"]["event_seq"], event["event_seq"])
        self.assertEqual(state["current"]["song_id"], "song-a")

    def test_lock_release_does_not_delete_a_new_owner(self) -> None:
        self.redis.set(room.ROOM_STATE_LOCK, "new-owner")
        room._release_lock(self.redis, room.ROOM_STATE_LOCK, "expired-owner")
        self.assertEqual(self.redis.get(room.ROOM_STATE_LOCK), "new-owner")

    def test_queue_remove_targets_the_requested_duplicate_index(self) -> None:
        for name in ("First", "Second"):
            room.apply_event(
                self.redis,
                "QUEUE_APPEND",
                {
                    "song_id": "same-song",
                    "song_meta": {"song_id": "same-song", "name": name, "artists": []},
                },
                "uid-a",
            )

        removed = room.apply_event(
            self.redis,
            "QUEUE_REMOVE",
            {"index": 1, "song_id": "same-song"},
            "uid-a",
        )

        self.assertIsNotNone(removed)
        self.assertEqual(removed["payload"]["index"], 1)
        state = room.get_state(self.redis)
        self.assertEqual(
            state["queue"],
            [{"song_id": "same-song", "name": "First", "artists": []}],
        )

    def test_queue_remove_rejects_a_stale_index_without_broadcasting(self) -> None:
        room.apply_event(
            self.redis,
            "QUEUE_APPEND",
            {
                "song_id": "same-song",
                "song_meta": {"song_id": "same-song", "name": "First", "artists": []},
            },
            "uid-a",
        )

        removed = room.apply_event(
            self.redis,
            "QUEUE_REMOVE",
            {"index": 1, "song_id": "same-song"},
            "uid-a",
        )

        self.assertIsNone(removed)
        self.assertEqual(
            room.get_state(self.redis)["queue"],
            [{"song_id": "same-song", "name": "First", "artists": []}],
        )

    @patch(
        "app.services.listen_together.room.listen_history.record_play",
        side_effect=RuntimeError("history database unavailable"),
    )
    def test_history_failure_does_not_drop_committed_room_event(self, _record_play) -> None:
        event = room.apply_event(
            self.redis,
            "PLAY",
            {
                "song_id": "song-a",
                "song_meta": {"song_id": "song-a", "name": "A", "artists": []},
            },
            "uid-a",
        )

        self.assertIsNotNone(event)
        self.assertEqual(event["type"], "PLAY")
        self.assertEqual(room.get_state(self.redis)["current"]["song_id"], "song-a")


if __name__ == "__main__":
    unittest.main()
