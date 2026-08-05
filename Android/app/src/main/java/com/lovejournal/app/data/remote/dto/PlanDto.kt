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
// 小屋·约会计划 (cottage plans) — /v1/cottage/plans
// 字段名严格镜像后端 app.schemas.cottage_plan (snake_case)。
// plan_date 为 "yyyy-MM-dd"（date）；created_at/updated_at/completed_at 为 ISO datetime 字符串。
// status 取值：planned | in_progress | done | cancelled。
// ---------------------------------------------------------------------------

@Serializable
data class PlanChecklistItemDto(
    val key: String? = null,
    val text: String = "",
    val done: Boolean = false,
)

@Serializable
data class PlanCreateRequest(
    val title: String,
    val description: String? = null,
    val location: String? = null,
    // ISO 日期 "yyyy-MM-dd"，可空表示未定档期。
    val plan_date: String? = null,
    val priority: Int = 0,
    val checklist: List<PlanChecklistItemDto> = emptyList(),
)

@Serializable
data class PlanUpdateRequest(
    val title: String? = null,
    val description: String? = null,
    val location: String? = null,
    val plan_date: String? = null,
    val priority: Int? = null,
    val checklist: List<PlanChecklistItemDto>? = null,
    // planned | in_progress | done | cancelled
    val status: String? = null,
)

@Serializable
data class PlanResponse(
    val pid: String,
    val title: String = "",
    val description: String? = null,
    val location: String? = null,
    val plan_date: String? = null,
    val status: String = "planned",
    val priority: Int = 0,
    val checklist: List<PlanChecklistItemDto> = emptyList(),
    val author_uid: String = "",
    val author_nickname: String = "",
    val completed_at: String? = null,
    val completed_by_uid: String? = null,
    val completed_by_nickname: String? = null,
    val created_at: String = "",
    val updated_at: String = "",
)

@Serializable
data class PlanListResponse(
    val items: List<PlanResponse> = emptyList(),
    val total: Int = 0,
    val active: Int = 0,
    val completed: Int = 0,
    val cancelled: Int = 0,
)
