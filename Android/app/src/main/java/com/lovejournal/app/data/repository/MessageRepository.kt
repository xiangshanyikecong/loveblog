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
import com.lovejournal.app.data.local.LoveDatabase
import com.lovejournal.app.data.ConnectivityMonitor
import com.lovejournal.app.data.local.dao.MessageDao
import com.lovejournal.app.data.local.dao.SyncQueueDao
import com.lovejournal.app.data.local.entity.MessageEntity
import com.lovejournal.app.data.local.entity.SyncQueueEntity
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.dto.MessageCreateRequest
import com.lovejournal.app.sync.SyncActions
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.time.Instant
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class MessageRepository @Inject constructor(
    private val api: LoveApiService,
    private val db: LoveDatabase,
    private val messageDao: MessageDao,
    private val syncQueueDao: SyncQueueDao,
    private val session: SessionManager,
    private val serverConfig: ServerConfig,
    private val connectivity: ConnectivityMonitor,
    private val json: Json,
) {
    fun observeMessages(): Flow<List<MessageEntity>> = messageDao.observeAll()

    suspend fun refresh(): Result<Unit> = runCatching {
        val remote = api.messages(includePrivate = true)
        messageDao.clearSynced()
        messageDao.upsert(remote.items.map { it.toEntity() })
    }

    /**
     * Optimistically inserts the message locally (marked pending), enqueues the
     * create operation, and attempts to flush immediately when online. The
     * pending row is reconciled with the server's copy by [com.lovejournal.app.sync.SyncEngine].
     */
    suspend fun send(content: String, isPublic: Boolean): SendOutcome {
        val localRef = UUID.randomUUID().toString()
        val payload = json.encodeToString(MessageCreateRequest(content, isPublic))
        val uid = session.sessionFlow.first().uid
            ?: throw IllegalStateException("登录状态已失效，请重新登录")
        val scope = serverConfig.dataScope(uid)

        db.withTransaction {
            messageDao.upsertOne(
                MessageEntity(
                    msgId = "local:$localRef",
                    content = content,
                    isPublic = isPublic,
                    authorUid = null,
                    authorNickname = "我",
                    createdAt = Instant.now().toString(),
                    version = 0,
                    pendingSync = true,
                ),
            )
            syncQueueDao.enqueue(
                SyncQueueEntity(
                    action = SyncActions.MESSAGE_CREATE,
                    payload = payload,
                    localRef = localRef,
                    scope = scope,
                    idempotencyKey = localRef,
                ),
            )
        }
        return if (connectivity.isOnline()) SendOutcome.QUEUED_ONLINE else SendOutcome.QUEUED_OFFLINE
    }

    enum class SendOutcome { QUEUED_ONLINE, QUEUED_OFFLINE }
}
