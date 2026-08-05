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

package com.lovejournal.app.ui.messages

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.local.entity.MessageEntity
import com.lovejournal.app.data.repository.MessageRepository
import com.lovejournal.app.data.repository.MessageRepository.SendOutcome
import com.lovejournal.app.sync.SyncScheduler
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class MessagesViewModel @Inject constructor(
    application: Application,
    private val repository: MessageRepository,
) : AndroidViewModel(application) {

    val messages: StateFlow<List<MessageEntity>> = repository.observeMessages()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    private val _status = MutableStateFlow<String?>(null)
    val status: StateFlow<String?> = _status.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch { repository.refresh() }
    }

    fun send(content: String, isPublic: Boolean) {
        if (content.isBlank()) return
        viewModelScope.launch {
            val outcome = repository.send(content.trim(), isPublic = isPublic)
            _status.value = when (outcome) {
                SendOutcome.QUEUED_ONLINE -> if (isPublic) "已发送" else "私密留言已发送"
                SendOutcome.QUEUED_OFFLINE -> "离线已保存，联网后自动同步"
            }
            // Kick an immediate sync attempt; WorkManager no-ops when offline.
            SyncScheduler.requestSyncNow(getApplication())
        }
    }

    fun clearStatus() {
        _status.value = null
    }
}
