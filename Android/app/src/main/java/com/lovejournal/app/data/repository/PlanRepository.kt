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

import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.PlanChecklistItemDto
import com.lovejournal.app.data.remote.dto.PlanCreateRequest
import com.lovejournal.app.data.remote.dto.PlanListResponse
import com.lovejournal.app.data.remote.dto.PlanUpdateRequest
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 小屋·约会计划。共享计划清单：任一方可创建/编辑/完成/重开/删除；
 * status 取 planned / in_progress / done / cancelled。网络直连，与 Reminder 范式一致。
 */
@Singleton
class PlanRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun list(status: String? = null): Result<PlanListResponse> =
        runCatching { api.plans(status = status) }

    suspend fun create(
        title: String,
        description: String?,
        location: String?,
        planDate: String?,
        priority: Int,
        checklist: List<PlanChecklistItemDto> = emptyList(),
    ): Result<Unit> = runCatching {
        api.createPlan(
            PlanCreateRequest(
                title = title,
                description = description,
                location = location,
                plan_date = planDate,
                priority = priority,
                checklist = checklist,
            ),
        )
        Unit
    }

    suspend fun update(pid: String, body: PlanUpdateRequest): Result<Unit> =
        runCatching { api.updatePlan(pid, body); Unit }

    suspend fun complete(pid: String): Result<Unit> = runCatching { api.completePlan(pid); Unit }

    suspend fun reopen(pid: String): Result<Unit> = runCatching { api.reopenPlan(pid); Unit }

    suspend fun delete(pid: String): Result<Unit> = runCatching {
        val response = api.deletePlan(pid)
        if (!response.isSuccessful) throw IllegalStateException("删除失败 (${response.code()})")
        Unit
    }
}
