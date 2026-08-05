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

package com.lovejournal.app.data.remote.dto

import kotlinx.serialization.Serializable

@Serializable
data class VaultMetaResponse(
    val initialized: Boolean = false,
    val salt: String? = null,
    val kdf: String? = null,
    val kdf_hash: String? = null,
    val iterations: Int? = null,
    val algo: String? = null,
    val verifier_iv: String? = null,
    val verifier_cipher: String? = null,
)

@Serializable
data class VaultSetupRequest(
    val salt: String,
    val kdf: String = "PBKDF2",
    val kdf_hash: String = "SHA-256",
    val iterations: Int = 210000,
    val algo: String = "AES-GCM",
    val verifier_iv: String,
    val verifier_cipher: String,
)

@Serializable
data class VaultEntryCreateRequest(val iv: String, val ciphertext: String)

@Serializable
data class VaultEntryUpdateRequest(val iv: String, val ciphertext: String)

@Serializable
data class VaultEntryResponse(
    val vid: String,
    val iv: String,
    val ciphertext: String,
    val author_uid: String? = null,
    val created_at: String? = null,
    val updated_at: String? = null,
)

@Serializable
data class VaultRekeyEntry(val vid: String, val iv: String, val ciphertext: String)

@Serializable
data class VaultRekeyRequest(
    val salt: String,
    val kdf: String = "PBKDF2",
    val kdf_hash: String = "SHA-256",
    val iterations: Int = 210000,
    val algo: String = "AES-GCM",
    val verifier_iv: String,
    val verifier_cipher: String,
    val entries: List<VaultRekeyEntry>,
)
