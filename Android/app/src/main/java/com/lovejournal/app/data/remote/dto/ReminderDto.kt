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
// 小屋·提醒 (cottage reminders) — /v1/cottage/reminders
// 字段名严格镜像后端 app.schemas.cottage_reminder (snake_case)。
// remind_at / created_at / updated_at / done_at 均为 ISO-8601 datetime 字符串。
// ---------------------------------------------------------------------------

@Serializable
data class ReminderCreateRequest(
    val title: String,
    val note: String? = null,
    // ISO-8601 datetime（带时区），后端会按 UTC 归一化存储。
    val remind_at: String,
    // "both" | "me" | "partner"
    val audience: String = "both",
)

@Serializable
data class ReminderResponse(
    val rid: String,
    val title: String,
    val note: String? = null,
    val remind_at: String = "",
    val audience: String = "both",
    val is_due: Boolean = false,
    val is_done: Boolean = false,
    val author_uid: String = "",
    val author_nickname: String = "",
    val done_at: String? = null,
    val done_by_uid: String? = null,
    val done_by_nickname: String? = null,
    val created_at: String = "",
    val updated_at: String = "",
)

@Serializable
data class ReminderListResponse(
    val items: List<ReminderResponse> = emptyList(),
    val total: Int = 0,
    val active: Int = 0,
    val done: Int = 0,
    val due: Int = 0,
)
