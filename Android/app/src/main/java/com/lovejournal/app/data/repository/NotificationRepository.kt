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
import com.lovejournal.app.data.remote.dto.NotificationListResponse
import javax.inject.Inject
import javax.inject.Singleton

/** 主端·通知中心。列表 + 标记单条/全部已读。网络直连。 */
@Singleton
class NotificationRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun list(unreadOnly: Boolean = false): Result<NotificationListResponse> =
        runCatching { api.notifications(unreadOnly = unreadOnly) }

    suspend fun markRead(nid: String): Result<Unit> = runCatching { api.markNotificationRead(nid); Unit }

    suspend fun markAllRead(): Result<Unit> = runCatching { api.markAllNotificationsRead(); Unit }
}
