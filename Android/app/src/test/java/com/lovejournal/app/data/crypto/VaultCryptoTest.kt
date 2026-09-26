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

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 保险箱端到端加密原语单测（纯 JVM：PBKDF2 + AES-GCM + java.util.Base64）。
 * 这里的任何回归都意味着用户私密内容无法解密或可被伪造，必须零容忍。
 */
class VaultCryptoTest {

    private val crypto = VaultCrypto(Json { ignoreUnknownKeys = true })

    private fun key(passphrase: String, salt: String) = crypto.deriveKey(passphrase, salt, ITERATIONS)

    @Test
    fun `entry roundtrip preserves title and body`() {
        val salt = crypto.generateSalt()
        val key = key("正确的口令", salt)
        val entry = VaultPlainEntry(title = "银行账号", body = "含「特殊字符」\n换行 emoji 🔒")
        val cipher = crypto.encryptEntry(key, entry)

        val decrypted = crypto.decryptEntry(key, cipher.iv, cipher.ciphertext)
        assertEquals(entry, decrypted)
    }

    @Test
    fun `wrong passphrase cannot verify`() {
        val salt = crypto.generateSalt()
        val verifier = crypto.createVerifier(key("正确口令", salt))

        val wrongKey = key("错误口令", salt)
        assertFalse(crypto.verify(wrongKey, verifier.iv, verifier.ciphertext))
    }

    @Test
    fun `wrong passphrase cannot decrypt entry`() {
        val salt = crypto.generateSalt()
        val key = key("正确口令", salt)
        val cipher = crypto.encryptEntry(key, VaultPlainEntry(title = "t", body = "秘密"))

        val wrongKey = key("另一个口令", salt)
        try {
            crypto.decryptEntry(wrongKey, cipher.iv, cipher.ciphertext)
            throw AssertionError("AES-GCM 应当因认证标签校验失败而抛异常")
        } catch (expected: Exception) {
            // GCM TagMismatch —— 期望路径
        }
    }

    @Test
    fun `verifier roundtrip succeeds with matching key`() {
        val salt = crypto.generateSalt()
        val key = key("口令", salt)
        val verifier = crypto.createVerifier(key)
        assertTrue(crypto.verify(key, verifier.iv, verifier.ciphertext))
    }

    @Test
    fun `same passphrase with different salts yields different keys`() {
        val salt1 = crypto.generateSalt()
        val salt2 = crypto.generateSalt()
        val verifier1 = crypto.createVerifier(key("同一口令", salt1))
        assertNotEquals(salt1, salt2)
        assertFalse(crypto.verify(key("同一口令", salt2), verifier1.iv, verifier1.ciphertext))
    }

    @Test
    fun `encryption is non-deterministic - fresh IV per call`() {
        val salt = crypto.generateSalt()
        val key = key("口令", salt)
        val entry = VaultPlainEntry(title = "t", body = "b")
        val first = crypto.encryptEntry(key, entry)
        val second = crypto.encryptEntry(key, entry)
        assertNotEquals(first.iv, second.iv)
        assertNotEquals(first.ciphertext, second.ciphertext)
        // 两个密文都能解回原文
        assertEquals(entry, crypto.decryptEntry(key, first.iv, first.ciphertext))
        assertEquals(entry, crypto.decryptEntry(key, second.iv, second.ciphertext))
    }

    @Test
    fun `tampered ciphertext is rejected`() {
        val salt = crypto.generateSalt()
        val key = key("口令", salt)
        val cipher = crypto.encryptEntry(key, VaultPlainEntry(title = "t", body = "b"))

        val bytes = java.util.Base64.getDecoder().decode(cipher.ciphertext)
        bytes[bytes.size - 1] = (bytes[bytes.size - 1].toInt() xor 0x01).toByte()
        val tampered = java.util.Base64.getEncoder().encodeToString(bytes)

        try {
            crypto.decryptEntry(key, cipher.iv, tampered)
            throw AssertionError("篡改后的密文必须被 GCM 认证标签拒绝")
        } catch (expected: Exception) {
            // 期望路径
        }
    }

    @Test
    fun `salt is 16 bytes base64`() {
        val decoded = java.util.Base64.getDecoder().decode(crypto.generateSalt())
        assertEquals(16, decoded.size)
    }

    private companion object {
        // 测试里用较低的迭代次数避免拖慢单测；生产路径由仓库层决定。
        const val ITERATIONS = 20_000
    }
}
