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

package com.lovejournal.app.data.remote.dto

import kotlinx.serialization.Serializable

// ---------------------------------------------------------------------------
// 小屋·情侣账本 (cottage ledger) — /v1/cottage/ledger
// 字段名严格镜像后端 app.schemas.ledger (snake_case)。金额以「分」(cents) 存储。
// ---------------------------------------------------------------------------

@Serializable
data class LedgerCreateRequest(
    val title: String,
    // 金额，单位「分」。
    val amount_cents: Int,
    val note: String? = null,
    val category: String? = null,
    // 谁付的（相对调用者）："me" | "partner"
    val payer: String = "me",
    // 分摊方式："aa" 平摊 | "treat" 请客 | "owed_full" 全欠
    val split_type: String = "aa",
    // ISO date "YYYY-MM-DD"
    val spent_on: String,
)

@Serializable
data class LedgerResponse(
    val leid: String,
    val title: String,
    val note: String? = null,
    val amount_cents: Int = 0,
    val category: String? = null,
    val split_type: String = "aa",
    val spent_on: String = "",
    val payer_uid: String = "",
    val payer_nickname: String = "",
    val author_uid: String = "",
    val author_nickname: String = "",
    val created_at: String = "",
)

@Serializable
data class LedgerListResponse(
    val items: List<LedgerResponse> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    val page_size: Int = 30,
    val has_next: Boolean = false,
)

@Serializable
data class LedgerPayerStat(
    val uid: String = "",
    val nickname: String = "",
    val paid_cents: Int = 0,
)

@Serializable
data class LedgerCategoryStat(
    val category: String = "",
    val amount_cents: Int = 0,
)

@Serializable
data class LedgerBalance(
    val settled: Boolean = true,
    val debtor_uid: String? = null,
    val debtor_nickname: String? = null,
    val creditor_uid: String? = null,
    val creditor_nickname: String? = null,
    val amount_cents: Int = 0,
)

@Serializable
data class LedgerSummaryResponse(
    val month: String? = null,
    val total_spent_cents: Int = 0,
    val entry_count: Int = 0,
    val by_payer: List<LedgerPayerStat> = emptyList(),
    val by_category: List<LedgerCategoryStat> = emptyList(),
    val balance: LedgerBalance = LedgerBalance(),
)
