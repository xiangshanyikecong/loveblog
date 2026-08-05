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

import com.lovejournal.app.data.local.LoveDatabase
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.AuthCookieJar
import com.lovejournal.app.data.remote.BypassHostSelection
import com.lovejournal.app.data.remote.NetworkErrors
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.LoginRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import retrofit2.HttpException
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: LoveApiService,
    private val session: SessionManager,
    private val cookieJar: AuthCookieJar,
    private val db: LoveDatabase,
    private val serverConfig: ServerConfig,
    private val okHttpClient: OkHttpClient,
    private val pushRepository: PushRepository,
) {
    val sessionFlow: Flow<com.lovejournal.app.data.prefs.SessionState> get() = session.sessionFlow

    suspend fun login(username: String, password: String): Result<Unit> = runCatching {
        val response = api.login(LoginRequest(username.trim(), password))
        if (!response.isSuccessful) {
            val msg = when (response.code()) {
                401 -> "用户名或密码错误"
                403 -> "账号被冻结或封禁，请稍后再试"
                429 -> "尝试过于频繁，请稍后再试"
                else -> "登录失败 (${response.code()})"
            }
            throw IllegalStateException(msg)
        }
        val profile = try {
            api.me()
        } catch (e: HttpException) {
            if (e.code() == 401) {
                cookieJar.clear()
                throw IllegalStateException(
                    "登录成功但会话未保持。若使用 http 自部署，请确认服务端 COOKIE_SECURE 未强制开启，" +
                        "且反代未误传 X-Forwarded-Proto: https",
                )
            }
            throw e
        }
        session.setLoggedIn(profile.uid, profile.nickname, profile.role, profile.avatar)
        runCatching { pushRepository.registerCurrentFcmToken().getOrThrow() }
        Unit
    }.recoverCatching { error ->
        if (error is IllegalStateException) throw error
        throw IllegalStateException(NetworkErrors.toUserMessage(error), error)
    }

    /**
     * Hits GET /health on the configured origin to verify reachability before login.
     * Does not require credentials.
     */
    suspend fun testConnection(serverAddress: String): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val base = serverConfig.healthBaseFor(serverAddress)
            if (base.isBlank()) {
                throw IllegalStateException("请先填写服务器地址")
            }
            val request = Request.Builder()
                .url("$base/health")
                .tag(BypassHostSelection::class.java, BypassHostSelection)
                .get()
                .build()
            // Health is public. Never attach the current server's cookies to a
            // candidate host/port while the user is only testing it.
            val publicClient = okHttpClient.newBuilder()
                .cookieJar(okhttp3.CookieJar.NO_COOKIES)
                .build()
            publicClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw IllegalStateException(
                        when (response.code) {
                            404 -> "服务器可达，但未找到健康检查接口（请确认端口为 :8000）"
                            else -> "服务器返回 ${response.code}"
                        },
                    )
                }
                "连接成功，后端运行正常"
            }
        }.recoverCatching { error ->
            if (error is IllegalStateException) throw error
            throw IllegalStateException(NetworkErrors.toUserMessage(error), error)
        }
    }

    suspend fun logout() {
        // Server-side unregister and local token rotation are both attempted;
        // a stale server record then becomes undeliverable even while offline.
        runCatching { pushRepository.unregisterCurrentFcmToken().getOrThrow() }
        runCatching { api.logout() }
        cookieJar.clear()
        session.clear()
        runCatching {
            db.messageDao().clear()
            db.moodDao().clear()
            db.eventDao().clear()
            // Outbox rows are scoped by server and uid. Keep failed user writes
            // so signing back into the same account can resume them safely.
        }
    }

    fun hasSession(): Boolean = cookieJar.hasSession()
}
