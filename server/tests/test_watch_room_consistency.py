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

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
import unittest

from app.services.watch_together import room


class BlockingRedis:
    def __init__(self) -> None:
        self.strings: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.write_started = Event()
        self.allow_write = Event()
        self.block_next_hash_write = True

    def set(self, key: str, value, *, nx: bool = False, px=None):
        if nx and key in self.strings:
            return None
        self.strings[key] = str(value)
        return True

    def get(self, key: str):
        return self.strings.get(key)

    def incr(self, key: str) -> int:
        value = int(self.strings.get(key, "0")) + 1
        self.strings[key] = str(value)
        return value

    def hset(self, key: str, mapping: dict):
        if self.block_next_hash_write:
            self.block_next_hash_write = False
            self.write_started.set()
            if not self.allow_write.wait(timeout=2):
                raise TimeoutError("test did not release blocked watch-room write")
        target = self.hashes.setdefault(key, {})
        target.update({str(field): str(value) for field, value in mapping.items()})

    def hgetall(self, key: str):
        return dict(self.hashes.get(key, {}))

    def delete(self, key: str):
        self.strings.pop(key, None)
        self.hashes.pop(key, None)


class WatchRoomConsistencyTests(unittest.TestCase):
    def test_snapshot_waits_for_in_flight_hash_and_sequence_mutation(self) -> None:
        redis_client = BlockingRedis()
        with ThreadPoolExecutor(max_workers=2) as executor:
            mutation = executor.submit(
                room.apply_event,
                redis_client,
                "LOAD",
                {"source_wsid": "video-a", "source_url": "/uploads/video.mp4"},
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
        self.assertEqual(state["current"]["source_wsid"], "video-a")


if __name__ == "__main__":
    unittest.main()
