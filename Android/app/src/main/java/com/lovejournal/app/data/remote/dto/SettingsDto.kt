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
// 主端·设置 (settings) — /v1/settings
// 后端 SiteSetting 字段众多，但服务器路径 / 媒体策略类配置不适合移动端修改，
// 这里只取移动端有意义的字段（ignoreUnknownKeys 自动忽略其余）。
// 更新请求 extra="forbid"：只发后端已定义的字段，null 由 explicitNulls=false 省略。
// ---------------------------------------------------------------------------

@Serializable
data class SiteSettingResponse(
    val site_name: String = "",
    // ISO-8601 datetime；恋爱开始日，驱动首页恋爱天数。
    val love_start_date: String? = null,
    val allow_registration: Boolean = false,
)

@Serializable
data class SiteSettingUpdateRequest(
    val site_name: String? = null,
    val love_start_date: String? = null,
    val allow_registration: Boolean? = null,
)
