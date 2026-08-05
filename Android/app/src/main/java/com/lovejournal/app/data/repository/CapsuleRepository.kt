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
import com.lovejournal.app.data.remote.dto.CapsuleCreateRequest
import com.lovejournal.app.data.remote.dto.CapsuleResponse
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 主端·时间胶囊。写给未来的信：到 open_at 才解锁内容。本期仅纯文字胶囊，
 * 语音/视频胶囊需上传链路，后续补。网络直连。
 */
@Singleton
class CapsuleRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun list(): Result<List<CapsuleResponse>> = runCatching { api.capsules() }

    suspend fun create(content: String, openAtIso: String): Result<Unit> = runCatching {
        api.createCapsule(CapsuleCreateRequest(content = content, open_at = openAtIso))
        Unit
    }

    suspend fun delete(uuid: String): Result<Unit> = runCatching {
        val response = api.deleteCapsule(uuid)
        if (!response.isSuccessful) throw IllegalStateException("删除失败 (${response.code()})")
        Unit
    }
}
