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
import kotlinx.serialization.json.JsonElement
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AdminRepository @Inject constructor(private val api: LoveApiService) {
    suspend fun health(): Result<JsonElement> = runCatching { api.systemHealth() }
    suspend fun auditLogs(): Result<JsonElement> = runCatching { api.auditLogs() }
    suspend fun users(): Result<JsonElement> = runCatching { api.securityUsers() }
    suspend fun storage(): Result<JsonElement> = runCatching { api.storageStats() }
    suspend fun backupInfo(): Result<Pair<JsonElement, JsonElement>> = runCatching { api.exportSchedule() to api.exportHistory() }
    suspend fun runBackup(): Result<JsonElement> = runCatching { api.runAutoExport() }
}
