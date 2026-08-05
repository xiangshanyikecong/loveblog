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

"""WebSocket endpoint for cottage 你画我猜 (draw & guess).

Single endpoint ``WS /v1/cottage/draw/ws``. The drawer's brush strokes are
*relayed* to the guesser in real time (never stored); the authoritative game
state (turn, secret word, scores, round) lives in Redis via
:mod:`app.services.cottage_games.draw`.

Client → server intents:

- ``NEW_GAME``      — start a fresh session (rounds / duration optional)
- ``STROKE`` / ``CLEAR`` — relayed to the partner verbatim (drawer only)
- ``GUESS``         — submit a guess (guesser only)
- ``ROUND_TIMEOUT`` — end the round when the timer elapsed (server-validated)
- ``NEXT_ROUND``    — advance after a round ends
- ``END_GAME``      — abort early
- ``EMOTE``         — couple emote relay

The secret word is delivered privately to the drawer via a ``YOUR_WORD`` frame;
broadcast ``STATE`` frames never contain it until the round is over.
Auth / presence / error-isolation mirror ``cottage_games_ws``.
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
    _other_partner_uid,
    _resolve_user,
    _PARTNER_ROLES,
)
from app.api.v1.ws_security import (
    close_when_session_revoked,
    stop_session_watchdog,
    websocket_origin_allowed,
)
from app.db.redis import get_redis
from app.db.session import SessionLocal
from app.models.game_match import GameMatch
from app.models.user import User
from app.services.cottage_games import draw
from app.services.cottage_games.common import IllegalMove
from app.services.notifications import notify_partners

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cottage/draw", tags=["cottage-draw-ws"])

manager = ConnectionManager()

_ALLOWED_EMOTES = {"❤️", "😘", "😝", "👍", "🤝", "😭", "🎉", "🤔", "🖌️", "🎨"}


def _now_ms() -> int:
    return int(time.time() * 1000)


async def _push_word_to_drawer(snapshot: dict[str, Any], redis_client) -> None:
    """Privately hand the current secret word to whoever is drawing now."""
    if snapshot.get("phase") != draw.PHASE_DRAWING:
        return
    drawer_uid = snapshot.get("drawer_uid")
    if not drawer_uid:
        return
    word = draw.draw_room.current_word(redis_client)
    if word:
        await manager.send_to_uid(drawer_uid, {"type": "YOUR_WORD", "payload": {"word": word}})


def _persist_finished_match(data: dict[str, Any]) -> None:
    """Write a GameMatch (game_key="draw") for a finished session. Best-effort."""
    try:
        if not data or data.get("phase") != draw.PHASE_FINISHED:
            return
        a_uid = data.get("a_uid")
        b_uid = data.get("b_uid")
        if not a_uid or not b_uid:
            return

        redis_client = get_redis()
        dedup_key = f"cottage_draw:match_persisted:{data.get('started_by')}:{data.get('ended_at_ms')}"
        try:
            if not redis_client.set(dedup_key, "1", nx=True, ex=7 * 86400):
                return
        except Exception:
            logger.warning("[cottage-draw] match dedup redis unavailable (continuing)", exc_info=True)

        db = SessionLocal()
        try:
            users = db.query(User).filter(User.uid.in_([a_uid, b_uid]), User.deleted_at.is_(None)).all()
            by_uid = {u.uid: u for u in users}
            a_user = by_uid.get(a_uid)
            b_user = by_uid.get(b_uid)
            if a_user is None or b_user is None:
                return

            scores = data.get("scores") or {}
            winner_uid = data.get("winner_uid")
            is_draw = winner_uid is None
            winner_user = None if is_draw else by_uid.get(winner_uid)
            match = GameMatch(
                game_key=draw.GAME_KEY,
                black_id=a_user.id,
                white_id=b_user.id,
                winner_id=winner_user.id if winner_user else None,
                is_draw=is_draw,
                end_reason="score",
                move_count=int(scores.get(a_uid, 0)) + int(scores.get(b_uid, 0)),
            )
            db.add(match)
            db.flush()
            if winner_user is not None:
                notify_partners(
                    db,
                    type="game.result",
                    title=f"{winner_user.nickname} 赢了一局你画我猜",
                    body="再来一局扳回来？进入小屋的「你画我猜」吧",
                    link="/cottage/games/draw",
                    source_type="game",
                    source_id=match.gmid,
                    exclude_user_id=winner_user.id,
                )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.warning("[cottage-draw] failed to persist finished match (non-fatal)")


@router.websocket("/ws")
async def cottage_draw_ws(ws: WebSocket) -> None:
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
    redis_client = get_redis()

    try:
        await ws.send_json({"type": "PRESENCE_SNAPSHOT", "payload": {"online": manager.online_uids()}})
        snapshot = draw.draw_room.get_snapshot(redis_client)
        await ws.send_json({"type": "STATE", "payload": snapshot})
        # If this socket belongs to the active drawer, re-hand them the word.
        if snapshot.get("phase") == draw.PHASE_DRAWING and snapshot.get("drawer_uid") == user.uid:
            word = draw.draw_room.current_word(redis_client)
            if word:
                await ws.send_json({"type": "YOUR_WORD", "payload": {"word": word}})
    except draw.DrawRoomUnavailable:
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

            # Late-joiner board handshake: a guesser sends SYNC_REQUEST and the
            # drawer answers with SYNC (the current strokes). Relayed verbatim;
            # carries no game state, so either partner may send it.
            if mtype in ("SYNC_REQUEST", "SYNC"):
                await manager.broadcast_except_uid(
                    user.uid,
                    {
                        "type": mtype,
                        "payload": payload if isinstance(payload, (dict, list)) else {},
                        "from_uid": user.uid,
                        "server_ts_ms": _now_ms(),
                    },
                )
                continue

            # High-frequency drawing frames: relay to the partner only. Only the
            # current drawer is allowed to paint / erase / undo.
            if mtype in ("STROKE", "CLEAR", "UNDO"):
                try:
                    snap = draw.draw_room.get_snapshot(redis_client)
                except Exception:
                    continue
                if snap.get("phase") == draw.PHASE_DRAWING and snap.get("drawer_uid") == user.uid:
                    await manager.broadcast_except_uid(
                        user.uid,
                        {
                            "type": mtype,
                            "payload": payload if isinstance(payload, (dict, list)) else {},
                            "from_uid": user.uid,
                            "server_ts_ms": _now_ms(),
                        },
                    )
                continue

            try:
                if mtype == "NEW_GAME":
                    other = _other_partner_uid(user.uid)
                    if not other:
                        await ws.send_json({"type": "ERROR", "payload": {"message": "需要两位伴侣账号才能开始游戏"}})
                        continue
                    snapshot = draw.draw_room.new_game(
                        redis_client,
                        requester_uid=user.uid,
                        partner_uid=other,
                        total_rounds=payload.get("total_rounds", draw.DEFAULT_TOTAL_ROUNDS),
                        round_duration_sec=payload.get("round_duration_sec", draw.DEFAULT_ROUND_DURATION_SEC),
                    )
                    await manager.broadcast({"type": "STATE", "payload": snapshot})
                    await _push_word_to_drawer(snapshot, redis_client)

                elif mtype == "GUESS":
                    snapshot, correct = draw.draw_room.record_guess(
                        redis_client, uid=user.uid, text=str(payload.get("text", ""))
                    )
                    await manager.broadcast({"type": "STATE", "payload": snapshot})
                    await manager.broadcast(
                        {
                            "type": "GUESS",
                            "payload": {
                                "from_uid": user.uid,
                                "from_nickname": user.nickname,
                                "text": str(payload.get("text", ""))[:50],
                                "correct": correct,
                            },
                            "server_ts_ms": _now_ms(),
                        }
                    )
                    if snapshot.get("phase") == draw.PHASE_ROUND_END:
                        await manager.broadcast({"type": "ROUND_END", "payload": snapshot})

                elif mtype == "ROUND_TIMEOUT":
                    snapshot = draw.draw_room.timeout_round(redis_client, uid=user.uid)
                    await manager.broadcast({"type": "STATE", "payload": snapshot})
                    if snapshot.get("phase") == draw.PHASE_ROUND_END:
                        await manager.broadcast({"type": "ROUND_END", "payload": snapshot})

                elif mtype == "NEXT_ROUND":
                    snapshot = draw.draw_room.next_round(redis_client, uid=user.uid)
                    await manager.broadcast({"type": "STATE", "payload": snapshot})
                    if snapshot.get("phase") == draw.PHASE_FINISHED:
                        _persist_finished_match(draw.draw_room.load(redis_client))
                        await manager.broadcast({"type": "GAME_OVER", "payload": snapshot})
                    else:
                        await _push_word_to_drawer(snapshot, redis_client)

                elif mtype == "END_GAME":
                    snapshot = draw.draw_room.end_game(redis_client, uid=user.uid)
                    await manager.broadcast({"type": "STATE", "payload": snapshot})
                    _persist_finished_match(draw.draw_room.load(redis_client))
                    await manager.broadcast({"type": "GAME_OVER", "payload": snapshot})

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
                # Unknown types ignored.
            except IllegalMove as exc:
                try:
                    await ws.send_json({"type": "ERROR", "payload": {"message": str(exc)}})
                except Exception:
                    break
            except draw.DrawRoomUnavailable:
                try:
                    await ws.send_json({"type": "ERROR", "payload": {"message": "游戏服务暂不可用"}})
                except Exception:
                    break
            except Exception:
                logger.warning("[cottage-draw] handler error (non-fatal)", exc_info=True)
                try:
                    await ws.send_json({"type": "ERROR", "payload": {"message": "操作失败，请重试"}})
                except Exception:
                    break
    finally:
        await stop_session_watchdog(session_watchdog)
        went_offline = await manager.disconnect(user.uid, ws)
        if went_offline:
            await manager.broadcast({"type": "PRESENCE", "payload": {"uid": user.uid, "online": False}})
