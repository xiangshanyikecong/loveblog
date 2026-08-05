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
// 小屋·足迹地图 (cottage footprints) — /v1/cottage/footprints
// 字段名严格镜像后端 app.schemas.footprint (snake_case)。
// 后端基于「报备打卡」解析出的城市文本聚合，仅返回城市与时间，无经纬度。
// ---------------------------------------------------------------------------

@Serializable
data class FootprintCity(
    val city: String = "",
    val count: Int = 0,
    val first_at: String = "",
    val last_at: String = "",
)

@Serializable
data class FootprintRecent(
    val city: String = "",
    val author_nickname: String = "",
    val created_at: String = "",
)

@Serializable
data class FootprintResponse(
    val cities: List<FootprintCity> = emptyList(),
    val total_cities: Int = 0,
    val total_checkins: Int = 0,
    val recent: List<FootprintRecent> = emptyList(),
)
