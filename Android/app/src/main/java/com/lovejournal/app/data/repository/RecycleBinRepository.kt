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
import com.lovejournal.app.data.remote.dto.RecycleBinResponse
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 主端·回收站。聚合 article/album/event/moment/message 五类软删项，支持恢复、
 * 永久删除与清空。网络直连，与其余 REST 模块范式一致。
 */
@Singleton
class RecycleBinRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun list(type: String? = null): Result<RecycleBinResponse> =
        runCatching { api.recycleBin(type) }

    suspend fun restore(type: String, id: String): Result<Unit> = runCatching {
        val response = api.restoreRecycleItem(type, id)
        if (!response.isSuccessful) throw IllegalStateException("恢复失败 (${response.code()})")
        Unit
    }

    suspend fun deleteForever(type: String, id: String): Result<Unit> = runCatching {
        val response = api.deleteRecycleItem(type, id)
        if (!response.isSuccessful) throw IllegalStateException("删除失败 (${response.code()})")
        Unit
    }

    suspend fun clear(type: String? = null): Result<Unit> = runCatching {
        val response = api.clearRecycleBin(type)
        if (!response.isSuccessful) throw IllegalStateException("清空失败 (${response.code()})")
        Unit
    }
}
