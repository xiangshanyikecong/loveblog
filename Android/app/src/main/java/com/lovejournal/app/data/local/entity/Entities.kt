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

package com.lovejournal.app.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(tableName = "messages")
data class MessageEntity(
    @PrimaryKey val msgId: String,
    val content: String,
    val isPublic: Boolean,
    val authorUid: String?,
    val authorNickname: String?,
    val createdAt: String,
    val version: Int,
    // True while a locally-created message has not yet been confirmed by the server.
    val pendingSync: Boolean = false,
)

@Entity(tableName = "moods")
data class MoodEntity(
    @PrimaryKey val mid: String,
    val authorUid: String,
    val authorNickname: String,
    val isSelf: Boolean,
    val moodDate: String,
    val mood: String,
    val emoji: String?,
    val note: String?,
    val updatedAt: String,
)

@Entity(tableName = "events")
data class EventEntity(
    @PrimaryKey val eid: String,
    val title: String,
    val date: String,
    val type: String,
    val isImportant: Boolean,
    val isYearlyRepeat: Boolean,
    val nextOccurrenceDays: Int?,
)

/**
 * A queued mutation made while offline (or that failed to reach the server).
 * The [SyncWorker] drains this table when connectivity returns.
 */
@Entity(
    tableName = "sync_queue",
    indices = [Index(value = ["scope", "idempotencyKey"], unique = true)],
)
data class SyncQueueEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    // e.g. "message.create", "mood.upsert"
    val action: String,
    // JSON-encoded request payload.
    val payload: String,
    // Client-side id correlating an optimistic local row to its queued op.
    val localRef: String,
    // Prevents one account or self-hosted server from replaying another one's work.
    @ColumnInfo(defaultValue = "'legacy'") val scope: String,
    // Stable across retries; the backend persists this Idempotency-Key.
    @ColumnInfo(defaultValue = "''") val idempotencyKey: String,
    val createdAt: Long = System.currentTimeMillis(),
    val retryCount: Int = 0,
    val lastError: String? = null,
)
