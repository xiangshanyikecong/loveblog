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

import com.lovejournal.app.R
import com.lovejournal.app.data.local.LoveDatabase
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.AuthCookieJar
import com.lovejournal.app.data.remote.BypassHostSelection
import com.lovejournal.app.data.remote.NetworkErrors
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.LoginRequest
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.UiTextException
import com.lovejournal.app.ui.components.uiText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
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
                401 -> uiText(R.string.auth_error_wrong_credentials)
                403 -> uiText(R.string.auth_error_frozen)
                429 -> uiText(R.string.auth_error_too_frequent)
                else -> uiText(R.string.auth_error_login_failed, response.code())
            }
            throw UiTextException(msg)
        }
        val profile = try {
            api.me()
        } catch (e: HttpException) {
            if (e.code() == 401) {
                cookieJar.clear()
                throw UiTextException(uiText(R.string.auth_error_session_not_kept))
            }
            throw e
        }
        session.setLoggedIn(profile.uid, profile.nickname, profile.role, profile.avatar)
        runCatching { pushRepository.registerCurrentFcmToken().getOrThrow() }
        Unit
    }.recoverCatching { error ->
        if (error is UiTextException) throw error
        throw UiTextException(NetworkErrors.toUiText(error), error)
    }

    /**
     * Hits GET /health on the configured origin to verify reachability before login.
     * Does not require credentials.
     */
    suspend fun testConnection(serverAddress: String): Result<UiText> = withContext(Dispatchers.IO) {
        runCatching {
            val base = serverConfig.healthBaseFor(serverAddress)
            if (base.isBlank()) {
                throw UiTextException(uiText(R.string.auth_error_no_server))
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
                    throw UiTextException(
                        when (response.code) {
                            404 -> uiText(R.string.auth_health_404)
                            else -> uiText(R.string.auth_health_code, response.code)
                        },
                    )
                }
                uiText(R.string.auth_connection_ok)
            }
        }.recoverCatching { error ->
            if (error is UiTextException) throw error
            throw UiTextException(NetworkErrors.toUiText(error), error)
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

    // ---- 首次初始化引导（bootstrap）与为另一半开通账号（register） ----

    /**
     * 查询站点是否已完成首次初始化（公开接口，无需登录）。
     * 成功返回 true / false；无法识别响应或网络失败时返回失败，
     * 由调用方决定如何呈现（登录页在未知状态下不显示引导入口）。
     */
    suspend fun bootstrapStatus(): Result<Boolean> = runCatching {
        val element = api.bootstrapStatus()
        element.jsonObject["bootstrapped"]?.let { (it as? JsonPrimitive)?.booleanOrNull }
            ?: throw UiTextException(uiText(R.string.bootstrap_error_unrecognized))
    }.recoverCatching { error ->
        if (error is UiTextException) throw error
        throw UiTextException(NetworkErrors.toUiText(error), error)
    }

    /**
     * 使用实例初始化令牌创建首个伴侣账号（PartnerA），仅站点未初始化时可用。
     * 服务器要求：用户名 3-32 位小写字母/数字/下划线，密码 ≥8 位且含字母和数字。
     * [loveStartDateIso] 传 ISO-8601 日期时间或 null。
     * 成功后服务器不会自动登录，调用方应引导用户用新账号登录。
     */
    suspend fun bootstrap(
        bootstrapToken: String,
        username: String,
        password: String,
        nickname: String,
        siteName: String?,
        loveStartDateIso: String?,
    ): Result<Unit> = runCatching {
        val body = buildJsonObject {
            put("username", username)
            put("password", password)
            put("nickname", nickname)
            put("role", "PartnerA")
            if (!siteName.isNullOrBlank()) put("site_name", siteName)
            if (!loveStartDateIso.isNullOrBlank()) put("love_start_date", loveStartDateIso)
        }
        api.bootstrap(bootstrapToken, body)
        Unit
    }.recoverCatching { error ->
        throw UiTextException(
            when (error) {
                is HttpException -> when (error.code()) {
                    401 -> uiText(R.string.bootstrap_error_token)
                    403 -> uiText(R.string.bootstrap_error_disabled)
                    409 -> uiText(R.string.bootstrap_error_conflict)
                    else -> NetworkErrors.toUiText(error)
                }
                else -> NetworkErrors.toUiText(error)
            },
            error,
        )
    }

    /**
     * 为另一半开通账号：已登录的伴侣填写唯一空缺的对方名额（PartnerA↔PartnerB），
     * [role] 传调用方的相反角色（"PartnerA" 或 "PartnerB"）。
     * 服务器不会为新账号建立会话，当前登录保持不变；成功后应提示对方用该账号登录。
     */
    suspend fun registerPartner(
        username: String,
        password: String,
        nickname: String,
        role: String,
    ): Result<Unit> = runCatching {
        val body = buildJsonObject {
            put("username", username)
            put("password", password)
            put("nickname", nickname)
            put("role", role)
        }
        api.register(body)
        Unit
    }.recoverCatching { error ->
        throw UiTextException(
            when (error) {
                is HttpException -> when (error.code()) {
                    403 -> uiText(R.string.register_error_not_partner)
                    409 -> uiText(R.string.register_error_conflict)
                    else -> NetworkErrors.toUiText(error)
                }
                else -> NetworkErrors.toUiText(error)
            },
            error,
        )
    }
}
