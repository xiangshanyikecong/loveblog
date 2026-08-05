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

package com.lovejournal.app.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.lovejournal.app.data.local.dao.EventDao
import com.lovejournal.app.data.local.dao.MessageDao
import com.lovejournal.app.data.local.dao.MoodDao
import com.lovejournal.app.data.local.dao.SyncQueueDao
import com.lovejournal.app.data.local.entity.EventEntity
import com.lovejournal.app.data.local.entity.MessageEntity
import com.lovejournal.app.data.local.entity.MoodEntity
import com.lovejournal.app.data.local.entity.SyncQueueEntity

@Database(
    entities = [
        MessageEntity::class,
        MoodEntity::class,
        EventEntity::class,
        SyncQueueEntity::class,
    ],
    version = 2,
    exportSchema = false,
)
abstract class LoveDatabase : RoomDatabase() {
    abstract fun messageDao(): MessageDao
    abstract fun moodDao(): MoodDao
    abstract fun eventDao(): EventDao
    abstract fun syncQueueDao(): SyncQueueDao
}
