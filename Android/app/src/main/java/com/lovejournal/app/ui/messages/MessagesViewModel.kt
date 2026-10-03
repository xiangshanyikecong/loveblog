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
import com.lovejournal.app.R
import com.lovejournal.app.data.local.entity.MessageEntity
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.NetworkErrors
import com.lovejournal.app.data.remote.dto.ContentVersion
import com.lovejournal.app.data.repository.MessageRepository
import com.lovejournal.app.data.repository.MessageRepository.SendOutcome
import com.lovejournal.app.sync.SyncScheduler
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class MessagesViewModel @Inject constructor(
    application: Application,
    private val repository: MessageRepository,
    private val session: SessionManager,
) : AndroidViewModel(application) {

    val messages: StateFlow<List<MessageEntity>> = repository.observeMessages()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    /** 当前登录用户的 uid，用于仅对自己的留言展示 编辑/删除/历史版本 操作。 */
    private val _selfUid = MutableStateFlow<String?>(null)
    val selfUid: StateFlow<String?> = _selfUid.asStateFlow()

    /** 当前查看的历史版本列表（打开留言的历史版本弹窗时加载）。 */
    private val _versions = MutableStateFlow<List<ContentVersion>>(emptyList())
    val versions: StateFlow<List<ContentVersion>> = _versions.asStateFlow()

    private val _status = MutableStateFlow<UiText?>(null)
    val status: StateFlow<UiText?> = _status.asStateFlow()

    init {
        refresh()
        viewModelScope.launch { _selfUid.value = session.sessionFlow.first().uid }
    }

    fun refresh() {
        viewModelScope.launch { repository.refresh() }
    }

    fun send(content: String, isPublic: Boolean) {
        if (content.isBlank()) return
        viewModelScope.launch {
            val outcome = repository.send(content.trim(), isPublic = isPublic)
            _status.value = when (outcome) {
                SendOutcome.QUEUED_ONLINE -> if (isPublic) uiText(R.string.messages_msg_sent) else uiText(R.string.messages_msg_sent_private)
                SendOutcome.QUEUED_OFFLINE -> uiText(R.string.messages_msg_offline_saved)
            }
            // Kick an immediate sync attempt; WorkManager no-ops when offline.
            SyncScheduler.requestSyncNow(getApplication())
        }
    }

    /**
     * 保存对留言的编辑。服务端 PATCH 按 exclude_unset 语义处理，
     * 只有内容或可见性真正变化时才提交对应字段。
     */
    fun editMessage(message: MessageEntity, newContent: String, newIsPublic: Boolean) {
        val content = newContent.trim()
        if (content.isEmpty()) {
            _status.value = uiText(R.string.messages_error_empty_content)
            return
        }
        val contentChanged = content != message.content
        val visibilityChanged = newIsPublic != message.isPublic
        if (!contentChanged && !visibilityChanged) {
            _status.value = uiText(R.string.messages_error_no_changes)
            return
        }
        viewModelScope.launch {
            repository.edit(
                message.msgId,
                newContent = if (contentChanged) content else null,
                isPublic = if (visibilityChanged) newIsPublic else null,
            ).fold(
                onSuccess = {
                    _status.value = uiText(R.string.msg_saved)
                    refresh()
                },
                onFailure = { _status.value = NetworkErrors.toUiText(it) },
            )
        }
    }

    /** 删除留言（软删除，进入回收站，可在后台恢复）。 */
    fun deleteMessage(msgId: String) {
        viewModelScope.launch {
            repository.remove(msgId).fold(
                onSuccess = {
                    _status.value = uiText(R.string.msg_deleted)
                    refresh()
                },
                onFailure = { _status.value = NetworkErrors.toUiText(it) },
            )
        }
    }

    /** 加载指定留言的历史版本列表。 */
    fun loadVersions(msgId: String) {
        viewModelScope.launch {
            repository.versions(msgId).fold(
                onSuccess = { _versions.value = it },
                onFailure = { _status.value = NetworkErrors.toUiText(it) },
            )
        }
    }

    /** 将留言回滚到指定历史版本。 */
    fun rollbackMessage(msgId: String, version: Int) {
        viewModelScope.launch {
            repository.rollback(msgId, version).fold(
                onSuccess = {
                    _status.value = uiText(R.string.messages_rolled_back, version)
                    _versions.value = emptyList()
                    refresh()
                },
                onFailure = { _status.value = NetworkErrors.toUiText(it) },
            )
        }
    }

    fun clearVersions() {
        _versions.value = emptyList()
    }

    fun clearStatus() {
        _status.value = null
    }
}
