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

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.WishResponse
import com.lovejournal.app.data.repository.WishlistRepository
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
    val error: String? = null,
)

@HiltViewModel
class WishlistViewModel @Inject constructor(
    private val repository: WishlistRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(WishlistUiState())
    val state: StateFlow<WishlistUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

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
                    _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败")
                },
            )
        }
    }

    fun add(title: String, description: String?, category: String?, onDone: () -> Unit) {
        if (title.isBlank()) {
            _message.value = "请填写心愿标题"
            return
        }
        viewModelScope.launch {
            repository.create(
                title = title.trim(),
                description = description?.trim()?.ifBlank { null },
                category = category?.trim()?.ifBlank { null },
                targetDate = null,
                priority = 0,
            ).fold(
                onSuccess = { _message.value = "已添加心愿"; onDone(); refresh() },
                onFailure = { _message.value = it.message ?: "添加失败" },
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
            _message.value = "请填写心愿标题"
            return
        }
        viewModelScope.launch {
            repository.update(
                wid = wid,
                title = title.trim(),
                description = description?.trim()?.ifBlank { null },
                category = category?.trim()?.ifBlank { null },
            ).fold(
                onSuccess = { _message.value = "已更新心愿"; onDone(); refresh() },
                onFailure = { _message.value = it.message ?: "更新失败" },
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
                onFailure = { _message.value = it.message ?: "操作失败" },
            )
        }
    }

    fun delete(wish: WishResponse) {
        viewModelScope.launch {
            repository.delete(wish.wid).fold(
                onSuccess = { _message.value = "已删除"; refresh() },
                onFailure = { _message.value = it.message ?: "删除失败" },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
