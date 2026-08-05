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

package com.lovejournal.app.data.remote

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import kotlin.math.min
import kotlin.math.pow

/**
 * Reusable client for the cottage realtime channels (chat / listen / watch /
 * games). Mirrors the web `createCottageSocket` contract:
 *
 * - JSON `{"type":"PING"}` keepalive every 25s; server replies `{"type":"PONG"}`
 *   (swallowed here, not surfaced to callers).
 * - Exponential reconnect (1s → 30s) on unexpected drops.
 * - Close codes 4401 (unauthorized) / 4403 (forbidden) are terminal — no
 *   reconnect, and [authRejected] fires so the UI can react.
 *
 * Auth rides on the shared cookie jar (the `access_token` cookie is sent on the
 * upgrade handshake), so no token ever travels in the query string. The caller
 * supplies the feature path, e.g. `"/cottage/chat/ws"`.
 */
class CottageWebSocket(
    private val client: OkHttpClient,
    private val serverConfig: ServerConfig,
    private val json: Json,
    private val path: String,
) {
    private val _events = MutableSharedFlow<JsonObject>(extraBufferCapacity = 64)
    val events: SharedFlow<JsonObject> = _events

    private val _connected = MutableSharedFlow<Boolean>(replay = 1, extraBufferCapacity = 4)
    val connected: SharedFlow<Boolean> = _connected

    private val _authRejected = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val authRejected: SharedFlow<Unit> = _authRejected

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var webSocket: WebSocket? = null
    private var pingJob: Job? = null
    private var reconnectAttempts = 0

    @Volatile
    private var closedByUser = false

    fun connect() {
        closedByUser = false
        openSocket()
    }

    private fun openSocket() {
        if (closedByUser) return
        val url = wsUrl() ?: return
        webSocket = client.newWebSocket(Request.Builder().url(url).build(), listener)
    }

    private val listener = object : WebSocketListener() {
        override fun onOpen(ws: WebSocket, response: Response) {
            reconnectAttempts = 0
            _connected.tryEmit(true)
            startPing(ws)
        }

        override fun onMessage(ws: WebSocket, text: String) {
            val obj = runCatching { json.parseToJsonElement(text).jsonObject }.getOrNull() ?: return
            if ((obj["type"] as? JsonPrimitive)?.content == "PONG") return
            _events.tryEmit(obj)
        }

        override fun onClosing(ws: WebSocket, code: Int, reason: String) {
            ws.close(NORMAL_CLOSURE, null)
        }

        override fun onClosed(ws: WebSocket, code: Int, reason: String) = handleDisconnect(code)

        override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) =
            handleDisconnect(response?.code ?: -1)
    }

    private fun handleDisconnect(code: Int) {
        stopPing()
        _connected.tryEmit(false)
        if (closedByUser) return
        if (code == WS_UNAUTHORIZED || code == WS_FORBIDDEN) {
            _authRejected.tryEmit(Unit)
            return
        }
        scheduleReconnect()
    }

    private fun scheduleReconnect() {
        val delayMs = min(RECONNECT_MAX_MS, (RECONNECT_BASE_MS * 2.0.pow(reconnectAttempts)).toLong())
        reconnectAttempts++
        scope.launch {
            delay(delayMs)
            if (!closedByUser) openSocket()
        }
    }

    private fun startPing(ws: WebSocket) {
        stopPing()
        pingJob = scope.launch {
            while (isActive) {
                delay(PING_INTERVAL_MS)
                ws.send("""{"type":"PING"}""")
            }
        }
    }

    private fun stopPing() {
        pingJob?.cancel()
        pingJob = null
    }

    fun send(message: String) {
        webSocket?.send(message)
    }

    fun close() {
        closedByUser = true
        stopPing()
        webSocket?.close(NORMAL_CLOSURE, null)
        webSocket = null
    }

    /** Derives ws(s)://host[:port]/v1<path> from the configured http(s) apiBase. */
    private fun wsUrl(): String? {
        val base = serverConfig.apiBase()
        val wsBase = when {
            base.startsWith("https://") -> "wss://" + base.removePrefix("https://")
            base.startsWith("http://") -> "ws://" + base.removePrefix("http://")
            else -> return null
        }
        return wsBase.trimEnd('/') + path
    }

    private companion object {
        const val PING_INTERVAL_MS = 25_000L
        const val RECONNECT_BASE_MS = 1_000L
        const val RECONNECT_MAX_MS = 30_000L
        const val NORMAL_CLOSURE = 1000
        const val WS_UNAUTHORIZED = 4401
        const val WS_FORBIDDEN = 4403
    }
}
