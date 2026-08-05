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
data class MoodCheckinRequest(
    val mood: String,
    val emoji: String? = null,
    val note: String? = null,
    val mood_date: String? = null,
)

@Serializable
data class MoodResponse(
    val mid: String,
    val author_uid: String,
    val author_nickname: String,
    val is_self: Boolean = false,
    val mood_date: String,
    val mood: String,
    val emoji: String? = null,
    val note: String? = null,
    val created_at: String,
    val updated_at: String,
)

@Serializable
data class MoodTodayResponse(
    val mine: MoodResponse? = null,
    val partner: MoodResponse? = null,
)

@Serializable
data class MoodCalendarResponse(
    val year: Int,
    val month: Int,
    val items: List<MoodResponse> = emptyList(),
)
