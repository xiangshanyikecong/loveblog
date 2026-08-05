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

package com.lovejournal.app.ui.cottage.reminders

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.ReminderResponse
import com.lovejournal.app.data.repository.ReminderRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ReminderUiState(
    val loading: Boolean = false,
    val items: List<ReminderResponse> = emptyList(),
    val active: Int = 0,
    val done: Int = 0,
    val due: Int = 0,
    val includeDone: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class ReminderViewModel @Inject constructor(
    private val repository: ReminderRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ReminderUiState())
    val state: StateFlow<ReminderUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        val includeDone = _state.value.includeDone
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.list(includeDone).fold(
                onSuccess = {
                    _state.value = ReminderUiState(
                        items = it.items,
                        active = it.active,
                        done = it.done,
                        due = it.due,
                        includeDone = includeDone,
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败")
                },
            )
        }
    }

    fun toggleIncludeDone() {
        _state.value = _state.value.copy(includeDone = !_state.value.includeDone)
        refresh()
    }

    fun add(
        title: String,
        note: String?,
        remindAtIso: String,
        audience: String,
        onDone: () -> Unit,
    ) {
        if (title.isBlank()) {
            _message.value = "请填写提醒内容"
            return
        }
        viewModelScope.launch {
            repository.create(
                title = title.trim(),
                note = note?.trim()?.ifBlank { null },
                remindAtIso = remindAtIso,
                audience = audience,
            ).fold(
                onSuccess = { _message.value = "已添加提醒"; onDone(); refresh() },
                onFailure = { _message.value = it.message ?: "添加失败" },
            )
        }
    }

    fun toggleDone(reminder: ReminderResponse) {
        viewModelScope.launch {
            val result = if (reminder.is_done) {
                repository.reopen(reminder.rid)
            } else {
                repository.markDone(reminder.rid)
            }
            result.fold(
                onSuccess = { refresh() },
                onFailure = { _message.value = it.message ?: "操作失败" },
            )
        }
    }

    fun delete(reminder: ReminderResponse) {
        viewModelScope.launch {
            repository.delete(reminder.rid).fold(
                onSuccess = { _message.value = "已删除"; refresh() },
                onFailure = { _message.value = it.message ?: "删除失败" },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
