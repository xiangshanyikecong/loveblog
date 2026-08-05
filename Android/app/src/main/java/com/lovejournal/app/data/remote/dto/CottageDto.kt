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
// 小屋·心愿单 (cottage wishlist) — /v1/cottage/wishes
// Field names mirror the backend pydantic schemas exactly (snake_case).
// ---------------------------------------------------------------------------

@Serializable
data class WishCreateRequest(
    val title: String,
    val description: String? = null,
    val category: String? = null,
    // ISO date "YYYY-MM-DD" or null. Omitted when null (Json.explicitNulls=false).
    val target_date: String? = null,
    val priority: Int = 0,
)

@Serializable
data class WishUpdateRequest(
    val title: String? = null,
    val description: String? = null,
    val category: String? = null,
    val target_date: String? = null,
    val priority: Int? = null,
)

@Serializable
data class WishResponse(
    val wid: String,
    val title: String,
    val description: String? = null,
    val category: String? = null,
    // "pending" | "completed" (app.models.wish.WishStatus)
    val status: String = "pending",
    val priority: Int = 0,
    val target_date: String? = null,
    val author_uid: String = "",
    val author_nickname: String = "",
    val completed_at: String? = null,
    val completed_by_uid: String? = null,
    val completed_by_nickname: String? = null,
    val created_at: String = "",
)

@Serializable
data class WishListResponse(
    val items: List<WishResponse> = emptyList(),
    val total: Int = 0,
    val pending: Int = 0,
    val completed: Int = 0,
)

// ---------------------------------------------------------------------------
// 小屋·每日一问 (cottage daily blind questions) — /v1/cottage/questions
// ---------------------------------------------------------------------------

@Serializable
data class DailyQuestionCreateRequest(
    val prompt: String,
    val question_date: String? = null,
)

@Serializable
data class DailyQuestionAnswerRequest(
    val content: String,
)

@Serializable
data class DailyQuestionAnswerDto(
    val aid: String? = null,
    val author_uid: String = "",
    val author_nickname: String = "",
    val is_self: Boolean = false,
    val answered: Boolean = false,
    val content_visible: Boolean = false,
    val content: String? = null,
    val created_at: String? = null,
    val updated_at: String? = null,
)

@Serializable
data class DailyQuestionResponse(
    val qid: String,
    val question_date: String = "",
    val prompt: String = "",
    val author_uid: String = "",
    val author_nickname: String = "",
    val revealed: Boolean = false,
    val answered_count: Int = 0,
    val partner_count: Int = 0,
    val answers: List<DailyQuestionAnswerDto> = emptyList(),
    val created_at: String = "",
    val updated_at: String = "",
)

@Serializable
data class DailyQuestionTodayResponse(
    val item: DailyQuestionResponse? = null,
)

@Serializable
data class DailyQuestionListResponse(
    val items: List<DailyQuestionResponse> = emptyList(),
    val total: Int = 0,
)
