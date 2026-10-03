/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
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

import com.lovejournal.app.R
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.uiText
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import retrofit2.HttpException
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import javax.net.ssl.SSLException
import javax.net.ssl.SSLHandshakeException

/**
 * Maps low-level network failures to localized [UiText] for the login /
 * test-connection UI. Raw OkHttp English strings are intentionally avoided —
 * they are meaningless to most users on a self-hosted setup. Server-provided
 * `detail` messages are surfaced verbatim as [UiText.Raw].
 */
object NetworkErrors {

    private val json = Json { ignoreUnknownKeys = true }

    fun toUiText(throwable: Throwable): UiText {
        val root = throwable.rootCause()
        return when (root) {
            is UnknownHostException -> uiText(R.string.error_unknown_host)
            is ConnectException -> uiText(R.string.error_connect)
            is SocketTimeoutException -> uiText(R.string.error_timeout)
            is SSLHandshakeException -> uiText(R.string.error_ssl_handshake)
            is SSLException -> uiText(R.string.error_ssl)
            is HttpException -> root.detailMessage()?.let { UiText.Raw(it) } ?: run {
                when (root.code()) {
                    401 -> uiText(R.string.error_401)
                    403 -> uiText(R.string.error_403)
                    404 -> uiText(R.string.error_404)
                    else -> uiText(R.string.error_server_code, root.code())
                }
            }
            is IOException ->
                root.message?.takeIf { it.isNotBlank() }
                    ?.let { uiText(R.string.error_network, it) }
                    ?: uiText(R.string.error_network_fallback)
            else ->
                throwable.message?.takeIf { it.isNotBlank() }?.let { UiText.Raw(it) }
                    ?: uiText(R.string.msg_operation_failed)
        }
    }

    /**
     * Extracts the `detail` field from a FastAPI error body so the backend
     * message is surfaced verbatim. Handles both shapes FastAPI emits:
     * `{"detail": "message"}` and the 422 validation form
     * `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`.
     * Returns null when the body is unreadable or not JSON, so callers fall
     * back to the generic per-status messages.
     */
    private fun HttpException.detailMessage(): String? = runCatching {
        val body = response()?.errorBody()?.string().orEmpty()
        if (body.isBlank()) return@runCatching null
        val detail = json.parseToJsonElement(body).jsonObject["detail"] ?: return@runCatching null
        when {
            detail is JsonPrimitive && detail.isString -> detail.content
            detail is JsonArray -> detail
                .filterIsInstance<JsonObject>()
                .mapNotNull { validationMessage(it) }
                .joinToString("；")
                .takeIf { it.isNotBlank() }
            else -> null
        }
    }.getOrNull()

    private fun validationMessage(item: JsonObject): String? {
        val msg = (item["msg"] as? JsonPrimitive)?.takeIf { it.isString }?.content ?: return null
        val field = (item["loc"] as? JsonArray)
            ?.filterIsInstance<JsonPrimitive>()
            ?.mapNotNull { it.takeIf { p -> p.isString }?.content }
            ?.lastOrNull()
        return if (field.isNullOrBlank()) msg else "$field: $msg"
    }

    private fun Throwable.rootCause(): Throwable {
        var current: Throwable = this
        while (current.cause != null && current.cause !== current) {
            current = current.cause!!
        }
        return current
    }
}
