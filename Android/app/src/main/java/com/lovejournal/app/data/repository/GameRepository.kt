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

package com.lovejournal.app.data.repository

import com.lovejournal.app.data.remote.CottageWebSocket
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.GameMatchListResponse
import com.lovejournal.app.data.remote.dto.GameStateResponse
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.OkHttpClient
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

sealed interface GameWsEvent {
    data class State(val state: GameStateResponse) : GameWsEvent
    data class Error(val message: String) : GameWsEvent
    data class Emote(val fromNickname: String, val emote: String) : GameWsEvent
    data class UndoResult(val accepted: Boolean) : GameWsEvent
    data class Connection(val connected: Boolean) : GameWsEvent
}

/**
 * 小屋·一起玩. The server owns all rules; this repo only relays MOVE / NEW_GAME /
 * … intents and surfaces the STATE snapshots it broadcasts back. One socket per
 * game key (the key is part of the WS path).
 */
@Singleton
class GameRepository @Inject constructor(
    private val api: LoveApiService,
    @Named("ws") private val wsClient: OkHttpClient,
    private val serverConfig: ServerConfig,
    private val json: Json,
) {
    private val _events = MutableSharedFlow<GameWsEvent>(extraBufferCapacity = 32)
    val events: SharedFlow<GameWsEvent> = _events

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var socket: CottageWebSocket? = null
    private val jobs = mutableListOf<Job>()

    fun connect(gameKey: String) {
        disconnect()
        val s = CottageWebSocket(wsClient, serverConfig, json, "/cottage/games/$gameKey/ws")
        socket = s
        jobs += scope.launch { s.events.collect { obj -> parseEvent(obj)?.let { _events.emit(it) } } }
        jobs += scope.launch { s.connected.collect { _events.emit(GameWsEvent.Connection(it)) } }
        s.connect()
    }

    fun disconnect() {
        jobs.forEach { it.cancel() }
        jobs.clear()
        socket?.close()
        socket = null
    }

    fun move(x: Int, y: Int) = send("""{"type":"MOVE","payload":{"x":$x,"y":$y}}""")
    fun newGame(size: Int) = send("""{"type":"NEW_GAME","payload":{"size":$size}}""")
    fun surrender() = send("""{"type":"SURRENDER"}""")
    fun requestUndo() = send("""{"type":"UNDO_REQUEST"}""")
    fun respondUndo(accept: Boolean) = send("""{"type":"UNDO_RESPOND","payload":{"accept":$accept}}""")

    private fun send(message: String) {
        socket?.send(message)
    }

    suspend fun matches(gameKey: String, limit: Int = 20): Result<GameMatchListResponse> =
        runCatching { api.gameMatches(gameKey, limit) }

    suspend fun invite(gameKey: String): Result<Unit> = runCatching {
        api.inviteGame(gameKey)
        Unit
    }

    private fun parseEvent(obj: JsonObject): GameWsEvent? {
        val type = obj["type"]?.jsonPrimitive?.contentOrNull ?: return null
        return when (type) {
            "STATE", "GAME_OVER" -> obj["payload"]
                ?.let { runCatching { json.decodeFromJsonElement<GameStateResponse>(it) }.getOrNull() }
                ?.let { GameWsEvent.State(it) }
            "ERROR" -> GameWsEvent.Error(
                obj["payload"]?.jsonObject?.get("message")?.jsonPrimitive?.contentOrNull ?: "操作失败",
            )
            "EMOTE" -> {
                val p = obj["payload"]?.jsonObject
                GameWsEvent.Emote(
                    fromNickname = p?.get("from_nickname")?.jsonPrimitive?.contentOrNull ?: "TA",
                    emote = p?.get("emote")?.jsonPrimitive?.contentOrNull ?: "",
                )
            }
            "UNDO_RESULT" -> GameWsEvent.UndoResult(
                obj["payload"]?.jsonObject?.get("accepted")?.jsonPrimitive?.contentOrNull == "true",
            )
            else -> null
        }
    }
}
