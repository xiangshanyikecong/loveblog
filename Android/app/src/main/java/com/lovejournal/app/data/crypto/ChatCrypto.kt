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

import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.SecretKey
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

/**
 * 端到端加密聊天（E2EE）客户端加密原语，与网页端 `web/src/lib/chatCrypto.js`
 * / `vaultCrypto.js` 完全互通：
 *
 *   passphrase ──PBKDF2(SHA-256, salt, iterations)──▶ AES-GCM-256 密钥
 *   明文       ──AES-GCM(key, random 12B iv)──────▶ { iv, ciphertext }
 *
 * 两端编解码全部使用标准 base64；WebCrypto 的 GCM 默认 tag 长度 128 bit，
 * 与 JVM `AES/GCM/NoPadding` 默认一致，无需额外参数。派生密钥仅保存在
 * 进程内存（[ChatKeySession]），任何落库/落盘内容都只有服务端可见的
 * 公开 KDF 参数与密文。
 */
object ChatCrypto {

    const val VERIFIER_TOKEN = "cottage-chat::verify::v1"
    const val DEFAULT_ITERATIONS = 210_000
    const val DEFAULT_KDF = "PBKDF2"
    const val DEFAULT_KDF_HASH = "SHA-256"
    const val DEFAULT_ALGO = "AES-GCM"

    /** 与 web `encryptString` 相同的信封：iv / ciphertext 均为标准 base64。 */
    data class Envelope(val iv: String, val ciphertext: String)

    /** 一次已解锁的聊天密钥会话：仅持有内存中的派生密钥与公开参数。 */
    class ChatKeySession(
        val key: SecretKey,
        val salt: String,
        val iterations: Int,
        val kdf: String,
        val kdfHash: String,
        val algo: String,
    )

    private val random = SecureRandom()

    fun generateSalt(): String = base64Encode(ByteArray(16).also { random.nextBytes(it) })

    fun deriveKey(passphrase: CharArray, saltB64: String, iterations: Int = DEFAULT_ITERATIONS): SecretKey {
        val factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
        val spec = PBEKeySpec(passphrase, base64Decode(saltB64), iterations, 256)
        val keyBytes = factory.generateSecret(spec).encoded
        spec.clearPassword()
        return SecretKeySpec(keyBytes, "AES")
    }

    fun encryptString(key: SecretKey, plaintext: String): Envelope {
        val iv = ByteArray(12).also { random.nextBytes(it) }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(128, iv))
        val encrypted = cipher.doFinal(plaintext.toByteArray(Charsets.UTF_8))
        return Envelope(iv = base64Encode(iv), ciphertext = base64Encode(encrypted))
    }

    /** 解密失败（口令错误 / 密文损坏）时抛出异常，由调用方决定如何提示。 */
    fun decryptString(key: SecretKey, ivB64: String, ciphertextB64: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, base64Decode(ivB64)))
        val plain = cipher.doFinal(base64Decode(ciphertextB64))
        return String(plain, Charsets.UTF_8)
    }

    fun encryptBytes(key: SecretKey, plaintext: ByteArray): Envelope {
        val iv = ByteArray(12).also { random.nextBytes(it) }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(128, iv))
        val encrypted = cipher.doFinal(plaintext)
        return Envelope(iv = base64Encode(iv), ciphertext = base64Encode(encrypted))
    }

    fun decryptBytes(key: SecretKey, ivB64: String, ciphertext: ByteArray): ByteArray {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, base64Decode(ivB64)))
        return cipher.doFinal(ciphertext)
    }

    /** 服务端 setup 载荷里的 verifier_hash：对密文 base64 字符串求 SHA-256 hex。 */
    fun sha256Hex(text: String): String =
        MessageDigest.getInstance("SHA-256")
            .digest(text.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }

    /** 校验口令是否正确：能否解出 verifier 里的已知常量。 */
    fun verifyPassphrase(passphrase: CharArray, salt: String, iterations: Int, verifierIv: String, verifierCipher: String): Boolean =
        runCatching {
            val key = deriveKey(passphrase, salt, iterations)
            decryptString(key, verifierIv, verifierCipher) == VERIFIER_TOKEN
        }.getOrDefault(false)

    // 用 java.util.Base64（minSdk 26 起可用）而非 android.util.Base64：
    // 与 web 端 btoa/atob 的标准字母表一致，且纯 JVM 单测可直接运行。
    private fun base64Encode(bytes: ByteArray): String =
        java.util.Base64.getEncoder().encodeToString(bytes)

    private fun base64Decode(text: String): ByteArray =
        java.util.Base64.getDecoder().decode(text)
}
