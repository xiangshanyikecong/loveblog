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

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 端到端加密聊天原语单测（纯 JVM，与 [VaultCryptoTest] 同级别零容忍）。
 *
 * 「web 互通已知答案」用例的向量由服务端仓库同款算法
 * （PBKDF2-HMAC-SHA256 + AES-GCM-256，等价 WebCrypto 默认参数）离线生成，
 * 锁定与网页端 chatCrypto.js 的互操作性：任何一侧改动参数/编码都会在这里失败。
 */
class ChatCryptoTest {

    private fun key(passphrase: String, salt: String = KAT_SALT) =
        ChatCrypto.deriveKey(passphrase.toCharArray(), salt, ChatCrypto.DEFAULT_ITERATIONS)

    @Test
    fun `string roundtrip preserves chinese emoji and newline`() {
        val key = key("正确的口令")
        val plaintext = "含「特殊字符」\n换行 emoji ❤️🔥"
        val envelope = ChatCrypto.encryptString(key, plaintext)
        assertEquals(plaintext, ChatCrypto.decryptString(key, envelope.iv, envelope.ciphertext))
    }

    @Test
    fun `web interop known answer vector decrypts`() {
        val key = key("恋爱记-test-❤️")
        val plaintext = ChatCrypto.decryptString(key, KAT_IV, KAT_CIPHERTEXT)
        assertEquals("你好，悄悄话 ❤️", plaintext)
    }

    @Test
    fun `web interop known answer vector encrypts to matching envelope`() {
        // 固定 salt + 固定 iv 下，加密结果必须逐字节等于 web 端算法输出。
        val key = key("恋爱记-test-❤️")
        val iv = java.util.Base64.getDecoder().decode(KAT_IV)
        val cipher = javax.crypto.Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(javax.crypto.Cipher.ENCRYPT_MODE, key, javax.crypto.spec.GCMParameterSpec(128, iv))
        val encrypted = cipher.doFinal("你好，悄悄话 ❤️".toByteArray(Charsets.UTF_8))
        assertEquals(KAT_CIPHERTEXT, java.util.Base64.getEncoder().encodeToString(encrypted))
    }

    @Test
    fun `verifier accepts correct passphrase and rejects wrong one`() {
        val salt = ChatCrypto.generateSalt()
        val verifier = ChatCrypto.encryptString(key("共享口令", salt), ChatCrypto.VERIFIER_TOKEN)

        assertTrue(
            ChatCrypto.verifyPassphrase(
                "共享口令".toCharArray(), salt, ChatCrypto.DEFAULT_ITERATIONS,
                verifier.iv, verifier.ciphertext,
            ),
        )
        assertFalse(
            ChatCrypto.verifyPassphrase(
                "错误口令".toCharArray(), salt, ChatCrypto.DEFAULT_ITERATIONS,
                verifier.iv, verifier.ciphertext,
            ),
        )
    }

    @Test
    fun `verifier hash matches sha256 of ciphertext base64`() {
        // 服务端 /chat/keys/setup 会校验 verifier_hash == sha256(verifier_cipher)，
        // 不一致直接 400，所以这里锁死哈希算法与输入（密文 base64 字符串本身）。
        assertEquals(
            "11bb4439c5094c93d794bc29f4abc0ad24323a412f4b69cc6e188d596e593fa4",
            ChatCrypto.sha256Hex(KAT_CIPHERTEXT),
        )
    }

    @Test
    fun `tampered ciphertext cannot decrypt`() {
        val key = key("口令")
        val envelope = ChatCrypto.encryptString(key, "机密内容")
        val tampered = envelope.ciphertext.toCharArray().also { it[0] = if (it[0] == 'A') 'B' else 'A' }
        val thrown = runCatching {
            ChatCrypto.decryptString(key, envelope.iv, String(tampered))
        }
        assertTrue(thrown.isFailure)
    }

    @Test
    fun `bytes roundtrip works for media payloads`() {
        val key = key("口令")
        val data = ByteArray(4096) { (it % 251).toByte() }
        val envelope = ChatCrypto.encryptBytes(key, data)
        assertEquals(data.toList(), ChatCrypto.decryptBytes(key, envelope.iv, java.util.Base64.getDecoder().decode(envelope.ciphertext)).toList())
    }

    @Test
    fun `web media interop known answer vector decrypts raw bytes`() {
        // E2EE 媒体（图片）互通向量：由 Node WebCrypto 以 web chatCrypto.js
        // encryptChatRaw 的完整参数离线生成（PBKDF2-SHA-256 210k 派生 + 整文件
        // AES-GCM），明文含 JPEG 魔数与 UTF-8 中文，锁定跨端字节级一致性。
        val key = key(MEDIA_KAT_PASSPHRASE, MEDIA_KAT_SALT)
        val plain = ChatCrypto.decryptBytes(
            key,
            MEDIA_KAT_IV,
            java.util.Base64.getDecoder().decode(MEDIA_KAT_CIPHERTEXT),
        )
        assertEquals(MEDIA_KAT_PLAIN.toList(), plain.toList())
    }

    @Test
    fun `raw media envelope roundtrip matches web encryptChatRaw contract`() {
        // encryptBytesRaw（密文文件直传用的原语）必须与 web encryptChatRaw
        // 返回同一形态：iv 为 base64，密文为原始字节（含 16B GCM tag）。
        val key = key(MEDIA_KAT_PASSPHRASE, MEDIA_KAT_SALT)
        val envelope = ChatCrypto.encryptBytesRaw(key, MEDIA_KAT_PLAIN)
        assertEquals(12, java.util.Base64.getDecoder().decode(envelope.iv).size)
        assertEquals(
            MEDIA_KAT_PLAIN.size + 16,
            envelope.ciphertextBytes.size,
        )
        assertEquals(
            MEDIA_KAT_PLAIN.toList(),
            ChatCrypto.decryptBytes(key, envelope.iv, envelope.ciphertextBytes).toList(),
        )
    }

    private companion object {
        // 由 Python cryptography（与 WebCrypto 等价参数）离线生成的固定向量。
        const val KAT_SALT = "AAECAwQFBgcICQoLDA0ODw=="
        const val KAT_IV = "AAECAwQFBgcICQoL"
        const val KAT_CIPHERTEXT = "sAE2xhkEeFbhunxtWd/IpnEjMx0yfSUDJu35jJVl24hWTQatYRJ/6xg="

        // 由 Node WebCrypto（web encryptChatRaw 同参数）生成的媒体互通向量。
        const val MEDIA_KAT_PASSPHRASE = "interop-passphrase-互通测试-💜"
        const val MEDIA_KAT_SALT = "vICBxiLZPFD8fqb5WUE1uw=="
        const val MEDIA_KAT_IV = "h269VbdTCG/3qYqq"
        const val MEDIA_KAT_CIPHERTEXT =
            "KdCD84vLc6vg+EmGZOGzKTBb1eSaM5m5gugKjgKCbgiQPmt57CdHMWS//pAjYCfFMpzlUaDRbN6T2Vm2DsC3QCA1FYSFuc94hV8="
        val MEDIA_KAT_PLAIN: ByteArray = byteArrayOf(
            0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE0.toByte(), 0x00, 0x10,
            0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        ) + "love-journal e2ee media interop 互通向量".toByteArray(Charsets.UTF_8) +
            byteArrayOf(0xFF.toByte(), 0xD9.toByte())
    }
}
