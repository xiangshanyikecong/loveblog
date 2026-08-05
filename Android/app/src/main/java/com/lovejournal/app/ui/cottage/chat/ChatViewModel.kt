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

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.dto.ChatMessageResponse
import com.lovejournal.app.data.remote.dto.ChatMediaPanelResponse
import com.lovejournal.app.data.remote.dto.ChatMemoryCardResponse
import com.lovejournal.app.data.remote.dto.ChatPinnedQuoteResponse
import com.lovejournal.app.data.repository.ChatRepository
import com.lovejournal.app.data.repository.ChatWsEvent
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
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val repository: ChatRepository,
    private val session: SessionManager,
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
        bootstrap()
        repository.connect()
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
        _state.update { it.copy(messages = messageMap.values.sortedBy { m -> m.id }) }
    }

    fun send(content: String, visibleAt: java.time.Instant? = null) {
        if (content.isBlank() && visibleAt == null) return
        if (typingActive) {
            typingActive = false
            repository.sendTyping(false)
        }
        viewModelScope.launch {
            // Offline-aware: a network failure parks the payload in the
            // SyncQueue for the next worker tick instead of dropping the
            // user-typed message on the floor.
            repository.sendOfflineAware(content.trim(), visibleAt = visibleAt)
                .onSuccess { messageMap[it.mid] = it; emitMessages() }
                .onFailure { _toast.tryEmit(it.message ?: "已存入待发送队列") }
        }
    }

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
}
