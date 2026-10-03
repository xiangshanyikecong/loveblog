/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

package com.lovejournal.app.sync

import androidx.room.withTransaction
import com.lovejournal.app.data.local.LoveDatabase
import com.lovejournal.app.data.local.dao.MessageDao
import com.lovejournal.app.data.local.dao.MoodDao
import com.lovejournal.app.data.local.dao.SyncQueueDao
import com.lovejournal.app.data.local.entity.SyncQueueEntity
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.dto.ChatSendRequest
import com.lovejournal.app.data.remote.dto.CheckInCreateRequest
import com.lovejournal.app.data.remote.dto.MessageCreateRequest
import com.lovejournal.app.data.remote.dto.MoodCheckinRequest
import com.lovejournal.app.data.remote.dto.MomentCreateRequest
import com.lovejournal.app.data.remote.dto.WishCreateRequest
import com.lovejournal.app.data.repository.toEntity
import kotlinx.serialization.json.Json
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Drains the offline mutation queue, replaying each operation against the
 * backend and reconciling the optimistic local rows with the server response.
 *
 * Failures are classified by [SyncRetryPolicy]: temporary failures (network /
 * 5xx) are re-queued with exponential backoff; permanent failures (4xx,
 * payload drift) and exhausted retries become dead letters that are kept for
 * diagnostics but never replayed. Other entries continue so a malformed
 * operation cannot wedge the queue. A process crash after a request is safe
 * because each operation carries a stable backend Idempotency-Key.
 *
 * Returns true when no retryable work is left waiting (dead letters do not
 * block the result — they are terminal by definition).
 */
@Singleton
class SyncEngine @Inject constructor(
    private val api: LoveApiService,
    private val db: LoveDatabase,
    private val syncQueueDao: SyncQueueDao,
    private val messageDao: MessageDao,
    private val moodDao: MoodDao,
    private val session: SessionManager,
    private val serverConfig: ServerConfig,
    private val json: Json,
) {
    suspend fun flush(): Boolean = flushMutex.withLock {
        val sessionState = session.sessionFlow.first()
        val uid = sessionState.uid
        if (!sessionState.loggedIn || uid == null) return@withLock true

        val now = System.currentTimeMillis()
        val pending = syncQueueDao.due(serverConfig.dataScope(uid), now)
        var allOk = true
        for (item in pending) {
            try {
                when (item.action) {
                    SyncActions.MESSAGE_CREATE -> {
                        val req = json.decodeFromString<MessageCreateRequest>(item.payload)
                        val created = api.createMessage(item.idempotencyKey, req)
                        db.withTransaction {
                            messageDao.delete("local:${item.localRef}")
                            messageDao.upsertOne(created.toEntity())
                            syncQueueDao.remove(item.id)
                        }
                    }
                    SyncActions.MOOD_UPSERT -> {
                        val req = json.decodeFromString<MoodCheckinRequest>(item.payload)
                        val saved = api.upsertMood(item.idempotencyKey, req)
                        db.withTransaction {
                            // Drop the optimistic local row so it isn't duplicated
                            // alongside the authoritative server copy.
                            moodDao.delete("local:${item.localRef}")
                            moodDao.upsert(listOf(saved.toEntity()))
                            syncQueueDao.remove(item.id)
                        }
                    }
                    SyncActions.CHAT_SEND -> {
                        // No local row to reconcile — the WS push (or the next
                        // history fetch) will deliver the server copy. We just
                        // need to forward the request with the original key.
                        val req = json.decodeFromString<ChatSendRequest>(item.payload)
                        api.sendChatMessage(
                            idempotencyKey = item.idempotencyKey,
                            body = req,
                        )
                        syncQueueDao.remove(item.id)
                    }
                    SyncActions.MOMENT_CREATE -> {
                        val req = json.decodeFromString<MomentCreateRequest>(item.payload)
                        api.createMoment(
                            idempotencyKey = item.idempotencyKey,
                            body = req,
                        )
                        syncQueueDao.remove(item.id)
                    }
                    SyncActions.CHECKIN_CREATE -> {
                        // No local Room row to reconcile — the server copy
                        // arrives via the normal refresh cycle.
                        val req = json.decodeFromString<CheckInCreateRequest>(item.payload)
                        api.createCheckin(
                            idempotencyKey = item.idempotencyKey,
                            body = req,
                        )
                        syncQueueDao.remove(item.id)
                    }
                    SyncActions.WISH_CREATE -> {
                        // Same as CHECKIN_CREATE: no local row to reconcile,
                        // the authoritative wish comes back with the next
                        // refresh.
                        val req = json.decodeFromString<WishCreateRequest>(item.payload)
                        api.createWish(
                            idempotencyKey = item.idempotencyKey,
                            body = req,
                        )
                        syncQueueDao.remove(item.id)
                    }
                    else -> throw IllegalStateException("Unknown sync action: ${item.action}")
                }
            } catch (e: Exception) {
                rethrowIfSyncCancelled(e)
                allOk = false
                // Never silently discard a user mutation, but also never let
                // one poisoned entry replay forever: temporary failures back
                // off, permanent ones (and exhausted retries) go dead-letter.
                handleFailure(item, e)
            }
        }
        allOk
    }

    private suspend fun handleFailure(item: SyncQueueEntity, error: Exception) {
        when (val decision = SyncRetryPolicy.classify(error)) {
            is SyncFailure.Retryable -> {
                val attempts = item.retryCount + 1
                if (attempts >= SyncRetryPolicy.MAX_ATTEMPTS) {
                    syncQueueDao.markDead(
                        item.id,
                        "exhausted after $attempts attempts: ${decision.reason}",
                    )
                } else {
                    syncQueueDao.markFailure(
                        item.id,
                        decision.reason,
                        System.currentTimeMillis() + SyncRetryPolicy.backoffMillis(attempts),
                    )
                }
            }
            is SyncFailure.Permanent ->
                syncQueueDao.markDead(item.id, decision.reason)
        }
    }

    private companion object {
        val flushMutex = Mutex()
    }
}

internal fun rethrowIfSyncCancelled(error: Exception) {
    if (error is CancellationException) throw error
}
