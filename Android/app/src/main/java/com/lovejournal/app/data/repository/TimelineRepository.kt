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
import com.lovejournal.app.data.remote.dto.MomentCreateRequest
import com.lovejournal.app.data.remote.dto.TimelineListResponse
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 主端·时间线。动态流（含评论树展示）。本期支持列表 / 发纯文字动态 / 删除；
 * 图片、语音上传与评论发布需上传链路，后续补。网络直连。
 */
@Singleton
class TimelineRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun list(page: Int = 1): Result<TimelineListResponse> =
        runCatching { api.timeline(page = page) }

    suspend fun post(content: String, visibility: String): Result<Unit> = runCatching {
        api.createMoment(MomentCreateRequest(content = content, visibility = visibility))
        Unit
    }

    suspend fun delete(mid: String): Result<Unit> = runCatching {
        val response = api.deleteMoment(mid)
        if (!response.isSuccessful) throw IllegalStateException("删除失败 (${response.code()})")
        Unit
    }
}
