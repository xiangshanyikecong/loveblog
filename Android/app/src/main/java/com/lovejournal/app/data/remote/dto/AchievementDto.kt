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
// 小屋·情侣成就/等级 (cottage achievements) — /v1/cottage/achievements
// 字段名严格镜像后端 app.schemas.achievements (snake_case)。
// stats 是开放字典：键为统计项 code（love_days/articles/...），值是计数，
// 展示顺序由客户端 STAT_LABELS 决定，未知键直接忽略。
// badge.tier: none | bronze | silver | gold；category: record | habit | interact | time。
// ---------------------------------------------------------------------------

@Serializable
data class CoupleLevel(
    val level: Int = 1,
    val title: String = "",
    val points: Int = 0,
    // 满级时为 null。
    val next_level_points: Int? = null,
    val next_level_title: String? = null,
    // 0-100，距下一等级的进度（满级恒为 100）。
    val progress_percent: Int = 0,
)

@Serializable
data class BadgeProgress(
    val code: String,
    val name: String,
    val description: String = "",
    val icon: String = "",
    val category: String = "",
    val tier: String = "none",
    val achieved: Boolean = false,
    val current: Int = 0,
    val next_target: Int? = null,
)

@Serializable
data class AchievementsResponse(
    val generated_at: String = "",
    val stats: Map<String, Int> = emptyMap(),
    val level: CoupleLevel,
    val badges: List<BadgeProgress> = emptyList(),
)
