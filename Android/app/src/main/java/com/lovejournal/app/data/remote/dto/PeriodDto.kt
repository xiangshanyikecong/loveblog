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
// 小屋·生理期关怀 (cottage period) — /v1/cottage/period
// 字段名严格镜像后端 app.schemas.period_cycle (snake_case)。
// 日期字段为 ISO date "YYYY-MM-DD"。
// ---------------------------------------------------------------------------

@Serializable
data class PeriodCreateRequest(
    val start_date: String,
    val end_date: String? = null,
    val note: String? = null,
)

@Serializable
data class PeriodResponse(
    val pcid: String,
    val start_date: String = "",
    val end_date: String? = null,
    val note: String? = null,
    // 本次经期天数（含首尾）；进行中为 null。
    val length_days: Int? = null,
    val author_uid: String = "",
    val author_nickname: String = "",
    val created_at: String = "",
)

@Serializable
data class PeriodListResponse(
    val items: List<PeriodResponse> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class PeriodSummaryResponse(
    val cycle_count: Int = 0,
    val avg_cycle_days: Int? = null,
    val avg_period_days: Int? = null,
    val last_start: String? = null,
    val last_end: String? = null,
    val predicted_next_start: String? = null,
    val predicted_days_until: Int? = null,
    // "in_period" / "due_soon" / "overdue" / "normal" / "unknown"
    val phase: String = "unknown",
)
