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
// 主端·时间线 (timeline / moments) — /v1/timeline
// 字段名严格镜像后端 app.schemas.moment / comment (snake_case)。
// visibility: "Public" | "PartnersOnly" | "Encrypted"（app.models.moment.Visibility 的值）。
// ---------------------------------------------------------------------------

@Serializable
data class MomentCreateRequest(
    val content: String = "",
    val media_urls: List<String> = emptyList(),
    val audio_url: String? = null,
    val audio_duration_sec: Int? = null,
    val location: String? = null,
    val visibility: String = "PartnersOnly",
    val tags: List<String> = emptyList(),
)

@Serializable
data class CommentNodeResponse(
    val cid: String = "",
    val parent_cid: String? = null,
    val content: String = "",
    val author_uid: String = "",
    val author_nickname: String = "",
    val mention_uids: List<String> = emptyList(),
    val created_at: String = "",
    val replies: List<CommentNodeResponse> = emptyList(),
)

@Serializable
data class MomentResponse(
    val mid: String,
    val author_uid: String = "",
    val author_nickname: String = "",
    val content: String = "",
    val media_urls: List<String> = emptyList(),
    val audio_url: String? = null,
    val audio_duration_sec: Int? = null,
    val location: String? = null,
    val visibility: String = "Public",
    val tags: List<String> = emptyList(),
    val timestamp: String = "",
    val comments: List<CommentNodeResponse> = emptyList(),
)

@Serializable
data class TimelineListResponse(
    val items: List<MomentResponse> = emptyList(),
    val page: Int = 1,
    val page_size: Int = 20,
    val total: Int = 0,
    val has_next: Boolean = false,
    val sort: String = "desc",
)
