/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, version 3 of the License.
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
// 小屋·轻触回应 (cottage taps) — /v1/cottage/taps
// 字段名严格镜像后端 app.schemas.cottage_tap (snake_case)。
// kind: tap（敲一敲）| heartbeat（心跳）。服务端限频 60 次/小时（429），
// 无伴侣账号时 404；记录按对保留最近 500 条。
// ---------------------------------------------------------------------------

@Serializable
data class TapCreateRequest(
    val kind: String = "tap",
)

@Serializable
data class TapResponse(
    val tid: String,
    val kind: String = "tap",
    val from_uid: String = "",
    val from_nickname: String = "",
    val to_uid: String = "",
    val to_nickname: String = "",
    val created_at: String = "",
)

@Serializable
data class TapListResponse(
    val items: List<TapResponse> = emptyList(),
    val total_kept: Int = 0,
)
