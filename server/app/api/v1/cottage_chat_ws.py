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

"""WebSocket endpoint for the cottage realtime channel (presence + chat + poke).

Single endpoint ``WS /v1/cottage/chat/ws``. The socket is primarily a *push*
channel: chat messages, read receipts and pokes are produced by the REST layer
and fan out through :mod:`app.services.cottage_realtime`. The only thing a
client sends upstream is ``PING`` (keepalive). Presence is derived from the
live socket set — connecting / disconnecting broadcasts a ``PRESENCE`` event
to the partner.

Authentication mirrors ``cottage_listen_ws``: token from the ``access_token``
cookie or ``Authorization: Bearer`` header, never from the query string.
"""
from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.core.config import settings
from app.api.v1.ws_security import (
    close_when_session_revoked,
    stop_session_watchdog,
    websocket_origin_allowed,
)
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.services.cottage_realtime import manager, set_event_loop
from app.services.security import check_session_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cottage/chat", tags=["cottage-chat-ws"])

WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403

_PARTNER_ROLES = {UserRole.partner_a, UserRole.partner_b}


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
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
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
async def cottage_chat_ws(ws: WebSocket) -> None:
    if not websocket_origin_allowed(ws):
        await ws.close(code=WS_CLOSE_FORBIDDEN)
        return
    token = _extract_token(ws)
    user = _resolve_user(token) if token else None
    if user is None:
        await ws.close(code=WS_CLOSE_UNAUTHORIZED)
        return
    if user.role not in _PARTNER_ROLES:
        await ws.close(code=WS_CLOSE_FORBIDDEN)
        return

    # Capture the running loop so sync REST handlers can push frames.
    set_event_loop(asyncio.get_running_loop())

    await ws.accept()
    became_online = await manager.connect(user.uid, ws)
    session_watchdog = asyncio.create_task(
        close_when_session_revoked(ws, token or "", _resolve_user)
    )

    # Initial presence snapshot for this socket.
    try:
        await ws.send_json({"type": "PRESENCE_SNAPSHOT", "payload": {"online": manager.online_uids()}})
    except Exception:  # pragma: no cover - defensive
        pass

    if became_online:
        await manager.broadcast(
            {
                "type": "PRESENCE",
                "payload": {
                    "uid": user.uid,
                    "online": True,
                    "online_since": (
                        manager.online_since(user.uid).isoformat()
                        if manager.online_since(user.uid)
                        else None
                    ),
                    "last_active_at": (
                        manager.last_active_at(user.uid).isoformat()
                        if manager.last_active_at(user.uid)
                        else None
                    ),
                },
            },
            exclude_uid=user.uid,
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
                if not token or await asyncio.to_thread(_resolve_user, token) is None:
                    await ws.close(code=WS_CLOSE_UNAUTHORIZED)
                    break
                next_auth_check = time.monotonic() + 15
            manager.touch(user.uid)
            if msg.get("type") == "PING":
                try:
                    await ws.send_json({"type": "PONG"})
                except Exception:
                    break
            elif msg.get("type") == "TYPING":
                payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
                await manager.broadcast(
                    {
                        "type": "TYPING",
                        "payload": {
                            "uid": user.uid,
                            "nickname": user.nickname,
                            "is_typing": bool(payload.get("is_typing")),
                            "at": (
                                manager.last_active_at(user.uid).isoformat()
                                if manager.last_active_at(user.uid)
                                else None
                            ),
                        },
                    },
                    exclude_uid=user.uid,
                )
    finally:
        await stop_session_watchdog(session_watchdog)
        went_offline = await manager.disconnect(user.uid, ws)
        if went_offline:
            await manager.broadcast(
                {
                    "type": "PRESENCE",
                    "payload": {
                        "uid": user.uid,
                        "online": False,
                        "online_since": None,
                        "last_active_at": (
                            manager.last_active_at(user.uid).isoformat()
                            if manager.last_active_at(user.uid)
                            else None
                        ),
                    },
                },
                exclude_uid=user.uid,
            )
