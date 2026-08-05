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
data class DashboardResponse(
    val love_clock: LoveClock,
    val stats: DashboardStats,
    val couple: CoupleInfo,
    val recent_events: List<EventResponse> = emptyList(),
    val latest_messages: List<MessageResponse> = emptyList(),
)

@Serializable
data class LoveClock(
    val days: Long = 0,
    val hours: Long = 0,
    val minutes: Long = 0,
    val seconds: Long = 0,
)

@Serializable
data class DashboardStats(
    val article_count: Int = 0,
    val album_count: Int = 0,
    val event_count: Int = 0,
    val message_count: Int = 0,
)

@Serializable
data class CoupleInfo(
    val partner_a: CoupleMember? = null,
    val partner_b: CoupleMember? = null,
)

@Serializable
data class CoupleMember(
    val role: String,
    val nickname: String? = null,
    val avatar: String? = null,
)

@Serializable
data class EventResponse(
    val eid: String,
    val title: String,
    val date: String,
    val type: String,
    val creator_uid: String,
    val creator_nickname: String,
    val is_important: Boolean = false,
    val is_yearly_repeat: Boolean = false,
    val visibility: String = "public",
    val tags: List<String> = emptyList(),
    val next_occurrence_days: Int? = null,
    val created_at: String,
)
