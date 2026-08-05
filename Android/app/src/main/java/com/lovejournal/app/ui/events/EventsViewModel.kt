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

package com.lovejournal.app.ui.events

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.EventCreateRequest
import com.lovejournal.app.data.remote.dto.EventResponse
import com.lovejournal.app.data.repository.EventsRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class EventsUiState(
    val loading: Boolean = false,
    val events: List<EventResponse> = emptyList(),
    val error: String? = null,
)

@HiltViewModel
class EventsViewModel @Inject constructor(
    private val repository: EventsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(EventsUiState())
    val state: StateFlow<EventsUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.list().fold(
                onSuccess = { _state.value = EventsUiState(events = it) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败") },
            )
        }
    }

    fun save(
        existing: EventResponse?,
        title: String,
        date: String,
        type: String,
        isImportant: Boolean,
        isYearlyRepeat: Boolean,
        onDone: () -> Unit,
    ) {
        if (title.isBlank() || date.isBlank()) {
            _message.value = "请填写标题和日期"
            return
        }
        val request = EventCreateRequest(
            title = title.trim(),
            date = date.trim(),
            type = type,
            is_important = isImportant,
            is_yearly_repeat = isYearlyRepeat,
        )
        viewModelScope.launch {
            val result = if (existing == null) {
                repository.create(request)
            } else {
                repository.update(existing.eid, request)
            }
            result.fold(
                onSuccess = {
                    _message.value = if (existing == null) "已添加" else "已保存"
                    onDone()
                    refresh()
                },
                onFailure = { _message.value = it.message ?: "保存失败" },
            )
        }
    }

    fun delete(event: EventResponse) {
        viewModelScope.launch {
            repository.delete(event.eid).fold(
                onSuccess = {
                    _message.value = "已删除"
                    refresh()
                },
                onFailure = { _message.value = it.message ?: "删除失败" },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
