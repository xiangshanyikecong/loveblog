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

package com.lovejournal.app.ui.cottage.chat

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.ConnectivityMonitor
import com.lovejournal.app.data.chat.ChatMediaDecryptor
import com.lovejournal.app.data.crypto.ChatCrypto
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.dto.ChatMessageResponse
import com.lovejournal.app.data.remote.dto.ChatMediaPanelResponse
import com.lovejournal.app.data.remote.dto.ChatMemoryCardResponse
import com.lovejournal.app.data.remote.dto.ChatPinnedQuoteResponse
import com.lovejournal.app.data.repository.ChatRepository
import com.lovejournal.app.data.repository.ChatWsEvent
import com.lovejournal.app.data.repository.UploadRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException
import javax.inject.Inject

data class ChatUiState(
    val messages: List<ChatMessageResponse> = emptyList(),
    val partnerNickname: String? = null,
    val partnerOnline: Boolean = false,
    val partnerTyping: Boolean = false,
    val connected: Boolean = false,
    val selfUid: String? = null,
    val loading: Boolean = true,
    val toolsOpen: Boolean = false,
    val pinnedQuote: ChatPinnedQuoteResponse? = null,
    val favorites: List<ChatMessageResponse> = emptyList(),
    val future: List<ChatMessageResponse> = emptyList(),
    val mediaPanel: ChatMediaPanelResponse? = null,
    val memoryCard: ChatMemoryCardResponse? = null,
    /** 图片消息正在上传/发送中，用于附件按钮的转圈与防连点。 */
    val uploadingImage: Boolean = false,
    // ---- 聊天搜索 ----
    val searchQuery: String = "",
    val searchResults: List<ChatMessageResponse>? = null,
    val searching: Boolean = false,
    // ---- 端到端加密（E2EE）----
    /** 服务器已设置共享口令。 */
    val e2eeInitialized: Boolean = false,
    /** 本机已解锁（派生密钥在内存中）。 */
    val e2eeUnlocked: Boolean = false,
    /** 是否曾尝试取密钥状态（避免设置完成前的误报）。 */
    val e2eeReady: Boolean = false,
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val repository: ChatRepository,
    private val uploadRepository: UploadRepository,
    private val serverConfig: ServerConfig,
    private val connectivity: ConnectivityMonitor,
    private val session: SessionManager,
    val mediaDecryptor: ChatMediaDecryptor,
) : ViewModel() {

    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    private val _toast = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val toast: SharedFlow<String> = _toast

    // mid -> message; sorted by server id when emitted (dedups REST + WS echoes).
    private val messageMap = linkedMapOf<String, ChatMessageResponse>()
    private var partnerUid: String? = null
    private var typingResetJob: Job? = null
    private var typingActive = false

    init {
        viewModelScope.launch {
            _state.update { it.copy(selfUid = session.sessionFlow.first().uid) }
        }
        observeConnection()
        observeEvents()
        observeKeySession()
        bootstrap()
        refreshKeyState()
        repository.connect()
    }

    private fun observeKeySession() {
        viewModelScope.launch {
            repository.keySession.collect { session ->
                _state.update { it.copy(e2eeUnlocked = session != null) }
                // 解锁/上锁都影响已渲染的密文，重新解密一遍；已解密的媒体
                // 缓存同样作废（换口令后旧明文不再代表当前可读状态）。
                mediaDecryptor.clear()
                emitMessages()
            }
        }
    }

    /** 拉取服务端 E2EE 密钥状态（是否已设置共享口令）。 */
    fun refreshKeyState() {
        viewModelScope.launch {
            repository.keyMeta().onSuccess { meta ->
                _state.update {
                    it.copy(e2eeInitialized = meta.initialized, e2eeReady = true)
                }
            }
            // 失败时不置 e2eeReady：状态未知（可能离线/出错）就放行明文发送，
            // 若恰逢对方已启用加密，入队的明文会被服务端永久拒绝。
        }
    }

    fun unlockE2ee(passphrase: String, onDone: (String?) -> Unit) {
        viewModelScope.launch {
            repository.unlockKey(passphrase.toCharArray())
                .onSuccess { onDone(null) }
                .onFailure { onDone(it.message ?: "解锁失败") }
        }
    }

    fun setupE2ee(passphrase: String, onDone: (String?) -> Unit) {
        viewModelScope.launch {
            repository.setupKey(passphrase.toCharArray())
                .onSuccess {
                    _state.update { it.copy(e2eeInitialized = true) }
                    onDone(null)
                }
                .onFailure { onDone(it.message ?: "设置失败") }
        }
    }

    fun rekeyE2ee(passphrase: String, onDone: (String?) -> Unit) {
        viewModelScope.launch {
            repository.rekeyKey(passphrase.toCharArray())
                .onSuccess { onDone(null) }
                .onFailure { onDone(it.message ?: "更换口令失败") }
        }
    }

    private fun bootstrap() {
        viewModelScope.launch {
            repository.state().onSuccess { st ->
                partnerUid = st.partner_uid
                _state.update {
                    it.copy(partnerNickname = st.partner_nickname, partnerOnline = st.partner_online)
                }
            }
            repository.history().onSuccess { hist ->
                hist.items.forEach { messageMap[it.mid] = it }
                emitMessages()
            }
            _state.update { it.copy(loading = false) }
            repository.markRead()
        }
    }

    private fun observeConnection() {
        viewModelScope.launch {
            repository.connected.collect { c -> _state.update { it.copy(connected = c) } }
        }
    }

    private fun observeEvents() {
        viewModelScope.launch {
            repository.events.collect { event ->
                when (event) {
                    is ChatWsEvent.Message -> {
                        messageMap[event.message.mid] = event.message
                        emitMessages()
                        if (event.message.sender_uid != _state.value.selfUid) {
                            repository.markRead()
                        }
                    }
                    is ChatWsEvent.Presence ->
                        if (partnerUid == null || event.uid == partnerUid) {
                            _state.update { it.copy(partnerOnline = event.online) }
                        }
                    is ChatWsEvent.PresenceSnapshot ->
                        _state.update {
                            it.copy(partnerOnline = partnerUid != null && event.onlineUids.contains(partnerUid))
                        }
                    is ChatWsEvent.Typing -> {
                        _state.update { it.copy(partnerTyping = event.isTyping) }
                        if (event.isTyping) scheduleTypingReset()
                    }
                    is ChatWsEvent.Poke -> _toast.tryEmit("${event.fromNickname} ${event.label}")
                    ChatWsEvent.Read -> Unit
                }
            }
        }
    }

    private fun scheduleTypingReset() {
        typingResetJob?.cancel()
        typingResetJob = viewModelScope.launch {
            delay(6_000)
            _state.update { it.copy(partnerTyping = false) }
        }
    }

    private fun emitMessages() {
        val decrypted = repository.decryptAll(messageMap.values.sortedBy { m -> m.id })
        _state.update { it.copy(messages = decrypted) }
    }

    // ---- 聊天搜索 ----

    private var searchJob: Job? = null

    fun updateSearchQuery(query: String) {
        _state.update { it.copy(searchQuery = query) }
        searchJob?.cancel()
        if (query.isBlank()) {
            _state.update { it.copy(searchResults = null, searching = false) }
            return
        }
        searchJob = viewModelScope.launch {
            delay(250) // 输入防抖
            _state.update { it.copy(searching = true) }
            repository.search(query.trim()).onSuccess { resp ->
                val merged = LinkedHashMap<String, ChatMessageResponse>()
                resp.items.forEach { merged[it.mid] = it }
                // E2EE 消息服务端搜不到：与 web 一致，补充本地已加载消息的
                // 明文匹配（对本地副本先解密再匹配）。
                if (_state.value.e2eeInitialized) {
                    val needle = query.trim().lowercase()
                    repository.decryptAll(messageMap.values.sortedByDescending { it.id })
                        .filter { it.type == "text" && !it.is_recalled }
                        .filter { (it.content ?: "").lowercase().contains(needle) }
                        .take(20)
                        .forEach { merged.getOrPut(it.mid) { it } }
                }
                val results = repository.decryptAll(merged.values.sortedByDescending { it.id })
                if (_state.value.searchQuery.trim() == query.trim()) {
                    _state.update { it.copy(searchResults = results, searching = false) }
                }
            }.onFailure {
                if (_state.value.searchQuery.trim() == query.trim()) {
                    _state.update { it.copy(searchResults = emptyList(), searching = false) }
                }
            }
        }
    }

    fun send(content: String, visibleAt: java.time.Instant? = null) {
        if (content.isBlank() && visibleAt == null) return
        if (typingActive) {
            typingActive = false
            repository.sendTyping(false)
        }
        viewModelScope.launch {
            // E2EE 状态未知时（冷启动正在拉取密钥状态）禁止发送：否则明文
            // 消息可能在对方刚启用加密后入队，重放会被服务端永久拒绝，
            // 在同步队列里反复失败。状态就绪后：已启用 → 必须本地加密；
            // 已启用但未解锁 → 拦截提示。
            if (!_state.value.e2eeReady) {
                _toast.tryEmit("正在同步加密设置，请稍候再发送")
                refreshKeyState() // 每次发送尝试都顺带重试拉取加密状态
                return@launch
            }
            val envelope = if (_state.value.e2eeInitialized && _state.value.e2eeUnlocked) {
                repository.encryptText(content.trim())
            } else {
                null
            }
            if (_state.value.e2eeInitialized && envelope == null) {
                _toast.tryEmit("聊天已加密，请先输入共享口令解锁")
                return@launch
            }
            // Offline-aware: a network failure parks the payload in the
            // SyncQueue for the next worker tick instead of dropping the
            // user-typed message on the floor.
            repository.sendOfflineAware(content.trim(), visibleAt = visibleAt, envelope = envelope)
                .onSuccess { msg ->
                    // 加密消息服务端回包 content=null：像 web 一样用本地明文回填。
                    messageMap[msg.mid] = if (msg.is_encrypted && msg.content == null) {
                        msg.copy(content = content.trim())
                    } else {
                        msg
                    }
                    emitMessages()
                }
                .onFailure { _toast.tryEmit(it.message ?: "已存入待发送队列") }
        }
    }

    /**
     * 发送图片消息。未启用 E2EE 时走明文链路：经 [UploadRepository.uploadImage]
     * 压缩上传到 /v1/uploads/checkin，输入框里已输入的文字作为图片说明。
     *
     * 已启用 E2EE 时与网页端协议一致（见 docs/design/E2EE_CHAT_IMAGE_DESIGN.md）：
     * 压缩 → AES-GCM 整文件加密 → 密文上传 /v1/uploads/chat-encrypted-media →
     * 消息只携带 iv。服务端 schema 禁止加密媒体携带明文说明与内联密文，
     * 因此 [caption] 在加密模式下不发送（UI 保留输入框文字并提示）。
     *
     * 仅在线可用：上传依赖网络，失败不会进同步队列（队列按设计只存纯
     * 文本），一律通过 [toast] 提示用户重试。
     */
    fun sendImage(uri: Uri, caption: String) {
        if (_state.value.uploadingImage) return // 上传中，忽略重复点击
        // 加密状态未知时不放行：与 send() 同理，避免对方刚启用加密后，
        // 明文图片在重放时被服务端永久拒绝（error.encrypted_chat_no_plaintext）。
        if (!_state.value.e2eeReady) {
            _toast.tryEmit("正在同步加密设置，请稍候再发送")
            refreshKeyState() // 顺带重试拉取加密状态
            return
        }
        if (!connectivity.isOnline()) {
            _toast.tryEmit("当前离线，图片消息需要联网后发送")
            return
        }
        if (_state.value.e2eeInitialized && !_state.value.e2eeUnlocked) {
            _toast.tryEmit("聊天已加密，请先输入共享口令解锁")
            return
        }
        _state.update { it.copy(uploadingImage = true) }
        viewModelScope.launch {
            try {
                if (_state.value.e2eeInitialized) {
                    sendEncryptedImage(uri, caption)
                } else {
                    sendPlaintextImage(uri, caption)
                }
            } finally {
                _state.update { it.copy(uploadingImage = false) }
            }
        }
    }

    private suspend fun sendPlaintextImage(uri: Uri, caption: String) {
        uploadRepository.uploadImage(uri)
            .onSuccess { uploaded ->
                repository.send(
                    content = caption.trim(),
                    type = "image",
                    mediaUrl = uploaded.url,
                )
                    .onSuccess { messageMap[it.mid] = it; emitMessages() }
                    .onFailure { _toast.tryEmit(it.message ?: "图片发送失败") }
            }
            .onFailure { _toast.tryEmit(it.message ?: "图片上传失败") }
    }

    /**
     * 加密图片链路：压缩 → 加密 → 密文上传 → 发送（消息只带 iv）。
     * 服务端密文文件上限 25MB，收到 413 时按 [UPLOAD_TIERS] 降质重压重试。
     */
    private suspend fun sendEncryptedImage(uri: Uri, caption: String) {
        if (caption.isNotBlank()) {
            _toast.tryEmit("加密模式下图片不支持附带文字")
        }
        for ((maxEdge, quality) in UPLOAD_TIERS) {
            val plain = runCatching { uploadRepository.compressChatImage(uri, maxEdge, quality) }
                .getOrElse { _toast.tryEmit(it.message ?: "图片处理失败"); return }
            val envelope = repository.encryptMedia(plain) ?: run {
                _toast.tryEmit("聊天已加密，请先输入共享口令解锁")
                return
            }
            val uploaded = uploadRepository.uploadEncryptedChatMedia(envelope.ciphertextBytes)
            val error = uploaded.exceptionOrNull()
            when {
                error == null -> {
                    // 媒体消息不内联密文：信封只取 iv（密文在 media_url 文件里）。
                    repository.send(
                        content = "",
                        type = "image",
                        mediaUrl = uploaded.getOrThrow().url,
                        envelope = ChatCrypto.Envelope(iv = envelope.iv, ciphertext = ""),
                    )
                        .onSuccess { messageMap[it.mid] = it; emitMessages() }
                        .onFailure { _toast.tryEmit(it.message ?: "图片发送失败") }
                    return
                }
                (error as? HttpException)?.code() == 413 -> Unit // 超限，降档重压后重试
                else -> {
                    _toast.tryEmit(error.message ?: "图片上传失败")
                    return
                }
            }
        }
        _toast.tryEmit("图片过大，压缩后仍无法上传，请换一张试试")
    }

    /** 把服务端返回的相对媒体路径解析成可加载的绝对 URL（与相册页同一套规则）。 */
    fun mediaUrl(path: String?): String? = serverConfig.mediaUrl(path)

    /** Drives the lightweight TYPING signal: notify once on start, once on stop. */
    fun onInputChanged(text: String) {
        val active = text.isNotBlank()
        if (active != typingActive) {
            typingActive = active
            repository.sendTyping(active)
        }
    }

    fun poke() {
        viewModelScope.launch {
            repository.poke("poke")
                .onSuccess { _toast.tryEmit("已戳一戳对方 👉") }
                .onFailure { _toast.tryEmit(it.message ?: "戳一戳失败") }
        }
    }

    fun recall(message: ChatMessageResponse) = viewModelScope.launch {
        repository.recall(message.mid).fold(onSuccess = { messageMap[it.mid] = it; emitMessages() }, onFailure = { _toast.tryEmit(it.message ?: "撤回失败") })
    }

    fun toggleFavorite(message: ChatMessageResponse) = viewModelScope.launch {
        repository.favorite(message.mid, !message.is_favorite).fold(onSuccess = { messageMap[it.mid] = it; emitMessages() }, onFailure = { _toast.tryEmit(it.message ?: "操作失败") })
    }

    fun pin(message: ChatMessageResponse) = viewModelScope.launch {
        repository.pin(message.mid).fold(onSuccess = { _state.update { state -> state.copy(pinnedQuote = it) } }, onFailure = { _toast.tryEmit(it.message ?: "置顶失败") })
    }

    fun clearPin() = viewModelScope.launch {
        repository.clearPin().onSuccess { _state.update { state -> state.copy(pinnedQuote = it) } }
    }

    fun openTools() {
        _state.update { it.copy(toolsOpen = true) }
        viewModelScope.launch {
            repository.pinnedQuote().onSuccess { value -> _state.update { it.copy(pinnedQuote = value) } }
            repository.favorites().onSuccess { value -> _state.update { it.copy(favorites = value) } }
            repository.future().onSuccess { value -> _state.update { it.copy(future = value) } }
            repository.mediaPanel().onSuccess { value -> _state.update { it.copy(mediaPanel = value) } }
            repository.memoryCard().onSuccess { value -> _state.update { it.copy(memoryCard = value) } }
        }
    }

    fun closeTools() { _state.update { it.copy(toolsOpen = false) } }

    override fun onCleared() {
        repository.disconnect()
        super.onCleared()
    }

    private companion object {
        /** 加密图片压缩档位（最长边 px to JPEG 质量）：超服务端 25MB 密文上限时逐档降级。 */
        val UPLOAD_TIERS = listOf(1600 to 85, 1280 to 70, 1024 to 55)
    }
}
