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

package com.lovejournal.app.ui.recyclebin

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.dto.RecycleBinItemDto
import com.lovejournal.app.data.repository.RecycleBinRepository
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class RecycleBinUiState(
    val loading: Boolean = false,
    val items: List<RecycleBinItemDto> = emptyList(),
    val total: Int = 0,
    val error: UiText? = null,
)

@HiltViewModel
class RecycleBinViewModel @Inject constructor(
    private val repository: RecycleBinRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(RecycleBinUiState())
    val state: StateFlow<RecycleBinUiState> = _state.asStateFlow()

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
                    _state.value = RecycleBinUiState(items = it.items, total = it.total)
                },
                onFailure = {
                    _state.value = _state.value.copy(loading = false, error = it.toUiText())
                },
            )
        }
    }

    fun restore(item: RecycleBinItemDto) {
        viewModelScope.launch {
            repository.restore(item.type, item.id).fold(
                onSuccess = { _message.value = uiText(R.string.recycle_bin_msg_restored); refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun deleteForever(item: RecycleBinItemDto) {
        viewModelScope.launch {
            repository.deleteForever(item.type, item.id).fold(
                onSuccess = { _message.value = uiText(R.string.recycle_bin_msg_deleted_forever); refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun clearAll() {
        viewModelScope.launch {
            repository.clear().fold(
                onSuccess = { _message.value = uiText(R.string.recycle_bin_msg_cleared); refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
