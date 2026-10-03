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
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.ReminderCreateRequest
import com.lovejournal.app.data.remote.dto.ReminderListResponse
import com.lovejournal.app.data.remote.dto.ReminderResponse
import com.lovejournal.app.ui.components.UiTextException
import com.lovejournal.app.ui.components.uiText
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.time.OffsetDateTime
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
        if (!response.isSuccessful) throw UiTextException(uiText(R.string.msg_delete_failed))
        Unit
    }

    /**
     * 编辑既有提醒（PATCH /cottage/reminders/{rid}）。服务端按
     * ``model_dump(exclude_unset=True)`` 只应用请求体里出现的字段，因此这里与
     * [entry] 逐项比较，body 只携带真正变化的键；note 允许显式传 null 清空。
     * 全部未变则不发请求。服务端收到 remind_at 会重置上次通知时间，所以时间点
     * 未变时严格不发该字段（按时刻比较，而非字符串写法）。
     */
    suspend fun update(
        entry: ReminderResponse,
        title: String,
        note: String?,
        remindAtIso: String,
        audience: String,
    ): Result<ReminderResponse> = runCatching {
        val body = buildJsonObject {
            if (title != entry.title) put("title", title)
            if (note.orEmpty() != entry.note.orEmpty()) put("note", note)
            if (!sameInstant(remindAtIso, entry.remind_at)) put("remind_at", remindAtIso)
            if (audience != entry.audience) put("audience", audience)
        }
        if (body.isEmpty()) return@runCatching entry
        api.patchReminder(entry.rid, body)
    }

    /** 比较 ISO-8601 时间点：客户端与服务端的 UTC 后缀（Z / +00:00）写法可能不同。 */
    private fun sameInstant(a: String, b: String): Boolean {
        if (a == b) return true
        return runCatching {
            OffsetDateTime.parse(a).toInstant() == OffsetDateTime.parse(b).toInstant()
        }.getOrDefault(false)
    }
}
