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

package com.lovejournal.app.data.chat

import com.lovejournal.app.data.crypto.ChatCrypto
import com.lovejournal.app.data.repository.ChatRepository
import okhttp3.OkHttpClient
import okhttp3.Request
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import java.io.IOException
import java.util.LinkedHashMap
import javax.inject.Inject
import javax.inject.Singleton

/**
 * E2EE 聊天媒体（图片等）解密管线，与 web 端 `enqueueMediaDecrypt` 对齐：
 *
 *   下载密文文件（.enc，需登录 cookie）→ AES-GCM 解密 → 明文字节交给 UI
 *   （Coil 从 ByteBuffer 加载，由内容魔数自行识别格式）。
 *
 * - 并发上限 [MAX_CONCURRENT]（与 web 相同的 3），避免打开长会话时一次性
 *   拉满几十条历史消息打爆内存/网络。
 * - 解密结果按 `mid@iv` 缓存在进程内存 LRU（预算 [MAX_CACHE_BYTES] /
 *   [MAX_CACHE_ENTRIES]），不落盘 —— 与「密钥仅进程内存、冷启动重新解锁」
 *   的既有安全姿态一致。
 */
@Singleton
class ChatMediaDecryptor @Inject constructor(
    private val chatRepository: ChatRepository,
    private val client: OkHttpClient,
) {
    private val cache = object : LinkedHashMap<String, ByteArray>(16, 0.75f, true) {}
    private var cacheBytes = 0L
    private val semaphore = Semaphore(MAX_CONCURRENT)

    /**
     * 解密一条加密媒体消息，返回明文原始字节。并发受限、结果缓存；
     * 未解锁 / 网络失败 / 密文损坏（口令不对或消息属于旧口令时代）时抛出
     * 异常，由调用方决定占位与重试。
     */
    suspend fun decryptBytes(mid: String, iv: String, url: String): ByteArray {
        val cacheKey = "$mid@$iv"
        synchronized(cache) { cache[cacheKey] }?.let { return it }
        val plain = semaphore.withPermit {
            withContext(Dispatchers.IO) {
                // 拿到并发名额后再查一次缓存：同一条消息可能已在前一批解完。
                synchronized(cache) { cache[cacheKey] }?.let { return@withContext it }
                val key = chatRepository.keySession.value?.key
                    ?: throw IOException("尚未解锁加密聊天")
                val cipher = client.newCall(Request.Builder().url(url).build()).execute().use { resp ->
                    if (!resp.isSuccessful) throw IOException("媒体下载失败（HTTP ${resp.code}）")
                    resp.body?.bytes() ?: throw IOException("媒体内容为空")
                }
                ChatCrypto.decryptBytes(key, iv, cipher)
            }
        }
        synchronized(cache) {
            cache[cacheKey] = plain
            cacheBytes += plain.size
            while (cacheBytes > MAX_CACHE_BYTES || cache.size > MAX_CACHE_ENTRIES) {
                val eldest = cache.entries.iterator()
                if (!eldest.hasNext()) break
                val entry = eldest.next()
                eldest.remove()
                cacheBytes -= entry.value.size
            }
        }
        return plain
    }

    /** 口令更换/重新解锁后清空缓存：旧解密结果不再代表当前可读状态。 */
    fun clear() = synchronized(cache) {
        cache.clear()
        cacheBytes = 0L
    }

    private companion object {
        const val MAX_CONCURRENT = 3
        const val MAX_CACHE_BYTES = 64L * 1024 * 1024
        const val MAX_CACHE_ENTRIES = 40
    }
}
