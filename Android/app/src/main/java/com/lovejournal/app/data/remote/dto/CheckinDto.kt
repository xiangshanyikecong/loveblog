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
// 主端·报备签到 (check-ins) — /v1/checkins
// 字段名严格镜像后端 app.schemas.checkin (snake_case)。
// 隐私不变量：latitude/longitude 仅在创建请求里临时上传（后端反查地名后即丢弃，
// 绝不落库、绝不回传）；响应里只有 location_text/status，没有坐标。
// 读取端遵循「自己看不到自己」——latest/list 只返回 TA 的报备。
// media_urls 必须是后端返回的 server-relative "/uploads/..." 路径。
// ---------------------------------------------------------------------------

@Serializable
data class CheckInCreateRequest(
    val content: String? = null,
    val media_urls: List<String> = emptyList(),
    val latitude: Double? = null,
    val longitude: Double? = null,
    val location_permission_denied: Boolean = false,
)

@Serializable
data class CheckInResponse(
    val cid: String,
    val author_uid: String = "",
    val author_nickname: String = "",
    val content: String? = null,
    val media_urls: List<String> = emptyList(),
    val location_text: String? = null,
    // resolved | omitted | permission_denied | lookup_failed
    val location_status: String = "",
    val location_provider: String? = null,
    val created_at: String = "",
)

@Serializable
data class CheckInLatestResponse(
    val item: CheckInResponse? = null,
)

@Serializable
data class CheckInListResponse(
    val items: List<CheckInResponse> = emptyList(),
    val page: Int = 1,
    val page_size: Int = 20,
    val total: Int = 0,
    val has_next: Boolean = false,
)
