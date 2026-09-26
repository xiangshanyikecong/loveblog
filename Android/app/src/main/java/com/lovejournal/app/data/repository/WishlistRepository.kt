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
import com.lovejournal.app.data.local.dao.SyncQueueDao
import com.lovejournal.app.data.local.entity.SyncQueueEntity
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.WishCreateRequest
import com.lovejournal.app.data.remote.dto.WishListResponse
import com.lovejournal.app.data.remote.dto.WishUpdateRequest
import com.lovejournal.app.sync.SyncActions
import kotlinx.coroutines.flow.first
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 小屋·心愿单。Shared list — either partner may add / complete / reopen / delete
 * any wish. Network-backed (mirrors Events/Articles repos); [createOfflineAware]
 * parks a failed create in the SyncQueue so SyncWorker replays it once the
 * device is back online.
 */
@Singleton
class WishlistRepository @Inject constructor(
    private val api: LoveApiService,
    private val db: LoveDatabase,
    private val syncQueueDao: SyncQueueDao,
    private val session: SessionManager,
    private val serverConfig: ServerConfig,
    private val json: Json,
) {
    /** @param status null = all, "pending" or "completed" to filter. */
    suspend fun list(status: String? = null): Result<WishListResponse> = runCatching {
        api.wishes(status)
    }

    suspend fun create(
        title: String,
        description: String?,
        category: String?,
        targetDate: String?,
        priority: Int,
    ): Result<Unit> = runCatching {
        api.createWish(
            body = WishCreateRequest(
                title = title,
                description = description,
                category = category,
                target_date = targetDate,
                priority = priority,
            ),
        )
        Unit
    }

    /**
     * 离线感知的心愿创建：先用一次性 UUID 幂等键尝试直连上报；一旦失败
     * （含离线），把请求原样序列化进 SyncQueue（action =
     * [SyncActions.WISH_CREATE]，localRef/idempotencyKey 均为该键），
     * SyncWorker 联网后用同一载荷补发。无论入队与否都返回
     * [Result.failure]，由 UI 依据连接状态决定展示「已离线暂存」还是
     * 原始错误。
     *
     * 无本地 Room 行需要对账 —— 服务端权威副本经正常刷新回流。
     */
    suspend fun createOfflineAware(
        title: String,
        description: String?,
        category: String?,
        targetDate: String?,
        priority: Int,
    ): Result<Unit> {
        val key = UUID.randomUUID().toString()
        val req = WishCreateRequest(
            title = title,
            description = description,
            category = category,
            target_date = targetDate,
            priority = priority,
        )
        return try {
            api.createWish(idempotencyKey = key, body = req)
            Result.success(Unit)
        } catch (e: Exception) {
            val uid = session.sessionFlow.first().uid
                ?: return Result.failure(IllegalStateException("登录状态已失效"))
            val scope = serverConfig.dataScope(uid)
            db.withTransaction {
                syncQueueDao.enqueue(
                    SyncQueueEntity(
                        action = SyncActions.WISH_CREATE,
                        payload = json.encodeToString(req),
                        localRef = key,
                        scope = scope,
                        idempotencyKey = key,
                    ),
                )
            }
            Result.failure(e)
        }
    }

    suspend fun update(
        wid: String,
        title: String,
        description: String?,
        category: String?,
    ): Result<Unit> = runCatching {
        api.updateWish(
            wid,
            WishUpdateRequest(title = title, description = description, category = category),
        )
        Unit
    }

    suspend fun complete(wid: String): Result<Unit> = runCatching { api.completeWish(wid); Unit }

    suspend fun reopen(wid: String): Result<Unit> = runCatching { api.reopenWish(wid); Unit }

    suspend fun delete(wid: String): Result<Unit> = runCatching {
        val response = api.deleteWish(wid)
        if (!response.isSuccessful) {
            throw IllegalStateException("删除失败 (${response.code()})")
        }
        Unit
    }
}
