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

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GamePlayer(BaseModel):
    """One partner's seat / presence info for a game room."""

    uid: str
    nickname: str
    color: str | None = None  # "black" | "white" | None (not seated this match)
    online: bool = False


class GameLastMove(BaseModel):
    x: int
    y: int
    color: int


class GameStateResponse(BaseModel):
    """Live room snapshot returned by GET /state (mirrors the WS STATE frame)."""

    game_key: str
    phase: str  # "waiting" | "playing" | "finished"
    size: int
    cells: list[int]
    turn: str | None = None  # "black" | "white" | None
    turn_uid: str | None = None
    winner: str | None = None  # "black" | "white" | "draw" | None
    win_line: list[list[int]] = []
    legal_moves: list[list[int]] = []  # placements the player-to-move may pick (reversi)
    last_move: GameLastMove | None = None
    move_count: int = 0
    black_uid: str | None = None
    white_uid: str | None = None
    started_by: str | None = None
    end_reason: str | None = None
    undo_request_by: str | None = None  # uid of a pending 悔棋 requester, if any
    seq: int = 0
    server_ts_ms: int = 0
    players: list[GamePlayer] = []
    cols: int | None = None
    rows: int | None = None
    tiles: list[int] | None = None
    states: list[int] | None = None
    icons: list[str] | None = None
    black_score: int = 0
    white_score: int = 0
    pending: list[int] | None = None


class GameMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gmid: str
    game_key: str
    black_uid: str
    black_nickname: str
    white_uid: str
    white_nickname: str
    winner_uid: str | None
    is_draw: bool
    end_reason: str
    move_count: int
    created_at: datetime


class GamePlayerStat(BaseModel):
    uid: str
    nickname: str
    wins: int = 0


class GameMatchListResponse(BaseModel):
    items: list[GameMatchResponse]
    total: int
    draws: int = 0
    stats: list[GamePlayerStat] = []
