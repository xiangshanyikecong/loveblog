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
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import okhttp3.OkHttpClient
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

@Singleton
class DrawRepository @Inject constructor(
    private val api: LoveApiService,
    @Named("ws") wsClient: OkHttpClient,
    serverConfig: ServerConfig,
    json: Json,
) {
    private val socket = CottageWebSocket(wsClient, serverConfig, json, "/cottage/draw/ws")
    val events: SharedFlow<JsonObject> = socket.events
    val connected: SharedFlow<Boolean> = socket.connected
    fun connect() = socket.connect()
    fun disconnect() = socket.close()
    fun send(value: String) = socket.send(value)
    suspend fun state(): Result<JsonObject> = runCatching { api.drawState() }
    suspend fun matches(): Result<GameMatchListResponse> = runCatching { api.drawMatches() }
    suspend fun invite(): Result<Unit> = runCatching { api.inviteDraw(); Unit }
}
