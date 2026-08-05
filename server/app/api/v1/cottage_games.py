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

"""REST endpoints for cottage 一起玩 (五子棋 / 井字棋 / 黑白棋 / 记忆翻牌 / 连连看…).

Everything that isn't live gameplay (gameplay flows over the WebSocket):

- ``GET  /v1/cottage/games/{game}/state``    — live room + partner presence
- ``GET  /v1/cottage/games/{game}/matches``  — recent results + win stats (战绩)
- ``POST /v1/cottage/games/{game}/invite``   — nudge the partner to come play

``{game}`` is one of ``gomoku`` | ``tictactoe`` | ``reversi`` | ``memory`` |
``linklink``. All endpoints are partner-only and read-only except the
(idempotent) invite.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.api.v1.cottage_games_ws import get_manager
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.game_match import GameMatch
from app.models.user import User, UserRole
from app.schemas.game import (
    GameMatchListResponse,
    GameMatchResponse,
    GamePlayer,
    GamePlayerStat,
    GameStateResponse,
)
from app.services import cottage_realtime
from app.services.cottage_games import room
from app.services.notifications import notify_partners

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cottage/games", tags=["cottage-games"])

_PARTNER_ROLES = [UserRole.partner_a, UserRole.partner_b]

GAME_NAMES = {"gomoku": "五子棋", "tictactoe": "井字棋", "reversi": "黑白棋", "memory": "记忆翻牌", "linklink": "连连看"}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _require_game(game_key: str):
    game_room = room.get_room(game_key)
    if game_room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未知的游戏")
    return game_room


def _partners(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role.in_(_PARTNER_ROLES), User.deleted_at.is_(None))
        .order_by(User.id.asc())
        .all()
    )


def _build_players(db: Session, game_key: str, snapshot: dict[str, Any]) -> list[GamePlayer]:
    black_uid = snapshot.get("black_uid")
    white_uid = snapshot.get("white_uid")
    ws_manager = get_manager(game_key)
    players: list[GamePlayer] = []
    for p in _partners(db):
        color = None
        if p.uid == black_uid:
            color = "black"
        elif p.uid == white_uid:
            color = "white"
        players.append(
            GamePlayer(
                uid=p.uid,
                nickname=p.nickname,
                color=color,
                online=ws_manager.is_online(p.uid),
            )
        )
    return players


@router.get("/{game_key}/state", response_model=GameStateResponse)
def get_game_state(
    game_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> GameStateResponse:
    ensure_partner(current_user)
    game_room = _require_game(game_key)
    try:
        snapshot = game_room.get_snapshot(redis_client)
    except room.RoomUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="游戏服务暂不可用"
        ) from exc
    snapshot["players"] = _build_players(db, game_key, snapshot)
    return GameStateResponse(**snapshot)


@router.get("/{game_key}/matches", response_model=GameMatchListResponse)
def list_game_matches(
    game_key: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GameMatchListResponse:
    ensure_partner(current_user)
    _require_game(game_key)
    limit = max(1, min(limit, 100))

    matches = (
        db.query(GameMatch)
        .options(
            joinedload(GameMatch.black),
            joinedload(GameMatch.white),
            joinedload(GameMatch.winner),
        )
        .filter(GameMatch.game_key == game_key)
        .order_by(GameMatch.created_at.desc())
        .limit(limit)
        .all()
    )

    items = [
        GameMatchResponse(
            gmid=m.gmid,
            game_key=m.game_key,
            black_uid=m.black.uid if m.black else "",
            black_nickname=m.black.nickname if m.black else "",
            white_uid=m.white.uid if m.white else "",
            white_nickname=m.white.nickname if m.white else "",
            winner_uid=m.winner.uid if m.winner else None,
            is_draw=m.is_draw,
            end_reason=m.end_reason,
            move_count=m.move_count,
            created_at=m.created_at,
        )
        for m in matches
    ]

    # Lifetime win stats per partner (cheap aggregate over a small table).
    wins: dict[str, int] = {}
    draws = (
        db.query(GameMatch)
        .filter(GameMatch.game_key == game_key, GameMatch.is_draw.is_(True))
        .count()
    )
    won_rows = (
        db.query(GameMatch)
        .options(joinedload(GameMatch.winner))
        .filter(GameMatch.game_key == game_key, GameMatch.winner_id.isnot(None))
        .all()
    )
    for row in won_rows:
        if row.winner:
            wins[row.winner.uid] = wins.get(row.winner.uid, 0) + 1

    stats = [
        GamePlayerStat(uid=p.uid, nickname=p.nickname, wins=wins.get(p.uid, 0))
        for p in _partners(db)
    ]

    return GameMatchListResponse(items=items, total=len(items), draws=draws, stats=stats)


@router.post("/{game_key}/invite", status_code=status.HTTP_204_NO_CONTENT)
async def invite_game_partner(
    game_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_partner(current_user)
    _require_game(game_key)
    game_name = GAME_NAMES.get(game_key, "棋")
    notify_partners(
        db,
        type="game.invite",
        title=f"{current_user.nickname} 邀请你下{game_name}",
        body="进入小屋的「一起玩」陪 Ta 来一局吧",
        link=f"/cottage/games/{game_key}",
        source_type="game",
        source_id=current_user.uid,
        exclude_user_id=current_user.id,
    )
    db.commit()
    # Push the invite over the shared cottage realtime channel so the partner
    # sees it no matter which cottage page they're on — not only if they happen
    # to be sitting on this game's own socket. The persisted notification above
    # is the reliable fallback when they're offline / out of the cottage.
    cottage_realtime.schedule_broadcast(
        {
            "type": "INVITE",
            "payload": {
                "from_uid": current_user.uid,
                "from_nickname": current_user.nickname,
                "kind": "game",
                "game_key": game_key,
                "title": f"下{game_name}",
                "link": f"/cottage/games/{game_key}",
            },
            "server_ts_ms": _now_ms(),
        },
        exclude_uid=current_user.uid,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
