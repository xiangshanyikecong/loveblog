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

package com.lovejournal.app.ui.cottage.wishlist

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.R
import com.lovejournal.app.data.ConnectivityMonitor
import com.lovejournal.app.data.remote.dto.WishResponse
import com.lovejournal.app.data.repository.WishlistRepository
import com.lovejournal.app.sync.SyncScheduler
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class WishlistUiState(
    val loading: Boolean = false,
    val items: List<WishResponse> = emptyList(),
    val pending: Int = 0,
    val completed: Int = 0,
    val error: UiText? = null,
)

@HiltViewModel
class WishlistViewModel @Inject constructor(
    application: Application,
    private val repository: WishlistRepository,
    private val connectivity: ConnectivityMonitor,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(WishlistUiState())
    val state: StateFlow<WishlistUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<UiText?>(null)
    val message: StateFlow<UiText?> = _message.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.list().fold(
                onSuccess = {
                    _state.value = WishlistUiState(
                        items = it.items,
                        pending = it.pending,
                        completed = it.completed,
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(loading = false, error = it.toUiText())
                },
            )
        }
    }

    fun add(title: String, description: String?, category: String?, onDone: () -> Unit) {
        if (title.isBlank()) {
            _message.value = uiText(R.string.wishlist_error_title_required)
            return
        }
        viewModelScope.launch {
            repository.createOfflineAware(
                title = title.trim(),
                description = description?.trim()?.ifBlank { null },
                category = category?.trim()?.ifBlank { null },
                targetDate = null,
                priority = 0,
            ).fold(
                onSuccess = { _message.value = uiText(R.string.msg_added); onDone(); refresh() },
                onFailure = { e ->
                    if (!connectivity.isOnline()) {
                        // 离线：请求已由仓库暂存进同步队列，联网后由
                        // SyncWorker 自动补发，这里按成功收尾避免重复提交。
                        _message.value = uiText(R.string.messages_msg_offline_saved)
                        onDone()
                        SyncScheduler.requestSyncNow(getApplication())
                    } else {
                        _message.value = e.toUiText()
                    }
                },
            )
        }
    }

    fun updateWish(
        wid: String,
        title: String,
        description: String?,
        category: String?,
        onDone: () -> Unit,
    ) {
        if (title.isBlank()) {
            _message.value = uiText(R.string.wishlist_error_title_required)
            return
        }
        viewModelScope.launch {
            repository.update(
                wid = wid,
                title = title.trim(),
                description = description?.trim()?.ifBlank { null },
                category = category?.trim()?.ifBlank { null },
            ).fold(
                onSuccess = { _message.value = uiText(R.string.msg_saved); onDone(); refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun toggle(wish: WishResponse) {
        viewModelScope.launch {
            val result = if (wish.status == "completed") {
                repository.reopen(wish.wid)
            } else {
                repository.complete(wish.wid)
            }
            result.fold(
                onSuccess = { refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun delete(wish: WishResponse) {
        viewModelScope.launch {
            repository.delete(wish.wid).fold(
                onSuccess = { _message.value = uiText(R.string.msg_deleted); refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
