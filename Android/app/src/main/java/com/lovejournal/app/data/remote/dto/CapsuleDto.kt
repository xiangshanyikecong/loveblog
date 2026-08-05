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
// 主端·时间胶囊 (capsules) — /v1/capsules
// 字段名严格镜像后端 app.schemas.capsule (snake_case)。
// 未到 open_at 前，content / media_url 由后端置空（masked）。
// ---------------------------------------------------------------------------

@Serializable
data class CapsuleCreateRequest(
    val content: String? = null,
    // ISO-8601 datetime，到此刻才解锁。
    val open_at: String,
    val media_url: String? = null,
    // "audio" | "video"
    val media_type: String? = null,
    val media_duration_sec: Int? = null,
)

@Serializable
data class CapsuleResponse(
    val uuid: String,
    val content: String? = null,
    val open_at: String = "",
    val created_at: String = "",
    val author_uid: String = "",
    val author_nickname: String = "",
    val is_open: Boolean = false,
    val has_media: Boolean = false,
    val media_type: String? = null,
    val media_duration_sec: Int? = null,
    val media_url: String? = null,
)
