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

import androidx.room.withTransaction
import com.lovejournal.app.R
import com.lovejournal.app.data.ConnectivityMonitor
import com.lovejournal.app.data.crypto.ChatCrypto
import com.lovejournal.app.data.local.LoveDatabase
import com.lovejournal.app.data.local.dao.SyncQueueDao
import com.lovejournal.app.data.local.entity.SyncQueueEntity
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.CottageWebSocket
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.ChatHistoryResponse
import com.lovejournal.app.data.remote.dto.ChatKeyMetaResponse
import com.lovejournal.app.data.remote.dto.ChatKeySetupRequest
import com.lovejournal.app.data.remote.dto.ChatKeyRekeyRequest
import com.lovejournal.app.data.remote.dto.ChatKeyVerifyRequest
import com.lovejournal.app.data.remote.dto.ChatMessageResponse
import com.lovejournal.app.data.remote.dto.ChatSendRequest
import com.lovejournal.app.data.remote.dto.ChatStateResponse
import com.lovejournal.app.data.remote.dto.ChatMediaPanelResponse
import com.lovejournal.app.data.remote.dto.ChatMemoryCardResponse
import com.lovejournal.app.data.remote.dto.ChatPinnedQuoteRequest
import com.lovejournal.app.data.remote.dto.ChatPinnedQuoteResponse
import com.lovejournal.app.data.remote.dto.ChatKeywordsResponse
import com.lovejournal.app.data.remote.dto.ChatSearchResponse
import com.lovejournal.app.data.remote.dto.PokeRequest
import com.lovejournal.app.sync.SyncActions
import com.lovejournal.app.sync.SyncScheduler
import com.lovejournal.app.ui.components.UiTextException
import com.lovejournal.app.ui.components.uiText
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.mapNotNull
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.OkHttpClient
import java.time.Instant
import java.util.UUID
import javax.crypto.SecretKey
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

/** Strongly-typed cottage-chat realtime events parsed from the WS push channel. */
sealed interface ChatWsEvent {
    data class Message(val message: ChatMessageResponse) : ChatWsEvent
    data class Presence(val uid: String, val online: Boolean) : ChatWsEvent
    data class PresenceSnapshot(val onlineUids: List<String>) : ChatWsEvent
    data class Typing(val nickname: String, val isTyping: Boolean) : ChatWsEvent
    data class Poke(val fromNickname: String, val label: String) : ChatWsEvent
    data object Read : ChatWsEvent
}

