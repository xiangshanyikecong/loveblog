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
import com.lovejournal.app.data.remote.dto.CheckInCreateRequest
import com.lovejournal.app.data.remote.dto.CheckInListResponse
import com.lovejournal.app.data.remote.dto.CheckInResponse
import com.lovejournal.app.sync.SyncActions
import kotlinx.coroutines.flow.first
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 主端·报备签到。创建（文字 + 照片 + 可选位置）与查看 TA 的最新/历史报备。
 * 后端在读取端强制「author_id != 本人」，因此 latest/list 永远只返回对方的报备。
 * 网络直连，与其余 REST 模块范式一致；[createOfflineAware] 在失败时把请求
 * 暂存进 SyncQueue，联网后由 SyncWorker 自动补发。
 */
@Singleton
class CheckinRepository @Inject constructor(
    private val api: LoveApiService,
    private val db: LoveDatabase,
    private val syncQueueDao: SyncQueueDao,
    private val session: SessionManager,
    private val serverConfig: ServerConfig,
    private val json: Json,
) {
    suspend fun latest(): Result<CheckInResponse?> =
        runCatching { api.checkinLatest().item }

    suspend fun list(page: Int = 1, pageSize: Int = 20): Result<CheckInListResponse> =
        runCatching { api.checkins(page = page, pageSize = pageSize) }

    suspend fun create(
        content: String?,
        mediaUrls: List<String>,
        latitude: Double?,
        longitude: Double?,
        locationPermissionDenied: Boolean,
    ): Result<Unit> = runCatching {
        api.createCheckin(
            body = CheckInCreateRequest(
                content = content,
                media_urls = mediaUrls,
                latitude = latitude,
                longitude = longitude,
                location_permission_denied = locationPermissionDenied,
            ),
        )
        Unit
    }

    /**
     * 离线感知的报备创建：先用一次性 UUID 幂等键尝试直连上报；一旦失败
     * （含离线），把请求原样序列化进 SyncQueue（action =
     * [SyncActions.CHECKIN_CREATE]，localRef/idempotencyKey 均为该键），
     * SyncWorker 联网后用同一载荷补发。无论入队与否都返回
     * [Result.failure]，由 UI 依据连接状态决定展示「已离线暂存」还是
     * 原始错误。
     *
     * 无本地 Room 行需要对账 —— 服务端权威副本经正常刷新回流
     * （且读取端「自己看不到自己」，补发成功后本地也不会出现重复行）。
     */
    suspend fun createOfflineAware(
        content: String?,
        mediaUrls: List<String>,
        latitude: Double?,
        longitude: Double?,
        locationPermissionDenied: Boolean,
    ): Result<Unit> {
        val key = UUID.randomUUID().toString()
        val req = CheckInCreateRequest(
            content = content,
            media_urls = mediaUrls,
            latitude = latitude,
            longitude = longitude,
            location_permission_denied = locationPermissionDenied,
        )
        return try {
            api.createCheckin(idempotencyKey = key, body = req)
            Result.success(Unit)
        } catch (e: Exception) {
            val uid = session.sessionFlow.first().uid
                ?: return Result.failure(IllegalStateException("登录状态已失效"))
            val scope = serverConfig.dataScope(uid)
            db.withTransaction {
                syncQueueDao.enqueue(
                    SyncQueueEntity(
                        action = SyncActions.CHECKIN_CREATE,
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
}
