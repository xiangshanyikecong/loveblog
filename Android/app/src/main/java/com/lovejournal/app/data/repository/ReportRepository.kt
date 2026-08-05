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
import com.lovejournal.app.data.remote.dto.CottageMonthlyReportResponse
import javax.inject.Inject
import javax.inject.Singleton

/** 小屋·恋爱月报。只读：按年月聚合双方在小屋的互动统计。网络直连。 */
@Singleton
class ReportRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun monthly(year: Int, month: Int): Result<CottageMonthlyReportResponse> =
        runCatching { api.monthlyReport(year, month) }
}
