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

"""WebSocket endpoint for cottage 一起玩 real-time play.

Single endpoint ``WS /v1/cottage/games/{game_key}/ws``. Supported games:
``gomoku``, ``tictactoe``, ``reversi``, ``memory``, ``linklink``. The socket is
the single source of gameplay truth: clients send ``MOVE`` / ``NEW_GAME`` /
``SURRENDER`` intents, the server validates them against the authoritative
Redis room state and broadcasts the full ``STATE`` snapshot back to both
partners. Illegal intents get a private ``ERROR`` frame and never mutate
anything.

Each game key has its own isolated room (Redis namespace) and its own presence
manager, so two different games can be in progress at once without interfering.

Isolation: a failure in any handler is caught and turned into an ``ERROR`` frame
for the offending socket — it cannot break the receive loop, the other socket,
or any other feature. Auth mirrors ``cottage_watch_ws`` (cookie or Bearer,
never query string).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.core.config import settings
from app.db.redis import get_redis
from app.db.session import SessionLocal
from app.models.game_match import GameMatch
from app.models.user import User, UserRole
from app.services.cottage_games import room
from app.services.cottage_games.common import IllegalMove
from app.services.notifications import notify_partners
from app.services.security import check_session_version
from app.api.v1.ws_security import (
    close_when_session_revoked,
    stop_session_watchdog,
    websocket_origin_allowed,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cottage/games", tags=["cottage-games-ws"])

WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403
WS_CLOSE_NOT_FOUND = 4404

_PARTNER_ROLES = {UserRole.partner_a, UserRole.partner_b}


def _now_ms() -> int:
    return int(time.time() * 1000)


class ConnectionManager:
    """Tracks game-room sockets in this backend process (at most two partners,
    each possibly with several tabs). Presence is derived from live sockets."""

    def __init__(self) -> None:
        self._conns: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, uid: str, ws: WebSocket) -> bool:
        async with self._lock:
            conns = self._conns.setdefault(uid, [])
            became_online = len(conns) == 0
            conns.append(ws)
            return became_online

    async def disconnect(self, uid: str, ws: WebSocket) -> bool:
        async with self._lock:
            conns = self._conns.get(uid)
            if conns and ws in conns:
                conns.remove(ws)
            went_offline = not self._conns.get(uid)
            if conns is not None and not conns:
                self._conns.pop(uid, None)
            return went_offline

    def is_online(self, uid: str) -> bool:
        return bool(self._conns.get(uid))

    def online_uids(self) -> list[str]:
        return [uid for uid, conns in self._conns.items() if conns]

    async def _snapshot(self) -> list[tuple[str, WebSocket]]:
        async with self._lock:
            return [(uid, ws) for uid, conns in self._conns.items() for ws in conns]

    async def broadcast(self, event: dict[str, Any]) -> None:
        dead: list[tuple[str, WebSocket]] = []
        for uid, ws in await self._snapshot():
            try:
                await ws.send_json(event)
            except Exception:
                dead.append((uid, ws))
        for uid, ws in dead:
            await self.disconnect(uid, ws)

    async def send_to_uid(self, uid: str, event: dict[str, Any]) -> None:
        """Send to every socket owned by ``uid`` (all of that partner's tabs).

        Used to hand the drawer their secret word out-of-band so it never rides
        on a broadcast STATE frame the guesser also receives.
        """
        dead: list[tuple[str, WebSocket]] = []
        for owner, ws in await self._snapshot():
            if owner != uid:
                continue
            try:
                await ws.send_json(event)
            except Exception:
                dead.append((owner, ws))
        for owner, ws in dead:
            await self.disconnect(owner, ws)

    async def broadcast_except_uid(self, exclude_uid: str, event: dict[str, Any]) -> None:
        """Send to every socket whose owner is not ``exclude_uid``.

        Used for high-frequency relay frames (drawing strokes / cursor) so the
        sender doesn't get its own paint echoed back, while the partner — and
        the sender's own *other* tabs — stay in sync.
        """
        dead: list[tuple[str, WebSocket]] = []
        for uid, ws in await self._snapshot():
            if uid == exclude_uid:
                continue
            try:
                await ws.send_json(event)
            except Exception:
                dead.append((uid, ws))
        for uid, ws in dead:
            await self.disconnect(uid, ws)


# One presence manager per game key, created lazily.
_managers: dict[str, ConnectionManager] = {}


def get_manager(game_key: str) -> ConnectionManager:
    mgr = _managers.get(game_key)
    if mgr is None:
        mgr = ConnectionManager()
        _managers[game_key] = mgr
    return mgr


# Back-compat alias: the original gomoku-only manager.
manager = get_manager("gomoku")


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


def _other_partner_uid(self_uid: str) -> str | None:
    db = SessionLocal()
    try:
        partners = (
            db.query(User)
            .filter(
                User.role.in_(list(_PARTNER_ROLES)),
                User.deleted_at.is_(None),
            )
            .order_by(User.id.asc())
            .all()
        )
        for p in partners:
            if p.uid != self_uid:
                return p.uid
        return None
    finally:
        db.close()


def _persist_finished_match(snapshot: dict[str, Any]) -> None:
    """Write a GameMatch row and notify the partner. Best-effort: any failure
    is logged and swallowed so it can never break the socket loop."""
    try:
        winner = snapshot.get("winner")  # "black" | "white" | "draw" | None
        if winner is None:
            return
        black_uid = snapshot.get("black_uid")
        white_uid = snapshot.get("white_uid")
        if not black_uid or not white_uid:
            return

        game_key = snapshot.get("game_key", "gomoku")
        room_seq = int(snapshot.get("seq") or 0)
        move_count = int(snapshot.get("move_count", 0))
        end_reason = snapshot.get("end_reason") or ("draw" if winner == "draw" else "five")

        redis_client = get_redis()
        dedup_key = f"cottage_game:{game_key}:match_persisted:{room_seq}"
        try:
            if room_seq > 0 and not redis_client.set(dedup_key, "1", nx=True, ex=7 * 86400):
                return
        except Exception:
            logger.warning("[cottage-games] match dedup redis unavailable (continuing)", exc_info=True)

        db = SessionLocal()
        try:
            users = (
                db.query(User)
                .filter(User.uid.in_([black_uid, white_uid]), User.deleted_at.is_(None))
                .all()
            )
            by_uid = {u.uid: u for u in users}
            black = by_uid.get(black_uid)
            white = by_uid.get(white_uid)
            if black is None or white is None:
                return

            is_draw = winner == "draw"
            existing = (
                db.query(GameMatch)
                .filter(
                    GameMatch.game_key == game_key,
                    GameMatch.black_id == black.id,
                    GameMatch.white_id == white.id,
                    GameMatch.move_count == move_count,
                    GameMatch.end_reason == end_reason,
                )
                .order_by(GameMatch.id.desc())
                .first()
            )
            if existing is not None:
                return

            winner_user = None if is_draw else (black if winner == "black" else white)
            game_name = _GAME_NAMES.get(game_key, "一局棋")
            match = GameMatch(
                game_key=game_key,
                black_id=black.id,
                white_id=white.id,
                winner_id=winner_user.id if winner_user else None,
                is_draw=is_draw,
                end_reason=end_reason,
                move_count=move_count,
            )
            db.add(match)
            db.flush()

            if winner_user is not None:
                notify_partners(
                    db,
                    type="game.result",
                    title=f"{winner_user.nickname} 赢了一局{game_name}",
                    body="再来一局扳回来？进入小屋的「一起玩」吧",
                    link=f"/cottage/games/{game_key}",
                    source_type="game",
                    source_id=match.gmid,
                    exclude_user_id=winner_user.id,
                )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.warning("[cottage-games] failed to persist finished match (non-fatal)")


_GAME_NAMES = {"gomoku": "五子棋", "tictactoe": "井字棋", "reversi": "黑白棋", "memory": "记忆翻牌", "linklink": "连连看"}

# Whitelisted in-game emotes (couple-flavored). Anything else is ignored so the
# socket can never be used to broadcast arbitrary payloads.
_ALLOWED_EMOTES = {"❤️", "😘", "😝", "👍", "🤝", "😭", "🎉", "🤔"}


@router.websocket("/{game_key}/ws")
async def cottage_games_ws(ws: WebSocket, game_key: str) -> None:
    if not websocket_origin_allowed(ws):
        await ws.close(code=WS_CLOSE_FORBIDDEN)
        return
    game_room = room.get_room(game_key)
    if game_room is None:
        await ws.close(code=WS_CLOSE_NOT_FOUND)
        return

    token = _extract_token(ws)
    user = _resolve_user(token) if token else None
    if user is None:
        await ws.close(code=WS_CLOSE_UNAUTHORIZED)
        return
    if user.role not in _PARTNER_ROLES:
        await ws.close(code=WS_CLOSE_FORBIDDEN)
        return

    manager = get_manager(game_key)
    engine = game_room.engine

    await ws.accept()
    became_online = await manager.connect(user.uid, ws)
    session_watchdog = asyncio.create_task(
        close_when_session_revoked(ws, token or "", _resolve_user)
    )
    redis_client = get_redis()

    # Initial presence + state snapshot for this socket.
    try:
        await ws.send_json({"type": "PRESENCE_SNAPSHOT", "payload": {"online": manager.online_uids()}})
        await ws.send_json({"type": "STATE", "payload": game_room.get_snapshot(redis_client)})
    except room.RoomUnavailable:
        try:
            await ws.send_json({"type": "ERROR", "payload": {"message": "游戏服务暂不可用"}})
        except Exception:
            pass
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
            payload = msg.get("payload") or {}

            if mtype == "PING":
                try:
                    await ws.send_json({"type": "PONG"})
                except Exception:
                    break
                continue

            try:
                if mtype == "NEW_GAME":
                    other = _other_partner_uid(user.uid)
                    if not other:
                        await ws.send_json(
                            {"type": "ERROR", "payload": {"message": "需要两位伴侣账号才能开始对局"}}
                        )
                        continue
                    size = engine.normalize_size(payload.get("size", engine.DEFAULT_SIZE))
                    snapshot = game_room.new_game(
                        redis_client,
                        requester_uid=user.uid,
                        partner_uid=other,
                        size=size,
                    )
                    await manager.broadcast({"type": "STATE", "payload": snapshot})

                elif mtype == "MOVE":
                    snapshot = game_room.apply_move(
                        redis_client, uid=user.uid, x=payload.get("x"), y=payload.get("y")
                    )
                    await manager.broadcast({"type": "STATE", "payload": snapshot})
                    if snapshot.get("phase") == room.PHASE_FINISHED:
                        _persist_finished_match(snapshot)
                        await manager.broadcast({"type": "GAME_OVER", "payload": snapshot})

                elif mtype == "SURRENDER":
                    snapshot = game_room.surrender(redis_client, uid=user.uid)
                    await manager.broadcast({"type": "STATE", "payload": snapshot})
                    _persist_finished_match(snapshot)
                    await manager.broadcast({"type": "GAME_OVER", "payload": snapshot})

                elif mtype == "UNDO_REQUEST":
                    snapshot = game_room.request_undo(redis_client, uid=user.uid)
                    await manager.broadcast({"type": "STATE", "payload": snapshot})

                elif mtype == "UNDO_RESPOND":
                    accept = bool(payload.get("accept"))
                    pre = game_room.get_snapshot(redis_client)
                    requester = pre.get("undo_request_by")
                    snapshot = game_room.respond_undo(
                        redis_client, uid=user.uid, accept=accept
                    )
                    await manager.broadcast({"type": "STATE", "payload": snapshot})
                    await manager.broadcast(
                        {
                            "type": "UNDO_RESULT",
                            "payload": {"accepted": accept, "requester": requester},
                        }
                    )

                elif mtype == "EMOTE":
                    emote = payload.get("emote")
                    if isinstance(emote, str) and emote in _ALLOWED_EMOTES:
                        await manager.broadcast(
                            {
                                "type": "EMOTE",
                                "payload": {
                                    "from_uid": user.uid,
                                    "from_nickname": user.nickname,
                                    "emote": emote,
                                },
                                "server_ts_ms": _now_ms(),
                            }
                        )

                # Unknown types are ignored.
            except IllegalMove as exc:
                try:
                    await ws.send_json({"type": "ERROR", "payload": {"message": str(exc)}})
                except Exception:
                    break
            except room.RoomUnavailable:
                try:
                    await ws.send_json({"type": "ERROR", "payload": {"message": "游戏服务暂不可用"}})
                except Exception:
                    break
            except Exception:
                logger.warning("[cottage-games] handler error (non-fatal)", exc_info=True)
                try:
                    await ws.send_json({"type": "ERROR", "payload": {"message": "操作失败，请重试"}})
                except Exception:
                    break
    finally:
        await stop_session_watchdog(session_watchdog)
        went_offline = await manager.disconnect(user.uid, ws)
        if went_offline:
            await manager.broadcast({"type": "PRESENCE", "payload": {"uid": user.uid, "online": False}})
