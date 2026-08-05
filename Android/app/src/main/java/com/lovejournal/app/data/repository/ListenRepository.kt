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
import com.lovejournal.app.data.remote.dto.ImportCookieRequest
import com.lovejournal.app.data.remote.dto.ListenHistoryResponse
import com.lovejournal.app.data.remote.dto.LocalTracksResponse
import com.lovejournal.app.data.remote.dto.PlaylistTracksResponse
import com.lovejournal.app.data.remote.dto.PlaylistsResponse
import com.lovejournal.app.data.remote.dto.QrKeyResponse
import com.lovejournal.app.data.remote.dto.QrStatusResponse
import com.lovejournal.app.data.remote.dto.RoomStateResponse
import com.lovejournal.app.data.remote.dto.SongLyricResponse
import com.lovejournal.app.data.remote.dto.SongMeta
import com.lovejournal.app.data.remote.dto.SongSearchResponse
import com.lovejournal.app.data.remote.dto.SongUrlResponse
import com.lovejournal.app.data.remote.dto.ToplistResponse
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonObjectBuilder
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody

sealed interface ListenWsEvent {
    data class RoomChanged(val type: String, val originUid: String?) : ListenWsEvent
    data object LoginChanged : ListenWsEvent
    data class Connection(val connected: Boolean) : ListenWsEvent
}

