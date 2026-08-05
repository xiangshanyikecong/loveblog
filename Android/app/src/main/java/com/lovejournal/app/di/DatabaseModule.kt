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

package com.lovejournal.app.di

import android.content.Context
import androidx.room.Room
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import com.lovejournal.app.data.local.LoveDatabase
import com.lovejournal.app.data.local.dao.EventDao
import com.lovejournal.app.data.local.dao.MessageDao
import com.lovejournal.app.data.local.dao.MoodDao
import com.lovejournal.app.data.local.dao.SyncQueueDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    private val MIGRATION_1_2 = object : Migration(1, 2) {
        override fun migrate(db: SupportSQLiteDatabase) {
            // The previous schema had no account/server ownership information.
            // Keep those entries for inspection instead of risking replay to the
            // next account. Newly queued work always has an explicit scope.
            db.execSQL("ALTER TABLE sync_queue ADD COLUMN scope TEXT NOT NULL DEFAULT 'legacy'")
            db.execSQL("ALTER TABLE sync_queue ADD COLUMN idempotencyKey TEXT NOT NULL DEFAULT ''")
            db.execSQL("UPDATE sync_queue SET idempotencyKey = localRef WHERE idempotencyKey = ''")
            db.execSQL(
                "CREATE UNIQUE INDEX IF NOT EXISTS index_sync_queue_scope_idempotencyKey " +
                    "ON sync_queue(scope, idempotencyKey)",
            )
        }
    }

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): LoveDatabase =
        Room.databaseBuilder(context, LoveDatabase::class.java, "love.db")
            .addMigrations(MIGRATION_1_2)
            .build()

    @Provides
    fun provideMessageDao(db: LoveDatabase): MessageDao = db.messageDao()

    @Provides
    fun provideMoodDao(db: LoveDatabase): MoodDao = db.moodDao()

    @Provides
    fun provideEventDao(db: LoveDatabase): EventDao = db.eventDao()

    @Provides
    fun provideSyncQueueDao(db: LoveDatabase): SyncQueueDao = db.syncQueueDao()
}
