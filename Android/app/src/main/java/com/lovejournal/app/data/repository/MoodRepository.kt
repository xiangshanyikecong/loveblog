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

import androidx.room.withTransaction
import com.lovejournal.app.data.ConnectivityMonitor
import com.lovejournal.app.data.local.LoveDatabase
import com.lovejournal.app.data.local.dao.MoodDao
import com.lovejournal.app.data.local.dao.SyncQueueDao
import com.lovejournal.app.data.local.entity.MoodEntity
import com.lovejournal.app.data.local.entity.SyncQueueEntity
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.dto.MoodCheckinRequest
import com.lovejournal.app.sync.SyncActions
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class MoodRepository @Inject constructor(
    private val api: LoveApiService,
    private val db: LoveDatabase,
    private val moodDao: MoodDao,
    private val syncQueueDao: SyncQueueDao,
    private val session: SessionManager,
    private val serverConfig: ServerConfig,
    private val connectivity: ConnectivityMonitor,
    private val json: Json,
) {
    fun observeAll(): Flow<List<MoodEntity>> = moodDao.observeAll()

    suspend fun refreshToday(): Result<Unit> = runCatching {
        val today = LocalDate.now().toString()
        val resp = api.moodToday(today)
        val rows = listOfNotNull(resp.mine, resp.partner).map { it.toEntity() }
        moodDao.upsert(rows)
    }

    suspend fun refreshCalendar(year: Int, month: Int): Result<Unit> = runCatching {
        val resp = api.moodCalendar(year, month)
        moodDao.upsert(resp.items.map { it.toEntity() })
    }

    suspend fun checkIn(mood: String, emoji: String?, note: String?): Boolean {
        val date = LocalDate.now(ZoneId.systemDefault()).toString()
        val payload = json.encodeToString(MoodCheckinRequest(mood, emoji, note, date))
        // localRef must equal the optimistic row's id suffix so the sync engine
        // can delete the local placeholder once the server copy lands (dedup).
        val localRef = UUID.randomUUID().toString()
        val uid = session.sessionFlow.first().uid
            ?: throw IllegalStateException("登录状态已失效，请重新登录")
        val scope = serverConfig.dataScope(uid)

        db.withTransaction {
            moodDao.upsert(
                listOf(
                    MoodEntity(
                        mid = "local:$localRef",
                        authorUid = "self",
                        authorNickname = "我",
                        isSelf = true,
                        moodDate = date,
                        mood = mood,
                        emoji = emoji,
                        note = note,
                        updatedAt = Instant.now().toString(),
                    ),
                ),
            )
            syncQueueDao.enqueue(
                SyncQueueEntity(
                    action = SyncActions.MOOD_UPSERT,
                    payload = payload,
                    localRef = localRef,
                    scope = scope,
                    idempotencyKey = localRef,
                ),
            )
        }
        return connectivity.isOnline()
    }
}
