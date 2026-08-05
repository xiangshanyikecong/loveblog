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
// 主端·回收站 (recycle bin) — /v1/recycle-bin
// 字段名严格镜像后端 RecycleBinItem / RecycleBinResponse (snake_case)。
// type 取值：article | album | event | moment | message。
// deleted_at 为 ISO datetime 字符串（可空）。
// ---------------------------------------------------------------------------

@Serializable
data class RecycleBinItemDto(
    val id: String,
    val type: String = "",
    val title: String = "",
    val deleted_at: String? = null,
)

@Serializable
data class RecycleBinResponse(
    val items: List<RecycleBinItemDto> = emptyList(),
    val total: Int = 0,
)
