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

"""WebSocket endpoint for cottage 一起看 (watch-together) real-time sync.

Single endpoint ``WS /v1/cottage/watch/ws``. Both partners connect, send
LOAD / PLAY / PAUSE / SEEK / RATE events upstream, and receive those same
events broadcast (after applying to Redis). PRESENCE events are emitted by the
server when a partner joins / leaves so each side can show "对方也在看".

Auth mirrors ``cottage_listen_ws``: prefer the ``access_token`` cookie, fall
back to ``Authorization: Bearer <token>``; never a query string (R5.1).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.api.v1.ws_security import (
    close_when_session_revoked,
    stop_session_watchdog,
    websocket_origin_allowed,
)
from app.core.config import settings
from app.db.redis import get_redis
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.services.security import check_session_version
from app.services.watch_together import presence, room

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cottage/watch", tags=["cottage-watch-ws"])


WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403

_PARTNER_ROLES = {UserRole.partner_a, UserRole.partner_b}


class ConnectionManager:
    """Tracks watch-room WebSocket connections in this backend process.

    At most two partners, each possibly with several tabs. Broadcasts go to
    every connection.
    """

    def __init__(self) -> None:
        self._conns: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, uid: str, ws: WebSocket) -> None:
        async with self._lock:
            self._conns.setdefault(uid, []).append(ws)

    async def disconnect(self, uid: str, ws: WebSocket) -> bool:
        """Remove a connection. Returns True if the uid has no tabs left."""
        async with self._lock:
            conns = self._conns.get(uid)
            if conns and ws in conns:
                conns.remove(ws)
            if conns is not None and not conns:
                self._conns.pop(uid, None)
                return True
            return uid not in self._conns

    async def broadcast(self, event: dict[str, Any]) -> None:
        async with self._lock:
            snapshot = [
                (uid, ws)
                for uid, ws_list in self._conns.items()
                for ws in ws_list
            ]
        dead: list[tuple[str, WebSocket]] = []
        for uid, ws in snapshot:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append((uid, ws))
        for uid, ws in dead:
            await self.disconnect(uid, ws)


manager = ConnectionManager()


def _extract_token(ws: WebSocket) -> str | None:
    cookie_token = ws.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    auth = ws.headers.get("authorization") or ws.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:]
    return None


def _resolve_user(token: str) -> User | None:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None

    uid = payload.get("sub")
    token_type = payload.get("type")
    if not uid or token_type != "access":
        return None

    session_version = payload.get("session_version")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.uid == uid, User.deleted_at.is_(None)).first()
        if (
            user is None
            or user.role not in _PARTNER_ROLES
            or user.is_banned
            or user.permission_status == "banned"
            or not check_session_version(user, session_version)
        ):
            return None
        db.expunge(user)
        return user
    finally:
        db.close()


@router.websocket("/ws")
async def watch_together_ws(ws: WebSocket) -> None:
    if not websocket_origin_allowed(ws):
        await ws.close(code=WS_CLOSE_FORBIDDEN)
        return
    token = _extract_token(ws)
    if not token:
        await ws.close(code=WS_CLOSE_UNAUTHORIZED)
        return
    user = _resolve_user(token)
    if user is None:
        await ws.close(code=WS_CLOSE_UNAUTHORIZED)
        return
    if user.role not in _PARTNER_ROLES:
        await ws.close(code=WS_CLOSE_FORBIDDEN)
        return

    await ws.accept()
    await manager.connect(user.uid, ws)
    session_watchdog = asyncio.create_task(
        close_when_session_revoked(ws, token, _resolve_user)
    )
    redis_client = get_redis()
    try:
        presence.mark_online(redis_client, user.uid)
    except Exception:
        logger.warning("[cottage-watch] presence mark_online failed")
    await manager.broadcast(
        {"type": "PRESENCE", "payload": {"user_uid": user.uid, "online": True}}
    )

    try:
        next_auth_check = time.monotonic() + 15
        while True:
            try:
                msg = await ws.receive_json()
            except WebSocketDisconnect:
                break
            except Exception:
                continue
            if not isinstance(msg, dict):
                continue
            if time.monotonic() >= next_auth_check:
                if await asyncio.to_thread(_resolve_user, token) is None:
                    await ws.close(code=WS_CLOSE_UNAUTHORIZED)
                    break
                next_auth_check = time.monotonic() + 15

            type_ = msg.get("type")
            payload = msg.get("payload") or {}
            if type_ == "PING":
                await ws.send_json({"type": "PONG"})
                continue
            if type_ == "HEARTBEAT":
                try:
                    presence.mark_online(redis_client, user.uid)
                except Exception:
                    pass
                continue
            if type_ in room.WATCH_EVENT_TYPES:
                # The room mutation performs synchronous Redis I/O and may
                # wait for its cross-process state lease. Keep that work off
                # the event loop so one contended room event cannot stall all
                # WebSockets served by this worker.
                event = await asyncio.to_thread(
                    room.apply_event, redis_client, type_, payload, user.uid
                )
                await manager.broadcast(event)
            # Unknown types (including server-originated PRESENCE) are ignored.
    finally:
        await stop_session_watchdog(session_watchdog)
        last_tab = await manager.disconnect(user.uid, ws)
        if last_tab:
            try:
                presence.mark_offline(redis_client, user.uid)
            except Exception:
                pass
            await manager.broadcast(
                {"type": "PRESENCE", "payload": {"user_uid": user.uid, "online": False}}
            )
