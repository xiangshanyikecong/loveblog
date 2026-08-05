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

package com.lovejournal.app.ui.capsules

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.CapsuleResponse
import com.lovejournal.app.data.repository.CapsuleRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CapsuleUiState(
    val loading: Boolean = false,
    val items: List<CapsuleResponse> = emptyList(),
    val error: String? = null,
)

@HiltViewModel
class CapsuleViewModel @Inject constructor(
    private val repository: CapsuleRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CapsuleUiState())
    val state: StateFlow<CapsuleUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.list().fold(
                onSuccess = { _state.value = CapsuleUiState(items = it) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败") },
            )
        }
    }

    fun add(content: String, openAtIso: String, onDone: () -> Unit) {
        if (content.isBlank()) {
            _message.value = "写点想对未来说的话吧"
            return
        }
        viewModelScope.launch {
            repository.create(content.trim(), openAtIso).fold(
                onSuccess = { _message.value = "已封存，到时间才能开启"; onDone(); refresh() },
                onFailure = { _message.value = it.message ?: "封存失败" },
            )
        }
    }

    fun delete(capsule: CapsuleResponse) {
        viewModelScope.launch {
            repository.delete(capsule.uuid).fold(
                onSuccess = { _message.value = "已删除"; refresh() },
                onFailure = { _message.value = it.message ?: "删除失败" },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
