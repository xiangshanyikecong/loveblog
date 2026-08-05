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
import com.lovejournal.app.data.remote.dto.CanvasArtworkCreateRequest
import com.lovejournal.app.data.remote.dto.CanvasArtworkListResponse
import com.lovejournal.app.data.remote.dto.CanvasArtworkResponse
import com.lovejournal.app.data.remote.dto.MomentCreateRequest
import com.lovejournal.app.data.remote.dto.UploadResponse
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import retrofit2.Response
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

@Singleton
class CanvasRepository @Inject constructor(
    private val api: LoveApiService,
    @Named("ws") wsClient: OkHttpClient,
    serverConfig: ServerConfig,
    json: Json,
) {
    private val socket = CottageWebSocket(wsClient, serverConfig, json, "/cottage/canvas/ws")
    val events: SharedFlow<JsonObject> = socket.events
    val connected: SharedFlow<Boolean> = socket.connected
    fun connect() = socket.connect()
    fun disconnect() = socket.close()
    fun send(value: String) = socket.send(value)

    suspend fun uploadTimelineImage(file: MultipartBody.Part): Result<UploadResponse> =
        runCatching { api.uploadTimeline(file) }

    suspend fun createMoment(content: String, mediaUrls: List<String>): Result<Unit> =
        runCatching { api.createMoment(MomentCreateRequest(content = content, media_urls = mediaUrls)); Unit }

    // ---- Canvas 作品集 (gallery) ----

    suspend fun listArtworks(page: Int = 1, pageSize: Int = 20): Result<CanvasArtworkListResponse> =
        runCatching { api.canvasArtworks(page, pageSize) }

    /**
     * Persist a snapshot of the current board. ``idempotencyKey`` lets the
     * Android SyncEngine retry a save across reconnects without writing
     * duplicate rows; the server encodes the key in the row's title to
     * dedup without a dedicated column.
     */
    suspend fun createArtwork(
        title: String?,
        strokesJson: String,
        thumbDataUrl: String,
        width: Int = 960,
        height: Int = 600,
        idempotencyKey: String? = null,
    ): Result<CanvasArtworkResponse> = runCatching {
        api.createCanvasArtwork(
            idempotencyKey = idempotencyKey,
            body = CanvasArtworkCreateRequest(
                title = title,
                strokes_json = strokesJson,
                thumb_data_url = thumbDataUrl,
                width = width,
                height = height,
                idempotency_key = idempotencyKey,
            ),
        )
    }

    suspend fun getArtwork(caid: String): Result<CanvasArtworkResponse> =
        runCatching { api.canvasArtwork(caid) }

    suspend fun deleteArtwork(caid: String): Result<Unit> = runCatching {
        val resp = api.deleteCanvasArtwork(caid)
        if (!resp.isSuccessful) throw IllegalStateException("删除失败 (${resp.code()})")
        Unit
    }

    @Suppress("unused")
    private fun keepTypes(resp: Response<Unit>): Response<Unit> = resp
}