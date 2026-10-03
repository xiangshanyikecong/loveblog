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
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.dto.CapsuleResponse
import com.lovejournal.app.data.repository.CapsuleRepository
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CapsuleUiState(
    val loading: Boolean = false,
    val items: List<CapsuleResponse> = emptyList(),
    val error: UiText? = null,
)

@HiltViewModel
class CapsuleViewModel @Inject constructor(
    private val repository: CapsuleRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CapsuleUiState())
    val state: StateFlow<CapsuleUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<UiText?>(null)
    val message: StateFlow<UiText?> = _message.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.list().fold(
                onSuccess = { _state.value = CapsuleUiState(items = it) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.toUiText()) },
            )
        }
    }

    fun add(content: String, openAtIso: String, onDone: () -> Unit) {
        if (content.isBlank()) {
            _message.value = uiText(R.string.capsules_msg_say_something)
            return
        }
        viewModelScope.launch {
            repository.create(content.trim(), openAtIso).fold(
                onSuccess = { _message.value = uiText(R.string.capsules_msg_sealed); onDone(); refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun delete(capsule: CapsuleResponse) {
        viewModelScope.launch {
            repository.delete(capsule.uuid).fold(
                onSuccess = { _message.value = uiText(R.string.msg_deleted); refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
