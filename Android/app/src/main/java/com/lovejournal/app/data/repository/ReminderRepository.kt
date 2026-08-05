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

import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.ReminderCreateRequest
import com.lovejournal.app.data.remote.dto.ReminderListResponse
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 小屋·提醒。共享提醒清单：任一方可创建/完成/重开/删除；audience 控制提醒对象
 * （both 两人 / me 仅我 / partner 仅 TA）。网络直连，与 Wishlist 范式一致。
 */
@Singleton
class ReminderRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun list(includeDone: Boolean = false): Result<ReminderListResponse> =
        runCatching { api.reminders(includeDone = includeDone) }

    suspend fun create(
        title: String,
        note: String?,
        remindAtIso: String,
        audience: String,
    ): Result<Unit> = runCatching {
        api.createReminder(
            ReminderCreateRequest(title = title, note = note, remind_at = remindAtIso, audience = audience),
        )
        Unit
    }

    suspend fun markDone(rid: String): Result<Unit> = runCatching { api.markReminderDone(rid); Unit }

    suspend fun reopen(rid: String): Result<Unit> = runCatching { api.reopenReminder(rid); Unit }

    suspend fun delete(rid: String): Result<Unit> = runCatching {
        val response = api.deleteReminder(rid)
        if (!response.isSuccessful) throw IllegalStateException("删除失败 (${response.code()})")
        Unit
    }
}
