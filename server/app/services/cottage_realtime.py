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

"""In-process realtime hub for the cottage (小屋) two-person channel.

Powers three features over a single WebSocket (``/v1/cottage/chat/ws``):

- **Presence** — who is currently connected (derived from live sockets, so it
  reflects reality exactly rather than a heartbeat guess).
- **Chat** — new messages are persisted by the REST layer, then pushed here.
- **Poke** — lightweight nudges (想你了 / 抱抱 / 戳一戳) pushed in real time.

Design notes
------------
There are at most two partner accounts, each possibly with several open tabs,
so an in-memory ``dict[uid, list[WebSocket]]`` is more than enough and keeps
chat working even when Redis is down.

The REST handlers are synchronous (run in a threadpool by FastAPI). To push
WebSocket frames from there we capture the uvicorn event loop once and use
``asyncio.run_coroutine_threadsafe`` via the ``schedule_*`` helpers.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class CottageRealtimeManager:
    def __init__(self) -> None:
        # uid -> list of live WebSocket connections (one per open tab)
        self._conns: dict[str, list[WebSocket]] = {}
        self._online_since: dict[str, datetime] = {}
        self._last_active_at: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def connect(self, uid: str, ws: WebSocket) -> bool:
        """Register a socket. Returns True if ``uid`` just came online."""
        async with self._lock:
            conns = self._conns.setdefault(uid, [])
            became_online = len(conns) == 0
            conns.append(ws)
            now = datetime.now(timezone.utc)
            self._last_active_at[uid] = now
            if became_online:
                self._online_since[uid] = now
            return became_online

    async def disconnect(self, uid: str, ws: WebSocket) -> bool:
        """Unregister a socket. Returns True if ``uid`` went fully offline."""
        async with self._lock:
            conns = self._conns.get(uid)
            if conns and ws in conns:
                conns.remove(ws)
            went_offline = not self._conns.get(uid)
            if conns is not None and not conns:
                self._conns.pop(uid, None)
                self._online_since.pop(uid, None)
                self._last_active_at[uid] = datetime.now(timezone.utc)
            return went_offline

    def is_online(self, uid: str) -> bool:
        return bool(self._conns.get(uid))

    def online_uids(self) -> list[str]:
        return [uid for uid, conns in self._conns.items() if conns]

    def touch(self, uid: str, at: datetime | None = None) -> None:
        self._last_active_at[uid] = at or datetime.now(timezone.utc)

    def online_since(self, uid: str | None) -> datetime | None:
        if not uid:
            return None
        return self._online_since.get(uid)

    def last_active_at(self, uid: str | None) -> datetime | None:
        if not uid:
            return None
        return self._last_active_at.get(uid)

    async def _snapshot(self) -> list[tuple[str, WebSocket]]:
        async with self._lock:
            return [(uid, ws) for uid, conns in self._conns.items() for ws in conns]

    async def broadcast(self, event: dict[str, Any], *, exclude_uid: str | None = None) -> None:
        snapshot = await self._snapshot()
        targets = [(uid, ws) for uid, ws in snapshot if exclude_uid is None or uid != exclude_uid]
        results = await asyncio.gather(
            *(self._safe_send(ws, event) for _, ws in targets), return_exceptions=True
        )
        await self._cleanup_dead(targets, results)

    async def broadcast_batch(self, events: list[dict[str, Any]], *, exclude_uid: str | None = None) -> None:
        """Send multiple events to all connections in a single pass."""
        if not events:
            return
        snapshot = await self._snapshot()
        targets = [(uid, ws) for uid, ws in snapshot if exclude_uid is None or uid != exclude_uid]

        async def send_all(ws: WebSocket) -> None:
            for event in events:
                await ws.send_json(event)

        results = await asyncio.gather(
            *(send_all(ws) for _, ws in targets), return_exceptions=True
        )
        await self._cleanup_dead(targets, results)

    async def send_to(self, uid: str, event: dict[str, Any]) -> None:
        async with self._lock:
            conns = list(self._conns.get(uid, []))
        results = await asyncio.gather(
            *(self._safe_send(ws, event) for ws in conns), return_exceptions=True
        )
        targets = [(uid, ws) for ws in conns]
        await self._cleanup_dead(targets, results)

    @staticmethod
    async def _safe_send(ws: WebSocket, event: dict[str, Any]) -> None:
        await ws.send_json(event)

    async def _cleanup_dead(
        self, targets: list[tuple[str, WebSocket]], results: list[Any]
    ) -> None:
        for (uid, ws), result in zip(targets, results):
            if isinstance(result, Exception):
                await self.disconnect(uid, ws)


manager = CottageRealtimeManager()


# ---------------------------------------------------------------------------
# Cross-thread scheduling (sync REST handlers -> async loop)
# ---------------------------------------------------------------------------

_loop: asyncio.AbstractEventLoop | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Remember the running uvicorn loop so sync code can schedule pushes."""
    global _loop
    _loop = loop


def _schedule(coro: Any) -> None:
    loop = _loop
    if loop is None:
        # No loop captured yet (e.g. a REST call before any WS connected and
        # before startup hook ran). The message is still persisted; we simply
        # skip the live push — clients reconcile on next fetch / reconnect.
        coro.close()
        return
    try:
        asyncio.run_coroutine_threadsafe(coro, loop)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to schedule cottage realtime push")


def schedule_broadcast(event: dict[str, Any], *, exclude_uid: str | None = None) -> None:
    _schedule(manager.broadcast(event, exclude_uid=exclude_uid))


def schedule_broadcast_batch(events: list[dict[str, Any]], *, exclude_uid: str | None = None) -> None:
    _schedule(manager.broadcast_batch(events, exclude_uid=exclude_uid))


def schedule_send_to(uid: str, event: dict[str, Any]) -> None:
    _schedule(manager.send_to(uid, event))


def schedule_coroutine(coro: Any) -> None:
    """Schedule an arbitrary coroutine on the captured uvicorn loop.

    Lets other features (e.g. cottage-listen) push WS frames from synchronous
    REST handlers — which FastAPI runs in a worker thread that has no running
    event loop — by reusing the single loop captured at startup via
    ``set_event_loop`` + ``run_coroutine_threadsafe``. If no loop is captured
    yet the coroutine is closed and the live push skipped (clients reconcile on
    their next fetch / reconnect).
    """
    _schedule(coro)
