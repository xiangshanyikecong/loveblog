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

"""WebSocket endpoint for the cottage 双人协作画板 (shared whiteboard).

Single endpoint ``WS /v1/cottage/canvas/ws``. This is a *pure relay*: the
server keeps no canvas state (strokes are far too chatty to persist), it only
tracks presence and forwards drawing frames between the two partners. Each
client keeps its own copy of the canvas; a late joiner asks the peer for a
``SYNC`` snapshot.

Frame types (client → server, relayed to the partner verbatim):

- ``STROKE``     — an in-progress / finished stroke segment
- ``CLEAR``      — wipe the board
- ``CURSOR``     — pointer position (for the "对方正在画" ghost cursor)
- ``UNDO``       — undo the last stroke
- ``SYNC_REQUEST`` / ``SYNC`` — late-joiner full-canvas handshake

Auth, presence and error isolation mirror ``cottage_games_ws`` exactly.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v1.cottage_games_ws import (
    WS_CLOSE_FORBIDDEN,
    WS_CLOSE_UNAUTHORIZED,
    ConnectionManager,
    _extract_token,
    _resolve_user,
    _PARTNER_ROLES,
)
from app.api.v1.ws_security import (
    close_when_session_revoked,
    stop_session_watchdog,
    websocket_origin_allowed,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cottage/canvas", tags=["cottage-canvas-ws"])

# One shared whiteboard room for the couple (at most two partners, multi-tab).
manager = ConnectionManager()

# Relay frames we forward to the partner. Anything else is ignored so the
# socket can never be used to broadcast arbitrary payloads.
_RELAY_TYPES = {"STROKE", "CLEAR", "CURSOR", "UNDO", "SYNC_REQUEST", "SYNC"}


def _now_ms() -> int:
    return int(time.time() * 1000)


@router.websocket("/ws")
async def cottage_canvas_ws(ws: WebSocket) -> None:
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

    await ws.accept()
    became_online = await manager.connect(user.uid, ws)

    session_watchdog = asyncio.create_task(
        close_when_session_revoked(ws, token or "", _resolve_user)
    )
    try:
        await ws.send_json({"type": "PRESENCE_SNAPSHOT", "payload": {"online": manager.online_uids()}})
    except Exception:
        pass

    if became_online:
        await manager.broadcast({"type": "PRESENCE", "payload": {"uid": user.uid, "online": True}})

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

            mtype = msg.get("type")
            if mtype == "PING":
                try:
                    await ws.send_json({"type": "PONG"})
                except Exception:
                    break
                continue

            if mtype not in _RELAY_TYPES:
                continue

            payload = msg.get("payload")
            frame: dict[str, Any] = {
                "type": mtype,
                "payload": payload if isinstance(payload, (dict, list)) else {},
                "from_uid": user.uid,
                "server_ts_ms": _now_ms(),
            }
            try:
                # Echo strokes / cursor only to the partner; a SYNC reply is
                # likewise meant for the other tab that asked for it.
                await manager.broadcast_except_uid(user.uid, frame)
            except Exception:
                logger.warning("[cottage-canvas] relay failed (non-fatal)", exc_info=True)
    finally:
        await stop_session_watchdog(session_watchdog)
        went_offline = await manager.disconnect(user.uid, ws)
        if went_offline:
            await manager.broadcast({"type": "PRESENCE", "payload": {"uid": user.uid, "online": False}})
