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
// 小屋·恋爱月报 (cottage reports) — /v1/cottage/reports/monthly
// 字段名严格镜像后端 app.schemas.cottage_report (snake_case)。只读统计。
// ---------------------------------------------------------------------------

@Serializable
data class CottageMoodStat(
    val mood: String = "",
    val emoji: String? = null,
    val count: Int = 0,
)

@Serializable
data class CottageReportHighlight(
    val kind: String = "",
    val title: String = "",
    val subtitle: String? = null,
    val occurred_at: String? = null,
)

@Serializable
data class CottageMonthlyReportResponse(
    val year: Int = 0,
    val month: Int = 0,
    val start_date: String = "",
    val end_date: String = "",
    val generated_at: String = "",
    // 各项计数：checkins/moods/questions/answers/chat_messages/
    // wishes_created/wishes_completed/plans_created/plans_completed/reminders_created
    val stats: Map<String, Int> = emptyMap(),
    val top_moods: List<CottageMoodStat> = emptyList(),
    val highlights: List<CottageReportHighlight> = emptyList(),
)
