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
// 主端·通知中心 (notifications) — /v1/notifications
// 字段名严格镜像后端 app.schemas.notification (snake_case)。
// ---------------------------------------------------------------------------

@Serializable
data class NotificationResponse(
    val nid: String,
    val type: String = "",
    val title: String = "",
    val body: String? = null,
    val link: String? = null,
    val source_type: String? = null,
    val source_id: String? = null,
    val is_read: Boolean = false,
    val created_at: String = "",
    val read_at: String? = null,
)

@Serializable
data class NotificationListResponse(
    val items: List<NotificationResponse> = emptyList(),
    val total: Int = 0,
    val unread_count: Int = 0,
)

@Serializable
data class NotificationReadAllResponse(
    val updated: Int = 0,
)
