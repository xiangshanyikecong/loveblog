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

@Serializable
data class MessageResponse(
    val msg_id: String,
    val content: String,
    val is_public: Boolean = true,
    val tags: List<String> = emptyList(),
    val is_deleted: Boolean = false,
    val version: Int = 1,
    val created_at: String,
    val author_uid: String? = null,
    val author_nickname: String? = null,
    val visitor_name: String? = null,
)

@Serializable
data class MessageListResponse(
    val items: List<MessageResponse> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class MessageCreateRequest(
    val content: String,
    val is_public: Boolean = true,
    val tags: List<String> = emptyList(),
)
