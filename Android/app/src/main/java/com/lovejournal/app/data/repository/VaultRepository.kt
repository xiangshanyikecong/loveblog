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
import com.lovejournal.app.data.remote.dto.VaultEntryCreateRequest
import com.lovejournal.app.data.remote.dto.VaultEntryResponse
import com.lovejournal.app.data.remote.dto.VaultEntryUpdateRequest
import com.lovejournal.app.data.remote.dto.VaultMetaResponse
import com.lovejournal.app.data.remote.dto.VaultRekeyRequest
import com.lovejournal.app.data.remote.dto.VaultSetupRequest
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class VaultRepository @Inject constructor(private val api: LoveApiService) {
    suspend fun meta(): Result<VaultMetaResponse> = runCatching { api.vaultMeta() }
    suspend fun setup(body: VaultSetupRequest): Result<VaultMetaResponse> = runCatching { api.setupVault(body) }
    suspend fun entries(): Result<List<VaultEntryResponse>> = runCatching { api.vaultEntries() }
    suspend fun create(body: VaultEntryCreateRequest): Result<VaultEntryResponse> = runCatching { api.createVaultEntry(body) }
    suspend fun update(vid: String, body: VaultEntryUpdateRequest): Result<VaultEntryResponse> = runCatching { api.updateVaultEntry(vid, body) }
    suspend fun delete(vid: String): Result<Unit> = runCatching { api.deleteVaultEntry(vid); Unit }
    suspend fun rekey(body: VaultRekeyRequest): Result<VaultMetaResponse> = runCatching { api.rekeyVault(body) }
    suspend fun reset(): Result<Unit> = runCatching { api.resetVault(); Unit }
}
