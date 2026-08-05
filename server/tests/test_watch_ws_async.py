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

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import WebSocketDisconnect

from app.api.v1 import cottage_watch_ws
from app.models.user import UserRole


class _FakeWebSocket:
    cookies = {"access_token": "test-token"}
    headers: dict[str, str] = {}

    def __init__(self) -> None:
        self.receive_count = 0
        self.sent: list[dict] = []

    async def accept(self) -> None:
        return None

    async def receive_json(self) -> dict:
        self.receive_count += 1
        if self.receive_count == 1:
            return {"type": "PLAY", "payload": {"position_ms": 100}}
        raise WebSocketDisconnect()

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self, code: int) -> None:
        return None


class WatchWebSocketAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_room_redis_mutation_runs_off_the_event_loop(self) -> None:
        websocket = _FakeWebSocket()
        user = SimpleNamespace(uid="partner-a", role=UserRole.partner_a)
        event_loop_thread = threading.get_ident()
        mutation_threads: list[int] = []

        def apply_event(_redis, type_, payload, uid):
            mutation_threads.append(threading.get_ident())
            return {"type": type_, "payload": payload, "origin_uid": uid}

        with (
            patch.object(cottage_watch_ws, "_resolve_user", return_value=user),
            patch.object(cottage_watch_ws, "get_redis", return_value=object()),
            patch.object(cottage_watch_ws.presence, "mark_online"),
            patch.object(cottage_watch_ws.presence, "mark_offline"),
            patch.object(cottage_watch_ws.room, "apply_event", side_effect=apply_event),
        ):
            await cottage_watch_ws.watch_together_ws(websocket)

        self.assertEqual(len(mutation_threads), 1)
        self.assertNotEqual(mutation_threads[0], event_loop_thread)


if __name__ == "__main__":
    unittest.main()
