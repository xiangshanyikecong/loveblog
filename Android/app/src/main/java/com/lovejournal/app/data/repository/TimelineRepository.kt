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

import androidx.paging.PagingSource
import androidx.paging.PagingState
import androidx.room.withTransaction
import com.lovejournal.app.R
import com.lovejournal.app.data.local.LoveDatabase
import com.lovejournal.app.data.local.dao.SyncQueueDao
import com.lovejournal.app.data.local.entity.SyncQueueEntity
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.CommentCreateRequest
import com.lovejournal.app.data.remote.dto.MomentCreateRequest
import com.lovejournal.app.data.remote.dto.MomentResponse
import com.lovejournal.app.data.remote.dto.TimelineListResponse
import com.lovejournal.app.sync.SyncActions
import com.lovejournal.app.ui.components.UiTextException
import com.lovejournal.app.ui.components.uiText
import kotlinx.coroutines.flow.first
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 主端·时间线。动态流（含评论树展示）。本期支持列表 / 发动态（图片先经
 * [UploadRepository.uploadTimelineImage] 上传，URL 随 [MomentCreateRequest.media_urls] 提交）/
 * 评论（支持通过 parent_cid 回复）/ 删除 / 往年今日回忆（只读）；语音上传仍需后续补。
 * [postOfflineAware] 在失败时把请求暂存进 SyncQueue，联网后由 SyncWorker 自动补发。
 */
@Singleton
class TimelineRepository @Inject constructor(
    private val api: LoveApiService,
    private val db: LoveDatabase,
    private val syncQueueDao: SyncQueueDao,
    private val session: SessionManager,
    private val serverConfig: ServerConfig,
    private val json: Json,
) {
    suspend fun list(page: Int = 1): Result<TimelineListResponse> =
        runCatching { api.timeline(page = page) }

    /**
     * 动态流的分页数据源：按服务端 `page` / `page_size`（上限 50）逐页加载，
     * 以 `has_next` 判断是否还有下一页。数据变更后调用 [PagingSource.invalidate]
     * 即可触发整列表重新加载。
     */
    fun pagingSource(): PagingSource<Int, MomentResponse> = TimelinePagingSource(api)

    companion object {
        /** 动态流每页条数（服务端 page_size 上限 50）。 */
        const val PAGE_SIZE = 20
    }

    /** 往年今日的动态（回忆视图数据源）。 */
    suspend fun memories(): Result<List<MomentResponse>> = runCatching { api.timelineMemories() }

    /**
     * 离线感知的发动态：先用一次性 UUID 幂等键尝试直连；一旦失败（含
     * 离线），把请求原样序列化进 SyncQueue（action =
     * [SyncActions.MOMENT_CREATE]，localRef/idempotencyKey 均为该键），
     * SyncWorker 联网后用同一载荷补发。无论入队与否都返回
     * [Result.failure]，由 UI 依据连接状态决定展示「已离线暂存」还是
     * 原始错误。
     *
     * 无本地 Room 行需要对账 —— 服务端权威副本经正常刷新回流。
     */
    suspend fun postOfflineAware(
        content: String,
        visibility: String,
        mediaUrls: List<String> = emptyList(),
    ): Result<Unit> {
        val key = UUID.randomUUID().toString()
        val req = MomentCreateRequest(content = content, media_urls = mediaUrls, visibility = visibility)
        return try {
            api.createMoment(idempotencyKey = key, body = req)
            Result.success(Unit)
        } catch (e: Exception) {
            val uid = session.sessionFlow.first().uid
                ?: return Result.failure(UiTextException(uiText(R.string.msg_session_expired)))
            val scope = serverConfig.dataScope(uid)
            db.withTransaction {
                syncQueueDao.enqueue(
                    SyncQueueEntity(
                        action = SyncActions.MOMENT_CREATE,
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

    /** 发表评论；[parentCid] 非空表示回复某条评论。 */
    suspend fun comment(mid: String, content: String, parentCid: String? = null): Result<Unit> = runCatching {
        api.commentMoment(mid, CommentCreateRequest(content = content, parent_cid = parentCid))
        Unit
    }

    suspend fun delete(mid: String): Result<Unit> = runCatching {
        val response = api.deleteMoment(mid)
        if (!response.isSuccessful) throw UiTextException(uiText(R.string.msg_delete_failed))
        Unit
    }

    private class TimelinePagingSource(
        private val api: LoveApiService,
    ) : PagingSource<Int, MomentResponse>() {

        override suspend fun load(params: LoadParams<Int>): LoadResult<Int, MomentResponse> {
            val page = params.key ?: 1
            return try {
                val response = api.timeline(page = page, pageSize = PAGE_SIZE)
                LoadResult.Page(
                    data = response.items,
                    // 首页无上一页；上一页索引正常递减（Paging 一般不会向前翻）。
                    prevKey = if (page <= 1) null else page - 1,
                    nextKey = if (response.has_next) page + 1 else null,
                )
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                LoadResult.Error(e)
            }
        }

        // 刷新（invalidate）后总是从第一页重新加载，保持「最新动态在最上」。
        override fun getRefreshKey(state: PagingState<Int, MomentResponse>): Int? = null
    }
}
