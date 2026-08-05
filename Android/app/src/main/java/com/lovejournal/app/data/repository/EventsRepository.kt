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
import com.lovejournal.app.data.remote.dto.EventCreateRequest
import com.lovejournal.app.data.remote.dto.EventResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class EventsRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun list(): Result<List<EventResponse>> = runCatching {
        api.events().items
    }

    suspend fun create(request: EventCreateRequest): Result<Unit> = runCatching {
        api.createEvent(request)
        Unit
    }

    suspend fun update(eid: String, request: EventCreateRequest): Result<Unit> = runCatching {
        api.updateEvent(eid, request)
        Unit
    }

    suspend fun delete(eid: String): Result<Unit> = runCatching {
        val response = api.deleteEvent(eid)
        if (!response.isSuccessful) {
            throw IllegalStateException("删除失败 (${response.code()})")
        }
        Unit
    }
}
