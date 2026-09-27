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

package com.lovejournal.app.data.remote.dto

import kotlinx.serialization.Serializable

// ---------------------------------------------------------------------------
// 主端·账号安全 (security) — /v1/security/users/{uid}/...
// 字段名严格镜像后端 app.schemas.security (snake_case)。
// new_password 规则（后端校验）：长度 8-128，且同时包含字母与数字。
// ---------------------------------------------------------------------------

@Serializable
data class ChangePasswordRequest(
    val old_password: String,
    val new_password: String,
)

@Serializable
data class RevokeSessionsRequest(
    val confirm: Boolean = true,
)

// ---- 两步验证（TOTP，对齐网页端安全设置）----

@Serializable
data class TotpStatusResponse(
    val enabled: Boolean = false,
    val recovery_codes_remaining: Int = 0,
)

@Serializable
data class TotpSetupResponse(
    val secret: String,
    val uri: String,
)

@Serializable
data class TotpEnableRequest(val code: String)

@Serializable
data class TotpEnableResponse(
    val enabled: Boolean = false,
    val recovery_codes: List<String> = emptyList(),
)

@Serializable
data class TotpDisableRequest(val code: String, val password: String)

// ---- 登录设备管理 ----

@Serializable
data class LoginDeviceResponse(
    val did: String,
    val device_name: String = "",
    val ip: String? = null,
    val user_agent: String? = null,
    val first_seen_at: String = "",
    val last_login_at: String = "",
)

@Serializable
data class DeviceRevokeResponse(
    val revoked: Boolean = false,
    val new_session_version: Int = 0,
)

@Serializable
data class DevicesRevokeAllResponse(val revoked: Int = 0)

@Serializable
data class PasswordRecoveryRequest(
    val username: String,
    val new_password: String,
)