@Singleton
class ListenRepository @Inject constructor(
    private val api: LoveApiService,
    @Named("ws") wsClient: OkHttpClient,
    serverConfig: ServerConfig,
    private val json: Json,
) {
    private val socket = CottageWebSocket(wsClient, serverConfig, json, "/cottage/listen/ws")
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val jobs = mutableListOf<Job>()

    private val _events = MutableSharedFlow<ListenWsEvent>(extraBufferCapacity = 32)
    val events: SharedFlow<ListenWsEvent> = _events

    fun connect() {
        disconnect()
        jobs += scope.launch { socket.events.collect { obj -> parse(obj)?.let { _events.emit(it) } } }
        jobs += scope.launch { socket.connected.collect { _events.emit(ListenWsEvent.Connection(it)) } }
        socket.connect()
    }

    fun disconnect() {
        jobs.forEach { it.cancel() }
        jobs.clear()
        socket.close()
    }

    fun play(song: SongMeta, positionMs: Long = 0L) = sendFrame("PLAY") {
        put("song_id", song.songId)
        put("song_meta", json.encodeToJsonElement(SongMeta.serializer(), song))
        put("position_ms", positionMs)
    }

    fun pause(positionMs: Long) = sendFrame("PAUSE") { put("position_ms", positionMs) }

    fun seek(positionMs: Long) = sendFrame("SEEK") { put("position_ms", positionMs) }

    fun next(expectedSongId: String? = null) = sendFrame("NEXT") {
        if (!expectedSongId.isNullOrBlank()) put("expected_song_id", expectedSongId)
    }

    fun prev() = sendFrame("PREV") {}

    fun queueAppend(song: SongMeta) = sendFrame("QUEUE_APPEND") {
        put("song_id", song.songId)
        put("song_meta", json.encodeToJsonElement(SongMeta.serializer(), song))
    }

    fun queueRemove(index: Int) = sendFrame("QUEUE_REMOVE") { put("index", index) }

    fun queueRemove(songId: String) = sendFrame("QUEUE_REMOVE") { put("song_id", songId) }

    fun queueClear() = sendFrame("QUEUE_CLEAR") {}

    fun heartbeat() = sendFrame("HEARTBEAT") {}

    fun ping() = sendFrame("PING") {}

    private inline fun sendFrame(type: String, payload: JsonObjectBuilder.() -> Unit) {
        val frame = buildJsonObject {
            put("type", type)
            put("payload", buildJsonObject(payload))
        }
        socket.send(json.encodeToString(JsonObject.serializer(), frame))
    }

    suspend fun state(): Result<RoomStateResponse> = runCatching { api.listenState() }

    suspend fun search(keyword: String, page: Int = 1, pageSize: Int = 20): Result<SongSearchResponse> =
        runCatching { api.listenSearch(keyword, page, pageSize) }

    suspend fun playlists(): Result<PlaylistsResponse> = runCatching { api.listenPlaylists() }

    suspend fun playlistTracks(
        playlistId: String,
        page: Int = 1,
        pageSize: Int = 50,
    ): Result<PlaylistTracksResponse> = runCatching {
        api.listenPlaylistTracks(playlistId, page, pageSize)
    }

    suspend fun recommendSongs(): Result<SongSearchResponse> =
        runCatching { api.listenDiscoverRecommendSongs() }

    suspend fun discoverPlaylists(limit: Int = 12): Result<PlaylistsResponse> =
        runCatching { api.listenDiscoverPlaylists(limit) }

    suspend fun discoverPlaylistTracks(
        playlistId: String,
        page: Int = 1,
        pageSize: Int = 50,
    ): Result<PlaylistTracksResponse> = runCatching {
        api.listenDiscoverPlaylistTracks(playlistId, page, pageSize)
    }

    suspend fun toplist(): Result<ToplistResponse> = runCatching { api.listenDiscoverToplist() }

    suspend fun toplistTracks(
        toplistId: String,
        page: Int = 1,
        pageSize: Int = 50,
    ): Result<PlaylistTracksResponse> = runCatching {
        api.listenDiscoverToplistTracks(toplistId, page, pageSize)
    }

    suspend fun history(limit: Int = 50): Result<ListenHistoryResponse> =
        runCatching { api.listenHistory(limit) }

    suspend fun localTracks(): Result<LocalTracksResponse> = runCatching { api.listenLocalTracks() }

    suspend fun uploadLocalTrack(
        file: MultipartBody.Part,
        name: RequestBody? = null,
        artist: RequestBody? = null,
        album: RequestBody? = null,
        durationMs: RequestBody? = null,
        coverUrl: RequestBody? = null,
    ): Result<SongMeta> = runCatching {
        api.uploadListenLocalTrack(file, name, artist, album, durationMs, coverUrl)
    }

    suspend fun deleteLocalTrack(songId: String): Result<Unit> = runCatching {
        val tid = songId.removePrefix("local:")
        val response = api.deleteListenLocalTrack(tid)
        if (!response.isSuccessful) error("删除失败: HTTP ${response.code()}")
        Unit
    }

    suspend fun songUrl(songId: String): Result<SongUrlResponse> =
        runCatching { api.listenSongUrl(songId) }

    suspend fun lyric(songId: String): Result<SongLyricResponse> =
        runCatching { api.listenSongLyric(songId) }

    suspend fun qrKey(): Result<QrKeyResponse> = runCatching { api.listenQrKey() }

    suspend fun qrStatus(key: String): Result<QrStatusResponse> =
        runCatching { api.listenQrStatus(key) }

    suspend fun importCookie(cookie: String): Result<QrStatusResponse> =
        runCatching { api.listenImportCookie(ImportCookieRequest(cookie)) }

    suspend fun logoutNetease(): Result<Unit> = runCatching {
        val response = api.listenLogout()
        if (!response.isSuccessful) error("退出网易云失败: HTTP ${response.code()}")
        Unit
    }

    private fun parse(obj: JsonObject): ListenWsEvent? {
        val type = obj["type"]?.jsonPrimitive?.contentOrNull ?: return null
        val origin = obj["origin_uid"]?.jsonPrimitive?.contentOrNull
        return when (type) {
            "PLAY", "PAUSE", "SEEK", "NEXT", "PREV",
            "QUEUE_APPEND", "QUEUE_REMOVE", "QUEUE_CLEAR" -> ListenWsEvent.RoomChanged(type, origin)
            "LOGIN_OK", "LOGOUT", "COOKIE_EXPIRED" -> ListenWsEvent.LoginChanged
            else -> null
        }
    }
}
