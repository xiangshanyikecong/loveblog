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

import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.ChangePasswordRequest
import com.lovejournal.app.data.remote.dto.DeviceRevokeResponse
import com.lovejournal.app.data.remote.dto.DevicesRevokeAllResponse
import com.lovejournal.app.data.remote.dto.LoginDeviceResponse
import com.lovejournal.app.data.remote.dto.PasswordRecoveryRequest
import com.lovejournal.app.data.remote.dto.RevokeSessionsRequest
import com.lovejournal.app.data.remote.dto.TotpDisableRequest
import com.lovejournal.app.data.remote.dto.TotpEnableRequest
import com.lovejournal.app.data.remote.dto.TotpEnableResponse
import com.lovejournal.app.data.remote.dto.TotpSetupResponse
import com.lovejournal.app.data.remote.dto.TotpStatusResponse
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 主端·账号安全自助能力：修改密码、登出全部设备。
 * uid 取自当前会话（SessionManager），后端强制 uid==本人，杜绝越权。
 * 注意：两项操作都会递增 session_version，使含当前设备在内的所有会话失效，
 * 因此成功后需要重新登录——由调用方在 UI 明确告知用户。
 */
@Singleton
class SecurityRepository @Inject constructor(
    private val api: LoveApiService,
    private val session: SessionManager,
) {
    private suspend fun currentUid(): String =
        session.sessionFlow.first().uid ?: throw IllegalStateException("未登录")

    suspend fun changePassword(oldPassword: String, newPassword: String): Result<Unit> = runCatching {
        val response = api.changePassword(currentUid(), ChangePasswordRequest(oldPassword, newPassword))
        if (!response.isSuccessful) {
            throw IllegalStateException(
                when (response.code()) {
                    400 -> "旧密码不正确"
                    422 -> "新密码不符合要求（至少 8 位，且同时包含字母和数字）"
                    else -> "修改失败 (${response.code()})"
                },
            )
        }
        Unit
    }

    suspend fun revokeOtherSessions(): Result<Unit> = runCatching {
        val response = api.revokeOwnSessions(currentUid(), RevokeSessionsRequest(confirm = true))
        if (!response.isSuccessful) throw IllegalStateException("操作失败 (${response.code()})")
        Unit
    }

    // ---- 两步验证（TOTP）----

    suspend fun totpStatus(): Result<TotpStatusResponse> = runCatching { api.totpStatus() }

    /** 开始绑定：返回 secret + otpauth:// 链接（供验证器 App 手动/扫码录入）。 */
    suspend fun totpSetup(): Result<TotpSetupResponse> = runCatching { api.totpSetup() }

    /** 输入验证器 6 位码确认开启；成功返回一次性恢复码列表。 */
    suspend fun totpEnable(code: String): Result<TotpEnableResponse> = runCatching {
        api.totpEnable(TotpEnableRequest(code.trim()))
    }

    suspend fun totpDisable(code: String, password: String): Result<TotpStatusResponse> = runCatching {
        api.totpDisable(TotpDisableRequest(code.trim(), password))
    }

    // ---- 登录设备管理 ----

    suspend fun loginDevices(): Result<List<LoginDeviceResponse>> = runCatching { api.loginDevices() }

    suspend fun revokeDevice(did: String): Result<DeviceRevokeResponse> = runCatching {
        api.revokeLoginDevice(did)
    }

    suspend fun revokeAllDevices(): Result<DevicesRevokeAllResponse> = runCatching {
        api.revokeAllLoginDevices()
    }

    // ---- 忘记密码（无需登录；需要能收到站点邮件或由伴侣在后台重置时使用）----

    /**
     * 忘记密码自助找回：需要服务器部署时设定的 BOOTSTRAP_SETUP_TOKEN
     * 作为授权凭证（与网页端找回流程一致），成功后该账号全部会话失效。
     */
    suspend fun passwordRecovery(username: String, newPassword: String, bootstrapToken: String): Result<Unit> = runCatching {
        val response = api.passwordRecovery(
            bootstrapToken.trim(),
            PasswordRecoveryRequest(username.trim(), newPassword),
        )
        if (!response.isSuccessful) {
            throw IllegalStateException(
                when (response.code()) {
                    401 -> "恢复令牌不正确"
                    403 -> "站点未开启自助找回（未配置 BOOTSTRAP_SETUP_TOKEN）"
                    404 -> "用户不存在"
                    422 -> "新密码不符合要求（至少 8 位，且同时包含字母和数字）"
                    else -> "找回失败 (${response.code()})"
                },
            )
        }
        Unit
    }
}

// ---------------------------------------------------------------------------
// 与网页端安全中心对齐：两步验证（TOTP）、登录设备管理、忘记密码自助找回。
// ---------------------------------------------------------------------------

