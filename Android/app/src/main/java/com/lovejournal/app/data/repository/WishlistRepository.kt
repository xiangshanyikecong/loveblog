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
import com.lovejournal.app.data.remote.dto.WishCreateRequest
import com.lovejournal.app.data.remote.dto.WishListResponse
import com.lovejournal.app.data.remote.dto.WishUpdateRequest
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 小屋·心愿单。Shared list — either partner may add / complete / reopen / delete
 * any wish. Network-backed (mirrors Events/Articles repos); offline caching is a
 * later enhancement.
 */
@Singleton
class WishlistRepository @Inject constructor(
    private val api: LoveApiService,
) {
    /** @param status null = all, "pending" or "completed" to filter. */
    suspend fun list(status: String? = null): Result<WishListResponse> = runCatching {
        api.wishes(status)
    }

    suspend fun create(
        title: String,
        description: String?,
        category: String?,
        targetDate: String?,
        priority: Int,
    ): Result<Unit> = runCatching {
        api.createWish(
            WishCreateRequest(
                title = title,
                description = description,
                category = category,
                target_date = targetDate,
                priority = priority,
            ),
        )
        Unit
    }

    suspend fun update(
        wid: String,
        title: String,
        description: String?,
        category: String?,
    ): Result<Unit> = runCatching {
        api.updateWish(
            wid,
            WishUpdateRequest(title = title, description = description, category = category),
        )
        Unit
    }

    suspend fun complete(wid: String): Result<Unit> = runCatching { api.completeWish(wid); Unit }

    suspend fun reopen(wid: String): Result<Unit> = runCatching { api.reopenWish(wid); Unit }

    suspend fun delete(wid: String): Result<Unit> = runCatching {
        val response = api.deleteWish(wid)
        if (!response.isSuccessful) {
            throw IllegalStateException("删除失败 (${response.code()})")
        }
        Unit
    }
}
