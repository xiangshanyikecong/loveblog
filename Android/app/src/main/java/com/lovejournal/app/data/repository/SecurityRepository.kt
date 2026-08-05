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
import com.lovejournal.app.data.remote.dto.RevokeSessionsRequest
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
}
