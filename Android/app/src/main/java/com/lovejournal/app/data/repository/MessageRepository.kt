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
import com.lovejournal.app.R
import com.lovejournal.app.data.local.LoveDatabase
import com.lovejournal.app.data.ConnectivityMonitor
import com.lovejournal.app.data.local.dao.MessageDao
import com.lovejournal.app.data.local.dao.SyncQueueDao
import com.lovejournal.app.data.local.entity.MessageEntity
import com.lovejournal.app.data.local.entity.SyncQueueEntity
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.dto.ContentVersion
import com.lovejournal.app.data.remote.dto.MessageCreateRequest
import com.lovejournal.app.data.remote.dto.MessageResponse
import com.lovejournal.app.sync.SyncActions
import com.lovejournal.app.ui.components.UiTextException
import com.lovejournal.app.ui.components.uiText
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.time.Instant
import java.time.OffsetDateTime
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import retrofit2.HttpException

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

    /**
     * Pulls server messages into the local cache.
     *
     * Normally incremental: only rows with `updated_at` newer than the stored
     * cursor are transferred, and server-side tombstones (is_deleted=true)
     * prune local copies. The cursor lives in DataStore (not Room) so it
     * survives restarts and is cleared on logout together with the session.
     * A full reconciliation re-runs at most once per day to heal drift the
     * cursor cannot cover (lost prefs, manual data fixes, ...).
     */
    suspend fun refresh(): Result<Unit> = runCatching {
        val now = System.currentTimeMillis()
        val cursor = session.messageSyncCursorFlow.first()
        val lastFullSyncAt = session.lastFullSyncAtFlow.first()
        val needsFullSync = cursor == null ||
            lastFullSyncAt == null ||
            now - lastFullSyncAt > 24 * 60 * 60 * 1000L // daily full reconciliation

        if (needsFullSync) {
            // Full sync: replace every synced row (pending local edits are kept)
            // and seed the cursor with the freshest server timestamp.
            val remote = api.messages(includePrivate = true)
            messageDao.clearSynced()
            messageDao.upsert(remote.items.map { it.toEntity() })
            session.setMessageSyncCursor(remote.items.latestUpdatedAt())
            session.setLastFullSyncAt(now)
        } else {
            // Incremental sync. The server orders rows by (updated_at, id) asc,
            // so the last row of each page carries the newest timestamp and its
            // raw ISO string is reused verbatim as the next cursor.
            val pageSize = 200 // matches the server's page-size cap
            var nextCursor = cursor
            while (true) {
                val batch = api.messages(
                    includePrivate = true,
                    updatedAfter = nextCursor,
                    pageSize = pageSize,
                )
                if (batch.items.isEmpty()) break
                db.withTransaction {
                    batch.items.forEach { item ->
                        if (item.is_deleted) messageDao.delete(item.msg_id)
                        else messageDao.upsertOne(item.toEntity())
                    }
                }
                nextCursor = batch.items.last().updated_at ?: break
                if (batch.items.size < pageSize) break
            }
            session.setMessageSyncCursor(nextCursor)
        }
    }

    /**
     * Newest `updated_at` among the given responses. Timestamps are parsed to
     * [Instant] before comparing because ISO strings with differing fractional
     * precision do not compare correctly as raw text.
     */
    private fun List<MessageResponse>.latestUpdatedAt(): String? = this
        .mapNotNull { item ->
            item.updated_at?.let { ts ->
                runCatching { OffsetDateTime.parse(ts).toInstant() }.getOrNull()
            }
        }
        .maxOrNull()
        ?.toString()

    /**
     * Optimistically inserts the message locally (marked pending), enqueues the
     * create operation, and attempts to flush immediately when online. The
     * pending row is reconciled with the server's copy by [com.lovejournal.app.sync.SyncEngine].
     */
    suspend fun send(content: String, isPublic: Boolean): SendOutcome {
        val localRef = UUID.randomUUID().toString()
        val payload = json.encodeToString(MessageCreateRequest(content, isPublic))
        val uid = session.sessionFlow.first().uid
            ?: throw UiTextException(uiText(R.string.msg_session_expired))
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

    /**
     * 编辑留言（内容 / 公开可见性）。服务端按 exclude_unset 语义处理 PATCH，
     * 因此请求体只携带真正发生变化的字段（传 null 表示未修改）。
     * 成功后用服务器返回的副本刷新本地缓存。
     */
    suspend fun edit(
        msgId: String,
        newContent: String? = null,
        isPublic: Boolean? = null,
    ): Result<MessageResponse> {
        if (newContent == null && isPublic == null) {
            return Result.failure(UiTextException(uiText(R.string.messages_error_no_changes)))
        }
        val body = buildJsonObject {
            if (newContent != null) put("content", newContent)
            if (isPublic != null) put("is_public", isPublic)
        }
        return runCatching {
            val updated = api.patchMessage(msgId, body)
            messageDao.upsertOne(updated.toEntity())
            updated
        }
    }

    /**
     * 删除留言。服务端是软删除（进入回收站，可在后台恢复），
     * 成功后同步移除本地缓存；后续增量同步中的墓碑会兜底清理。
     */
    suspend fun remove(msgId: String): Result<Unit> = runCatching {
        val response = api.deleteMessage(msgId)
        if (!response.isSuccessful) throw HttpException(response)
        messageDao.delete(msgId)
    }

    /** 拉取留言的历史版本列表（新版本在前，由服务端排序）。 */
    suspend fun versions(msgId: String): Result<List<ContentVersion>> = runCatching {
        api.messageVersions(msgId).items
    }

    /** 将留言回滚到指定历史版本，并用服务器返回的副本刷新本地缓存。 */
    suspend fun rollback(msgId: String, version: Int): Result<MessageResponse> = runCatching {
        val restored = api.rollbackMessage(msgId, version)
        messageDao.upsertOne(restored.toEntity())
        restored
    }

    enum class SendOutcome { QUEUED_ONLINE, QUEUED_OFFLINE }
}
