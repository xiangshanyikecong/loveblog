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

package com.lovejournal.app.data.crypto

import android.util.Base64
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.SecretKey
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec
import javax.inject.Inject
import javax.inject.Singleton

@Serializable
data class VaultPlainEntry(val title: String = "", val body: String = "")

data class VaultCipherText(val iv: String, val ciphertext: String)

@Singleton
class VaultCrypto @Inject constructor(private val json: Json) {
    private val random = SecureRandom()

    fun generateSalt(): String = encode(ByteArray(16).also(random::nextBytes))

    fun deriveKey(passphrase: String, salt: String, iterations: Int): SecretKey {
        val spec = PBEKeySpec(passphrase.toCharArray(), decode(salt), iterations, 256)
        val bytes = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
        spec.clearPassword()
        return SecretKeySpec(bytes, "AES")
    }

    fun createVerifier(key: SecretKey): VaultCipherText = encryptString(key, VERIFIER_TOKEN)

    fun verify(key: SecretKey, iv: String, ciphertext: String): Boolean =
        runCatching { decryptString(key, iv, ciphertext) == VERIFIER_TOKEN }.getOrDefault(false)

    fun encryptEntry(key: SecretKey, entry: VaultPlainEntry): VaultCipherText = encryptString(key, json.encodeToString(entry))

    fun decryptEntry(key: SecretKey, iv: String, ciphertext: String): VaultPlainEntry =
        json.decodeFromString(decryptString(key, iv, ciphertext))

    private fun encryptString(key: SecretKey, value: String): VaultCipherText {
        val iv = ByteArray(12).also(random::nextBytes)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(128, iv))
        return VaultCipherText(encode(iv), encode(cipher.doFinal(value.toByteArray(Charsets.UTF_8))))
    }

    private fun decryptString(key: SecretKey, iv: String, ciphertext: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, decode(iv)))
        return cipher.doFinal(decode(ciphertext)).toString(Charsets.UTF_8)
    }

    private fun encode(bytes: ByteArray): String = Base64.encodeToString(bytes, Base64.NO_WRAP)
    private fun decode(value: String): ByteArray = Base64.decode(value, Base64.DEFAULT)

    private companion object { const val VERIFIER_TOKEN = "cottage-vault::verify::v1" }
}
