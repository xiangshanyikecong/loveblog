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
// 主端·全局搜索 (search) — /v1/search
// 字段名严格镜像后端 app.schemas.search (snake_case)。
// type: article | album | event | moment | message
// ---------------------------------------------------------------------------

@Serializable
data class SearchResultItem(
    val type: String = "",
    val id: String = "",
    val title: String = "",
    val snippet: String = "",
    val url: String = "",
    val date: String = "",
    val tags: List<String> = emptyList(),
    val visibility: String = "",
    val is_encrypted: Boolean = false,
    val author_nickname: String? = null,
)

@Serializable
data class SearchResponse(
    val items: List<SearchResultItem> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    val page_size: Int = 20,
    val q: String? = null,
    val types: List<String> = emptyList(),
    val tags: List<String> = emptyList(),
    val tag_mode: String = "any",
)
