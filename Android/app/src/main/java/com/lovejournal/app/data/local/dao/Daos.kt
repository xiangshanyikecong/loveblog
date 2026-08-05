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

package com.lovejournal.app.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.lovejournal.app.data.local.entity.EventEntity
import com.lovejournal.app.data.local.entity.MessageEntity
import com.lovejournal.app.data.local.entity.MoodEntity
import com.lovejournal.app.data.local.entity.SyncQueueEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface MessageDao {
    @Query("SELECT * FROM messages ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<MessageEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(items: List<MessageEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertOne(item: MessageEntity)

    @Query("DELETE FROM messages WHERE msgId = :msgId")
    suspend fun delete(msgId: String)

    @Query("DELETE FROM messages WHERE pendingSync = 0")
    suspend fun clearSynced()

    @Query("DELETE FROM messages")
    suspend fun clear()
}

@Dao
interface MoodDao {
    @Query("SELECT * FROM moods ORDER BY moodDate DESC")
    fun observeAll(): Flow<List<MoodEntity>>

    @Query("SELECT * FROM moods WHERE moodDate = :date")
    fun observeByDate(date: String): Flow<List<MoodEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(items: List<MoodEntity>)

    @Query("DELETE FROM moods WHERE mid = :mid")
    suspend fun delete(mid: String)

    @Query("DELETE FROM moods")
    suspend fun clear()
}

@Dao
interface EventDao {
    @Query("SELECT * FROM events ORDER BY nextOccurrenceDays IS NULL, nextOccurrenceDays ASC")
    fun observeAll(): Flow<List<EventEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(items: List<EventEntity>)

    @Query("DELETE FROM events")
    suspend fun clear()
}

@Dao
interface SyncQueueDao {
    @Insert
    suspend fun enqueue(item: SyncQueueEntity): Long

    @Query("SELECT * FROM sync_queue WHERE scope = :scope ORDER BY createdAt ASC")
    suspend fun pending(scope: String): List<SyncQueueEntity>

    @Query("SELECT COUNT(*) FROM sync_queue WHERE scope = :scope")
    fun pendingCount(scope: String): Flow<Int>

    @Query("DELETE FROM sync_queue WHERE id = :id")
    suspend fun remove(id: Long)

    @Query("DELETE FROM sync_queue")
    suspend fun clear()

    @Query("UPDATE sync_queue SET retryCount = retryCount + 1, lastError = :error WHERE id = :id")
    suspend fun markFailure(id: Long, error: String?)
}
