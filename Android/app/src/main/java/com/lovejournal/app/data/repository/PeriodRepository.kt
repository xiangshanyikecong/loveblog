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
import com.lovejournal.app.data.remote.dto.PeriodCreateRequest
import com.lovejournal.app.data.remote.dto.PeriodListResponse
import com.lovejournal.app.data.remote.dto.PeriodSummaryResponse
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 小屋·生理期关怀。记录经期、读取周期统计与下次预测。数据敏感：后端限作者本人
 * 编辑 / 删除，但伴侣可见以便关怀。网络直连，与 Wishlist 范式一致。
 */
@Singleton
class PeriodRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun list(): Result<PeriodListResponse> = runCatching { api.periodCycles() }

    suspend fun summary(): Result<PeriodSummaryResponse> = runCatching { api.periodSummary() }

    suspend fun create(startDate: String, endDate: String?, note: String?): Result<Unit> =
        runCatching {
            api.createPeriod(PeriodCreateRequest(start_date = startDate, end_date = endDate, note = note))
            Unit
        }

    suspend fun delete(pcid: String): Result<Unit> = runCatching {
        val response = api.deletePeriod(pcid)
        if (!response.isSuccessful) throw IllegalStateException("删除失败 (${response.code()})")
        Unit
    }
}
