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

import asyncio
import unittest

from app.api.v1.ws_security import close_when_session_revoked, stop_session_watchdog


class _FakeWebSocket:
    def __init__(self) -> None:
        self.close_codes: list[int] = []

    async def close(self, *, code: int) -> None:
        self.close_codes.append(code)


class WebSocketSessionWatchdogTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolver_failure_closes_idle_socket_fail_closed(self) -> None:
        ws = _FakeWebSocket()

        def failing_resolver(_token: str):
            raise RuntimeError("authentication database unavailable")

        await asyncio.wait_for(
            close_when_session_revoked(
                ws,
                "token",
                failing_resolver,
                interval_seconds=0,
            ),
            timeout=1,
        )
        self.assertEqual(ws.close_codes, [4401])

    async def test_stopping_failed_watchdog_never_breaks_endpoint_cleanup(self) -> None:
        async def failed_watchdog() -> None:
            raise RuntimeError("watchdog failed before cleanup")

        task = asyncio.create_task(failed_watchdog())
        await asyncio.sleep(0)
        await stop_session_watchdog(task)
        self.assertTrue(task.done())


if __name__ == "__main__":
    unittest.main()