@Singleton
class ChatRepository @Inject constructor(
    private val api: LoveApiService,
    @Named("ws") wsClient: OkHttpClient,
    serverConfig: ServerConfig,
    private val json: Json,
    private val db: LoveDatabase,
    private val syncQueueDao: SyncQueueDao,
    private val session: SessionManager,
    private val serverConfigScope: ServerConfig,
    private val connectivity: ConnectivityMonitor,
) {
    private val socket = CottageWebSocket(wsClient, serverConfig, json, "/cottage/chat/ws")

    val events: Flow<ChatWsEvent> = socket.events.mapNotNull(::parseEvent)
    val connected: SharedFlow<Boolean> = socket.connected

    fun connect() = socket.connect()
    fun disconnect() = socket.close()

    // ---- E2EE 密钥会话（仅进程内存，与 web 端「冷启动需重新解锁」策略一致）----

    private val _keySession = MutableStateFlow<ChatCrypto.ChatKeySession?>(null)
    val keySession: StateFlow<ChatCrypto.ChatKeySession?> = _keySession.asStateFlow()

    val isUnlocked: Boolean get() = _keySession.value != null

    /** 服务端是否已初始化共享密钥（设置过口令）。 */
    var e2eeInitialized: Boolean = false
        private set

    /**
     * 解密结果缓存（mid@iv → 明文）。历史列表每次刷新都会全量重发，
     * 缓存保证每条密文只做一次 AES-GCM 解密，避免长会话中随消息数
     * 线性增长的重复解密开销。未解锁前密文不解，与 web 行为一致。
     */
    private val plaintextCache = java.util.concurrent.ConcurrentHashMap<String, String>()

    fun encryptText(plaintext: String): ChatCrypto.Envelope? =
        _keySession.value?.key?.let { ChatCrypto.encryptString(it, plaintext) }

    /** 解密一条 E2EE 消息；未解锁或密文损坏时返回 null（UI 显示占位）。 */
    fun decryptMessage(message: ChatMessageResponse): ChatMessageResponse {
        if (!message.is_encrypted || message.iv == null || message.ciphertext == null) return message
        val cacheKey = "${message.mid}@${message.iv}"
        plaintextCache[cacheKey]?.let { return message.copy(content = it) }
        val key = _keySession.value?.key ?: return message
        val plain = runCatching { ChatCrypto.decryptString(key, message.iv, message.ciphertext) }.getOrNull()
            ?: return message
        plaintextCache[cacheKey] = plain
        return message.copy(content = plain)
    }

    fun decryptAll(messages: List<ChatMessageResponse>): List<ChatMessageResponse> =
        if (_keySession.value == null) messages else messages.map(::decryptMessage)

    suspend fun keyMeta(): Result<ChatKeyMetaResponse> = runCatching {
        api.chatKeyMeta().also { e2eeInitialized = it.initialized }
    }

    /**
     * 一次性设置共享口令：本地派生密钥、生成 verifier，上传公开 KDF 参数。
     * 口令本身与派生密钥都不离开本机。
     */
    suspend fun setupKey(passphrase: CharArray): Result<ChatKeyMetaResponse> = runCatching {
        val salt = ChatCrypto.generateSalt()
        val key = ChatCrypto.deriveKey(passphrase, salt)
        val verifier = ChatCrypto.encryptString(key, ChatCrypto.VERIFIER_TOKEN)
        val meta = api.setupChatKey(
            ChatKeySetupRequest(
                salt = salt,
                iterations = ChatCrypto.DEFAULT_ITERATIONS,
                verifier_iv = verifier.iv,
                verifier_cipher = verifier.ciphertext,
                verifier_hash = ChatCrypto.sha256Hex(verifier.ciphertext),
            ),
        )
        e2eeInitialized = true
        _keySession.value = ChatCrypto.ChatKeySession(
            key = key,
            salt = salt,
            iterations = ChatCrypto.DEFAULT_ITERATIONS,
            kdf = meta.kdf ?: ChatCrypto.DEFAULT_KDF,
            kdfHash = meta.kdf_hash ?: ChatCrypto.DEFAULT_KDF_HASH,
            algo = meta.algo ?: ChatCrypto.DEFAULT_ALGO,
        )
        meta
    }

    /** 用口令解锁密钥：本地 verifier 校验 + 向服务端上报 proof（兼容 web 流程）。 */
    suspend fun unlockKey(passphrase: CharArray): Result<Unit> = runCatching {
        val meta = api.chatKeyMeta()
        e2eeInitialized = meta.initialized
        val salt = meta.salt ?: throw UiTextException(uiText(R.string.chat_error_e2ee_not_setup))
        val verifierIv = meta.verifier_iv ?: throw UiTextException(uiText(R.string.chat_error_e2ee_not_setup))
        val verifierCipher = meta.verifier_cipher ?: throw UiTextException(uiText(R.string.chat_error_e2ee_not_setup))
        if (!ChatCrypto.verifyPassphrase(passphrase, salt, meta.iterations ?: ChatCrypto.DEFAULT_ITERATIONS, verifierIv, verifierCipher)) {
            throw UiTextException(uiText(R.string.chat_error_wrong_passphrase))
        }
        val key = ChatCrypto.deriveKey(passphrase, salt, meta.iterations ?: ChatCrypto.DEFAULT_ITERATIONS)
        // 与 web 相同：解锁后发送一次性 proof（服务端仅作记录，不参与密钥校验）。
        val proof = ChatCrypto.encryptString(key, "${ChatCrypto.VERIFIER_TOKEN}::proof::${System.currentTimeMillis()}")
        runCatching {
            api.verifyChatKey(ChatKeyVerifyRequest(proof_iv = proof.iv, proof_cipher = proof.ciphertext))
            Unit
        }
        _keySession.value = ChatCrypto.ChatKeySession(
            key = key,
            salt = salt,
            iterations = meta.iterations ?: ChatCrypto.DEFAULT_ITERATIONS,
            kdf = meta.kdf ?: ChatCrypto.DEFAULT_KDF,
            kdfHash = meta.kdf_hash ?: ChatCrypto.DEFAULT_KDF_HASH,
            algo = meta.algo ?: ChatCrypto.DEFAULT_ALGO,
        )
    }

    /**
     * 更换共享口令（轮换 salt）。服务端 `ChatKeyRekeyRequest` 在 setup 字段
     * 之外还要求 new_salt / new_verifier_* 四个字段（web 端两处都填新值）；
     * 成功后按返回的新 meta 重建本机会话（与 web「重新解锁」一致）。
     */
    suspend fun rekeyKey(newPassphrase: CharArray): Result<ChatKeyMetaResponse> = runCatching {
        val salt = ChatCrypto.generateSalt()
        val key = ChatCrypto.deriveKey(newPassphrase, salt)
        val verifier = ChatCrypto.encryptString(key, ChatCrypto.VERIFIER_TOKEN)
        val verifierHash = ChatCrypto.sha256Hex(verifier.ciphertext)
        val meta = api.rekeyChatKey(
            ChatKeyRekeyRequest(
                salt = salt,
                iterations = ChatCrypto.DEFAULT_ITERATIONS,
                verifier_iv = verifier.iv,
                verifier_cipher = verifier.ciphertext,
                verifier_hash = verifierHash,
                new_salt = salt,
                new_verifier_iv = verifier.iv,
                new_verifier_cipher = verifier.ciphertext,
                new_verifier_hash = verifierHash,
            ),
        )
        e2eeInitialized = true
        _keySession.value = ChatCrypto.ChatKeySession(
            key = key,
            salt = meta.salt ?: salt,
            iterations = meta.iterations ?: ChatCrypto.DEFAULT_ITERATIONS,
            kdf = meta.kdf ?: ChatCrypto.DEFAULT_KDF,
            kdfHash = meta.kdf_hash ?: ChatCrypto.DEFAULT_KDF_HASH,
            algo = meta.algo ?: ChatCrypto.DEFAULT_ALGO,
        )
        meta
    }

    suspend fun search(keyword: String, limit: Int = 20): Result<ChatSearchResponse> =
        runCatching { api.searchChatMessages(q = keyword, limit = limit) }

    fun sendTyping(isTyping: Boolean) {
        socket.send("""{"type":"TYPING","payload":{"is_typing":$isTyping}}""")
    }

    suspend fun history(beforeId: Int? = null, limit: Int = 30): Result<ChatHistoryResponse> =
        runCatching { api.chatMessages(beforeId, limit) }

    /**
     * Send a chat message. When [visibleAt] is non-null, the server holds
     * the message until that timestamp before releasing it to both partners
     * (the "寄给未来" feature). [idempotencyKey] lets callers retry the
     * send safely across reconnects.
     *
     * 媒体消息（图片/贴纸/语音）：[type] 为对应类型时 [mediaUrl] 必填
     * （服务端约定），[content] 可为空串或图片说明；调用方需先通过
     * UploadRepository 上传拿到 URL。
     */
    suspend fun send(
        content: String,
        visibleAt: Instant? = null,
        idempotencyKey: String? = null,
        type: String = "text",
        mediaUrl: String? = null,
        envelope: ChatCrypto.Envelope? = null,
    ): Result<ChatMessageResponse> = runCatching {
        api.sendChatMessage(
            idempotencyKey = idempotencyKey,
            body = buildSendRequest(content, visibleAt, type, mediaUrl, envelope),
        )
    }

    /** 组装发送载荷；[envelope] 非空时正文置 null，与 web 端 E2EE 约定一致。 */
    private fun buildSendRequest(
        content: String,
        visibleAt: Instant?,
        type: String,
        mediaUrl: String?,
        envelope: ChatCrypto.Envelope?,
    ) = if (envelope != null) {
        ChatSendRequest(
            type = type,
            content = null,
            media_url = mediaUrl,
            visible_at = visibleAt?.toString(),
            is_encrypted = true,
            iv = envelope.iv,
            ciphertext = envelope.ciphertext,
            algo = ChatCrypto.DEFAULT_ALGO,
        )
    } else {
        ChatSendRequest(
            type = type,
            content = content,
            media_url = mediaUrl,
            visible_at = visibleAt?.toString(),
        )
    }

    /**
     * Offline-aware variant of [send]: when the network is down (or the
     * call fails), the request is parked in the SyncQueue so the periodic
     * [SyncWorker] can replay it after reconnect — with the same idempotency
     * key, so a 2xx lost in transit won't duplicate the row.
     *
     * 注意：同步队列按设计只支持纯文本消息 —— 媒体消息依赖先上传成功的
     * media_url，离线时无法补传，因此非 text 类型失败后直接上抛由 UI
     * 提示重试，绝不入队。E2EE 消息在入队前已完成加密（信封随载荷存
     * 进队列），重放时无需再次解锁。
     */
    suspend fun sendOfflineAware(
        content: String,
        visibleAt: Instant? = null,
        type: String = "text",
        mediaUrl: String? = null,
        envelope: ChatCrypto.Envelope? = null,
    ): Result<ChatMessageResponse> {
        val key = UUID.randomUUID().toString()
        val payload = buildSendRequest(content, visibleAt, type, mediaUrl, envelope)
        return try {
            val resp = api.sendChatMessage(idempotencyKey = key, body = payload)
            Result.success(resp)
        } catch (e: Exception) {
            // 媒体消息不入同步队列（队列是纯文本设计）。
            if (type != "text") return Result.failure(e)
            val uid = session.sessionFlow.first().uid
                ?: return Result.failure(UiTextException(uiText(R.string.msg_session_expired)))
            val scope = serverConfigScope.dataScope(uid)
            db.withTransaction {
                syncQueueDao.enqueue(
                    SyncQueueEntity(
                        action = SyncActions.CHAT_SEND,
                        payload = json.encodeToString(payload),
                        localRef = key,
                        scope = scope,
                        idempotencyKey = key,
                    ),
                )
            }
            // Best-effort wake-up of the worker so the queue drains the
            // moment connectivity returns, without waiting for the next
            // periodic tick.
            Result.failure(e)
        }
    }

    suspend fun markRead(): Result<Unit> = runCatching {
        api.markChatRead()
        Unit
    }

    suspend fun state(): Result<ChatStateResponse> = runCatching { api.chatState() }

    suspend fun favorites(): Result<List<ChatMessageResponse>> = runCatching { api.chatFavorites().items }
    suspend fun future(): Result<List<ChatMessageResponse>> = runCatching { api.chatFuture().items }
    suspend fun recall(mid: String): Result<ChatMessageResponse> = runCatching { api.recallChatMessage(mid) }
    suspend fun favorite(mid: String, enabled: Boolean): Result<ChatMessageResponse> = runCatching {
        if (enabled) api.favoriteChatMessage(mid) else api.unfavoriteChatMessage(mid)
    }
    suspend fun mediaPanel(): Result<ChatMediaPanelResponse> = runCatching { api.chatMediaPanel() }
    suspend fun pinnedQuote(): Result<ChatPinnedQuoteResponse> = runCatching { api.chatPinnedQuote() }
    suspend fun pin(mid: String): Result<ChatPinnedQuoteResponse> = runCatching { api.pinChatQuote(ChatPinnedQuoteRequest(mid)) }
    suspend fun clearPin(): Result<ChatPinnedQuoteResponse> = runCatching { api.clearChatPinnedQuote() }
    suspend fun keywords(): Result<ChatKeywordsResponse> = runCatching { api.chatKeywords() }
    suspend fun memoryCard(): Result<ChatMemoryCardResponse> = runCatching { api.chatMemoryCard() }

    suspend fun poke(kind: String): Result<Unit> = runCatching {
        api.poke(PokeRequest(kind))
        Unit
    }

    private fun parseEvent(obj: JsonObject): ChatWsEvent? {
        val type = obj["type"]?.jsonPrimitive?.contentOrNull ?: return null
        val payload = obj["payload"]?.jsonObject
        return when (type) {
            "CHAT_MESSAGE" -> obj["payload"]
                ?.let { runCatching { json.decodeFromJsonElement<ChatMessageResponse>(it) }.getOrNull() }
                ?.let { ChatWsEvent.Message(it) }
            "PRESENCE" -> {
                val uid = payload?.get("uid")?.jsonPrimitive?.contentOrNull ?: return null
                val online = payload["online"]?.jsonPrimitive?.booleanOrNull ?: false
                ChatWsEvent.Presence(uid, online)
            }
            "PRESENCE_SNAPSHOT" -> {
                val uids = payload?.get("online")?.jsonArray
                    ?.mapNotNull { it.jsonPrimitive.contentOrNull } ?: emptyList()
                ChatWsEvent.PresenceSnapshot(uids)
            }
            "TYPING" -> ChatWsEvent.Typing(
                nickname = payload?.get("nickname")?.jsonPrimitive?.contentOrNull ?: "",
                isTyping = payload?.get("is_typing")?.jsonPrimitive?.booleanOrNull ?: false,
            )
            "POKE" -> ChatWsEvent.Poke(
                fromNickname = payload?.get("from_nickname")?.jsonPrimitive?.contentOrNull ?: "Ta",
                label = payload?.get("label")?.jsonPrimitive?.contentOrNull ?: "戳了戳你",
            )
            "CHAT_READ" -> ChatWsEvent.Read
            else -> null
        }
    }
}
