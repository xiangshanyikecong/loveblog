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

"""REST endpoints for cottage 你画我猜 (draw & guess).

Everything that isn't live drawing/guessing (which flows over the WebSocket):

- ``GET  /v1/cottage/draw/state``    — live room + partner presence
- ``GET  /v1/cottage/draw/matches``  — recent results + win stats (战绩)
- ``POST /v1/cottage/draw/invite``   — nudge the partner to come play

Partner-only; read-only except the (idempotent) invite. Mirrors
``cottage_games`` but for the non-board draw-and-guess game.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.api.v1.cottage_draw_ws import manager as draw_manager
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.game_match import GameMatch
from app.models.user import User, UserRole
from app.schemas.game import (
    GameMatchListResponse,
    GameMatchResponse,
    GamePlayer,
    GamePlayerStat,
)
from app.services import cottage_realtime
from app.services.cottage_games import draw
from app.services.notifications import notify_partners

router = APIRouter(prefix="/cottage/draw", tags=["cottage-draw"])

_PARTNER_ROLES = [UserRole.partner_a, UserRole.partner_b]
GAME_NAME = "你画我猜"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _partners(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role.in_(_PARTNER_ROLES), User.deleted_at.is_(None))
        .order_by(User.id.asc())
        .all()
    )


@router.get("/state")
def get_draw_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> dict[str, Any]:
    ensure_partner(current_user)
    try:
        snapshot = draw.draw_room.get_snapshot(redis_client)
    except draw.DrawRoomUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="游戏服务暂不可用"
        ) from exc
    players = [
        GamePlayer(
            uid=p.uid,
            nickname=p.nickname,
            color=None,
            online=draw_manager.is_online(p.uid),
        ).model_dump()
        for p in _partners(db)
    ]
    snapshot["players"] = players
    return snapshot


@router.get("/matches", response_model=GameMatchListResponse)
def list_draw_matches(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GameMatchListResponse:
    ensure_partner(current_user)
    limit = max(1, min(limit, 100))

    matches = (
        db.query(GameMatch)
        .options(
            joinedload(GameMatch.black),
            joinedload(GameMatch.white),
            joinedload(GameMatch.winner),
        )
        .filter(GameMatch.game_key == draw.GAME_KEY)
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

    draws = (
        db.query(GameMatch)
        .filter(GameMatch.game_key == draw.GAME_KEY, GameMatch.is_draw.is_(True))
        .count()
    )
    wins: dict[str, int] = {}
    won_rows = (
        db.query(GameMatch)
        .options(joinedload(GameMatch.winner))
        .filter(GameMatch.game_key == draw.GAME_KEY, GameMatch.winner_id.isnot(None))
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


@router.post("/invite", status_code=status.HTTP_204_NO_CONTENT)
async def invite_draw_partner(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_partner(current_user)
    notify_partners(
        db,
        type="game.invite",
        title=f"{current_user.nickname} 邀请你玩{GAME_NAME}",
        body="进入小屋的「你画我猜」陪 Ta 来一局吧",
        link="/cottage/games/draw",
        source_type="game",
        source_id=current_user.uid,
        exclude_user_id=current_user.id,
    )
    db.commit()
    cottage_realtime.schedule_broadcast(
        {
            "type": "INVITE",
            "payload": {
                "from_uid": current_user.uid,
                "from_nickname": current_user.nickname,
                "kind": "game",
                "game_key": draw.GAME_KEY,
                "title": f"玩{GAME_NAME}",
                "link": "/cottage/games/draw",
            },
            "server_ts_ms": _now_ms(),
        },
        exclude_uid=current_user.uid,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
