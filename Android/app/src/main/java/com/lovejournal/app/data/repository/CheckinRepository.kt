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
import com.lovejournal.app.data.remote.dto.CheckInCreateRequest
import com.lovejournal.app.data.remote.dto.CheckInListResponse
import com.lovejournal.app.data.remote.dto.CheckInResponse
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 主端·报备签到。创建（文字 + 照片 + 可选位置）与查看 TA 的最新/历史报备。
 * 后端在读取端强制「author_id != 本人」，因此 latest/list 永远只返回对方的报备。
 * 网络直连，与其余 REST 模块范式一致。
 */
@Singleton
class CheckinRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun latest(): Result<CheckInResponse?> =
        runCatching { api.checkinLatest().item }

    suspend fun list(page: Int = 1, pageSize: Int = 20): Result<CheckInListResponse> =
        runCatching { api.checkins(page = page, pageSize = pageSize) }

    suspend fun create(
        content: String?,
        mediaUrls: List<String>,
        latitude: Double?,
        longitude: Double?,
        locationPermissionDenied: Boolean,
    ): Result<Unit> = runCatching {
        api.createCheckin(
            CheckInCreateRequest(
                content = content,
                media_urls = mediaUrls,
                latitude = latitude,
                longitude = longitude,
                location_permission_denied = locationPermissionDenied,
            ),
        )
        Unit
    }
}
