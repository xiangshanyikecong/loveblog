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

import com.lovejournal.app.data.local.dao.EventDao
import com.lovejournal.app.data.local.entity.EventEntity
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.DashboardResponse
import com.lovejournal.app.widget.LoveDaysWidget
import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class DashboardRepository @Inject constructor(
    private val api: LoveApiService,
    private val eventDao: EventDao,
    private val session: SessionManager,
    @ApplicationContext private val context: Context,
) {
    fun observeEvents(): Flow<List<EventEntity>> = eventDao.observeAll()

    suspend fun refresh(): Result<DashboardResponse> = runCatching {
        val data = api.dashboard()
        eventDao.clear()
        eventDao.upsert(data.recent_events.map { it.toEntity() })
        // Cache the love-days count so the home-screen widget can render offline.
        session.setLoveDays(data.love_clock.days)
        LoveDaysWidget.requestUpdate(context)
        data
    }
}
