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
import com.lovejournal.app.data.remote.dto.WatchBookmark
import com.lovejournal.app.data.remote.dto.WatchSourceCreateRequest
import com.lovejournal.app.data.remote.dto.WatchSourceListResponse
import com.lovejournal.app.data.remote.dto.WatchSourcePatchRequest
import com.lovejournal.app.data.remote.dto.WatchSourceResponse
import com.lovejournal.app.data.remote.dto.WatchStateResponse
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

sealed interface WatchWsEvent {
    /** Something about the shared playback changed; re-fetch /state to apply. */
    data class Sync(val originUid: String?) : WatchWsEvent
    data class Presence(val uid: String, val online: Boolean) : WatchWsEvent
    data class Connection(val connected: Boolean) : WatchWsEvent
}

/**
 * 小屋·一起看. The shared playback head lives server-side (Redis). On any remote
 * control event we re-read GET /state (which synthesizes the live position +
 * server_ts_ms) and apply it to the local player — robust against guessing
 * per-event field math.
 */
@Singleton
class WatchRepository @Inject constructor(
    private val api: LoveApiService,
    @Named("ws") wsClient: OkHttpClient,
    serverConfig: ServerConfig,
    private val json: Json,
) {
    private val socket = CottageWebSocket(wsClient, serverConfig, json, "/cottage/watch/ws")

    private val _events = MutableSharedFlow<WatchWsEvent>(extraBufferCapacity = 32)
    val events: SharedFlow<WatchWsEvent> = _events

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val jobs = mutableListOf<Job>()

    fun connect() {
        disconnect()
        jobs += scope.launch { socket.events.collect { obj -> parse(obj)?.let { _events.emit(it) } } }
        jobs += scope.launch { socket.connected.collect { _events.emit(WatchWsEvent.Connection(it)) } }
        socket.connect()
    }

    fun disconnect() {
        jobs.forEach { it.cancel() }
        jobs.clear()
        socket.close()
    }

    fun load(wsid: String, url: String, title: String, kind: String) = sendFrame("LOAD") {
        put("source_wsid", wsid)
        put("source_url", url)
        put("source_title", title)
        put("source_kind", kind)
        put("position_ms", 0)
    }

    fun play(positionMs: Long) = sendFrame("PLAY") { put("position_ms", positionMs) }
    fun pause(positionMs: Long) = sendFrame("PAUSE") { put("position_ms", positionMs) }
    fun seek(positionMs: Long) = sendFrame("SEEK") { put("position_ms", positionMs) }
    fun rate(rate: Float, positionMs: Long) = sendFrame("RATE") {
        put("rate", rate)
        put("position_ms", positionMs)
    }

    private inline fun sendFrame(type: String, payload: kotlinx.serialization.json.JsonObjectBuilder.() -> Unit) {
        val frame = buildJsonObject {
            put("type", type)
            put("payload", buildJsonObject(payload))
        }
        socket.send(json.encodeToString(JsonObject.serializer(), frame))
    }

    suspend fun state(): Result<WatchStateResponse> = runCatching { api.watchState() }
    suspend fun sources(): Result<WatchSourceListResponse> = runCatching { api.watchSources() }
    suspend fun addSource(title: String, url: String, poster: String?): Result<Unit> = runCatching {
        api.addWatchSource(WatchSourceCreateRequest(title = title, url = url, poster_url = poster))
        Unit
    }
    suspend fun uploadSource(file: MultipartBody.Part): Result<Unit> = runCatching {
        api.uploadWatchSource(file)
        Unit
    }
    /**
     * Partial update: resume position and/or bookmarks. Either field may be
     * null to leave the corresponding server-side value untouched; bookmarks
     * (when present) REPLACE the server list in full — the caller is
     * responsible for read-modify-write.
     */
    suspend fun patchSource(
        wsid: String,
        lastPositionMs: Long? = null,
        bookmarks: List<WatchBookmark>? = null,
    ): Result<WatchSourceResponse> = runCatching {
        api.patchWatchSource(wsid, WatchSourcePatchRequest(lastPositionMs, bookmarks))
    }
    suspend fun deleteSource(wsid: String): Result<Unit> = runCatching {
        val resp = api.deleteWatchSource(wsid)
        if (!resp.isSuccessful) throw IllegalStateException("删除失败 (${resp.code()})")
        Unit
    }
    suspend fun invite(): Result<Unit> = runCatching {
        api.inviteWatch()
        Unit
    }

    private fun parse(obj: JsonObject): WatchWsEvent? {
        val type = obj["type"]?.jsonPrimitive?.contentOrNull ?: return null
        return when (type) {
            "LOAD", "PLAY", "PAUSE", "SEEK", "RATE", "ROOM_CLEARED" ->
                WatchWsEvent.Sync(obj["origin_uid"]?.jsonPrimitive?.contentOrNull)
            "PRESENCE" -> {
                val p = obj["payload"]?.jsonObject ?: return null
                WatchWsEvent.Presence(
                    uid = p["user_uid"]?.jsonPrimitive?.contentOrNull ?: return null,
                    online = p["online"]?.jsonPrimitive?.booleanOrNull ?: false,
                )
            }
            else -> null
        }
    }
}
