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

"""WebSocket endpoint for cottage-listen-together real-time sync.

Single endpoint ``WS /v1/cottage/listen/ws``. Both partners connect, send
PLAY / PAUSE / SEEK / NEXT / PREV / QUEUE_* events upstream, and receive
those same events broadcast (after applying to Redis) plus system events
(LOGIN_OK / LOGOUT / COOKIE_EXPIRED) initiated by REST handlers.

Authentication mirrors ``app.api.deps.get_current_user``: prefer the
``access_token`` cookie, fall back to ``Authorization: Bearer <token>``.
We DO NOT accept token via query string (R5.1 — query strings end up in
access logs and that's an obvious cookie/leak vector here).
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
from app.services.listen_together.room import apply_event
from app.services.security import check_session_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cottage/listen", tags=["cottage-listen-ws"])


# ---------------------------------------------------------------------------
# WS close codes (R5.2 / R5.3)
# ---------------------------------------------------------------------------
WS_CLOSE_UNAUTHORIZED = 4401  # token invalid / missing
WS_CLOSE_FORBIDDEN = 4403    # token valid but role != partner_a / partner_b

_PARTNER_ROLES = {UserRole.partner_a, UserRole.partner_b}


# ---------------------------------------------------------------------------
# Connection manager — module singleton
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Tracks all currently-connected WebSockets in this backend process.

    There are at most two partners, but each partner can have multiple
    connected tabs. Broadcasts go to every connection.
    """

    def __init__(self) -> None:
        # uid -> list of WebSocket
        self._conns: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, uid: str, ws: WebSocket) -> None:
        async with self._lock:
            self._conns.setdefault(uid, []).append(ws)

    async def disconnect(self, uid: str, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._conns.get(uid)
            if conns and ws in conns:
                conns.remove(ws)
            if conns is not None and not conns:
                self._conns.pop(uid, None)

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Send the event JSON to every currently-connected client.

        Disconnected clients are detected by send failure and dropped from
        the registry. We don't await each send sequentially with heavy lock
        contention — copy the snapshot first then send outside the lock.
        """
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


# ---------------------------------------------------------------------------
# Handshake helper
# ---------------------------------------------------------------------------

def _extract_token(ws: WebSocket) -> str | None:
    """Read JWT from cookie or Authorization header. Never from query string."""
    cookie_token = ws.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    auth = ws.headers.get("authorization") or ws.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:]
    return None


def _resolve_user(token: str) -> User | None:
    """Validate the JWT and return the corresponding active User row.

    Returns None on any failure mode that should result in close 4401:
    missing token, decode error, expired session_version, deleted user.
    """
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
        # Detach so we can safely return after closing the session.
        db.expunge(user)
        return user
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def listen_together_ws(ws: WebSocket) -> None:  # noqa: PLR0912 — control-flow rich
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
    redis_client = get_redis()
    session_watchdog = asyncio.create_task(
        close_when_session_revoked(ws, token, _resolve_user)
    )

    try:
        next_auth_check = time.monotonic() + 15
        while True:
            try:
                msg = await ws.receive_json()
            except WebSocketDisconnect:
                break
            except Exception:
                # Bad JSON or other transport error — drop frame, continue.
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
                # 更新用户在线状态
                from app.services.listen_together.presence import update_presence
                update_presence(redis_client, user.uid)
                continue
            if type_ in (
                "PLAY", "PAUSE", "SEEK", "NEXT", "PREV",
                "QUEUE_APPEND", "QUEUE_REMOVE", "QUEUE_CLEAR",
            ):
                # apply_event does synchronous Redis I/O and, for PLAY/NEXT, a
                # DB write via record_play. Run it off the event loop so it can't
                # stall every other socket served by this process.
                event = await asyncio.to_thread(
                    apply_event, redis_client, type_, payload, user.uid
                )
                if event is not None:
                    await manager.broadcast(event)
            # else: ignore unknown / system event types (LOGIN_OK / LOGOUT /
            # COOKIE_EXPIRED are originated only by the REST layer, not by
            # clients).
    finally:
        await stop_session_watchdog(session_watchdog)
        await manager.disconnect(user.uid, ws)
