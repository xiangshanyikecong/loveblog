/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

package com.lovejournal.app.data.remote.dto

import kotlinx.serialization.Serializable

// ---------------------------------------------------------------------------
// 小屋·一起玩 (cottage games) — REST: /v1/cottage/games/{game}/*,
// WS: /v1/cottage/games/{game}/ws. The server is authoritative: it validates
// every MOVE and broadcasts the full STATE snapshot (this class) back.
// ---------------------------------------------------------------------------

@Serializable
data class GamePlayer(
    val uid: String = "",
    val nickname: String = "",
    val color: String? = null, // "black" | "white" | null
    val online: Boolean = false,
)

@Serializable
data class GameLastMove(
    val x: Int = 0,
    val y: Int = 0,
    val color: Int = 0,
)

@Serializable
data class GameStateResponse(
    val game_key: String = "",
    val phase: String = "waiting", // "waiting" | "playing" | "finished"
    val size: Int = 15,
    val cells: List<Int> = emptyList(), // size*size, 0 empty / 1 black / 2 white
    val turn: String? = null, // "black" | "white"
    val turn_uid: String? = null,
    val winner: String? = null, // "black" | "white" | "draw" | null
    val win_line: List<List<Int>> = emptyList(),
    val legal_moves: List<List<Int>> = emptyList(), // reversi placements [[x,y],...]
    val last_move: GameLastMove? = null,
    val move_count: Int = 0,
    val black_uid: String? = null,
    val white_uid: String? = null,
    val started_by: String? = null,
    val end_reason: String? = null,
    val undo_request_by: String? = null,
    val seq: Int = 0,
    val server_ts_ms: Long = 0,
    val players: List<GamePlayer> = emptyList(),
    // memory / linklink only (unused by the grid renderer)
    val cols: Int? = null,
    val rows: Int? = null,
    val tiles: List<Int>? = null,
    val states: List<Int>? = null,
    val icons: List<String>? = null,
    val black_score: Int = 0,
    val white_score: Int = 0,
    val pending: List<Int>? = null,
)

@Serializable
data class GameMatchResponse(
    val gmid: String = "",
    val game_key: String = "",
    val black_uid: String = "",
    val black_nickname: String = "",
    val white_uid: String = "",
    val white_nickname: String = "",
    val winner_uid: String? = null,
    val is_draw: Boolean = false,
    val end_reason: String = "",
    val move_count: Int = 0,
    val created_at: String = "",
)

@Serializable
data class GamePlayerStat(
    val uid: String = "",
    val nickname: String = "",
    val wins: Int = 0,
)

@Serializable
data class GameMatchListResponse(
    val items: List<GameMatchResponse> = emptyList(),
    val total: Int = 0,
    val draws: Int = 0,
    val stats: List<GamePlayerStat> = emptyList(),
)
