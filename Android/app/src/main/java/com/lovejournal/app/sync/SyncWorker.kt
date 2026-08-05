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

package com.lovejournal.app.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.lovejournal.app.data.repository.DashboardRepository
import com.lovejournal.app.data.repository.MessageRepository
import com.lovejournal.app.data.repository.MoodRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val syncEngine: SyncEngine,
    private val messageRepository: MessageRepository,
    private val moodRepository: MoodRepository,
    private val dashboardRepository: DashboardRepository,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        // 1. Push any queued offline mutations.
        val flushed = syncEngine.flush()
        // 2. Pull fresh server state so caches stay warm.
        messageRepository.refresh()
        moodRepository.refreshToday()
        dashboardRepository.refresh()
        // Retry later if the queue could not be fully drained (e.g. transient network).
        return if (flushed) Result.success() else Result.retry()
    }
}
