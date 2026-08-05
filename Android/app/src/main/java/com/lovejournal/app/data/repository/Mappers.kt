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

package com.lovejournal.app.data.repository

import com.lovejournal.app.data.local.entity.EventEntity
import com.lovejournal.app.data.local.entity.MessageEntity
import com.lovejournal.app.data.local.entity.MoodEntity
import com.lovejournal.app.data.remote.dto.EventResponse
import com.lovejournal.app.data.remote.dto.MessageResponse
import com.lovejournal.app.data.remote.dto.MoodResponse

fun MessageResponse.toEntity(pending: Boolean = false) = MessageEntity(
    msgId = msg_id,
    content = content,
    isPublic = is_public,
    authorUid = author_uid,
    authorNickname = author_nickname ?: visitor_name,
    createdAt = created_at,
    version = version,
    pendingSync = pending,
)

fun MoodResponse.toEntity() = MoodEntity(
    mid = mid,
    authorUid = author_uid,
    authorNickname = author_nickname,
    isSelf = is_self,
    moodDate = mood_date,
    mood = mood,
    emoji = emoji,
    note = note,
    updatedAt = updated_at,
)

fun EventResponse.toEntity() = EventEntity(
    eid = eid,
    title = title,
    date = date,
    type = type,
    isImportant = is_important,
    isYearlyRepeat = is_yearly_repeat,
    nextOccurrenceDays = next_occurrence_days,
)
