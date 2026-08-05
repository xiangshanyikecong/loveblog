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
import com.lovejournal.app.data.remote.dto.LedgerCreateRequest
import com.lovejournal.app.data.remote.dto.LedgerListResponse
import com.lovejournal.app.data.remote.dto.LedgerSummaryResponse
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 小屋·情侣账本。共享账本：任一方记账 / 删除；summary 给出总支出、分类占比与
 * 「谁欠谁」净额。金额单位为分(cents)。网络直连，与 Wishlist 范式一致。
 */
@Singleton
class LedgerRepository @Inject constructor(
    private val api: LoveApiService,
) {
    /** @param month "YYYY-MM" 过滤；category 分类过滤。 */
    suspend fun list(month: String? = null, category: String? = null, page: Int = 1): Result<LedgerListResponse> =
        runCatching { api.ledger(category = category, month = month, page = page) }

    suspend fun summary(month: String? = null): Result<LedgerSummaryResponse> =
        runCatching { api.ledgerSummary(month) }

    suspend fun create(
        title: String,
        amountCents: Int,
        note: String?,
        category: String?,
        payer: String,
        splitType: String,
        spentOn: String,
    ): Result<Unit> = runCatching {
        api.createLedger(
            LedgerCreateRequest(
                title = title,
                amount_cents = amountCents,
                note = note,
                category = category,
                payer = payer,
                split_type = splitType,
                spent_on = spentOn,
            ),
        )
        Unit
    }

    suspend fun delete(leid: String): Result<Unit> = runCatching {
        val response = api.deleteLedger(leid)
        if (!response.isSuccessful) throw IllegalStateException("删除失败 (${response.code()})")
        Unit
    }
}
