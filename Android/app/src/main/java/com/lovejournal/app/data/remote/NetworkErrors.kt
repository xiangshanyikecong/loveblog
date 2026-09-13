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
 * Maps low-level network failures to short, actionable Chinese messages for the
 * login / test-connection UI. Raw OkHttp English strings are intentionally
 * avoided — they are meaningless to most users on a self-hosted setup.
 */
object NetworkErrors {

    private val json = Json { ignoreUnknownKeys = true }

    fun toUserMessage(throwable: Throwable): String {
        val root = throwable.rootCause()
        return when (root) {
            is UnknownHostException ->
                "无法解析服务器地址，请检查域名或 IP 是否输入正确"
            is ConnectException ->
                "无法连接服务器，请检查地址、端口（默认 8000）与 Wi‑Fi/局域网"
            is SocketTimeoutException ->
                "连接超时，请确认手机与服务器在同一网络且后端已启动"
            is SSLHandshakeException ->
                "HTTPS 握手失败。自部署若无 TLS，请改用 http:// 开头"
            is SSLException ->
                "安全连接失败，请确认协议（http/https）与证书配置是否正确"
            is HttpException -> root.detailMessage() ?: run {
                when (root.code()) {
                    401 -> "未授权，请检查用户名与密码"
                    403 -> "访问被拒绝"
                    404 -> "服务器可达，但未找到接口（请确认地址含端口 :8000）"
                    else -> "服务器返回错误 (${root.code()})"
                }
            }
            is IOException ->
                "网络异常：${root.message?.takeIf { it.isNotBlank() } ?: "请检查网络连接"}"
            else ->
                throwable.message?.takeIf { it.isNotBlank() } ?: "操作失败，请稍后重试"
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
