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

package com.lovejournal.app.ui.cottage.plans

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.PlanResponse
import com.lovejournal.app.data.repository.PlanRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PlanUiState(
    val loading: Boolean = false,
    val items: List<PlanResponse> = emptyList(),
    val total: Int = 0,
    val active: Int = 0,
    val completed: Int = 0,
    val cancelled: Int = 0,
    val showDone: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class PlanViewModel @Inject constructor(
    private val repository: PlanRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(PlanUiState())
    val state: StateFlow<PlanUiState> = _state.asStateFlow()

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
                    _state.value = _state.value.copy(
                        loading = false,
                        items = it.items,
                        total = it.total,
                        active = it.active,
                        completed = it.completed,
                        cancelled = it.cancelled,
                        error = null,
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败")
                },
            )
        }
    }

    fun toggleShowDone() {
        _state.value = _state.value.copy(showDone = !_state.value.showDone)
    }

    fun add(
        title: String,
        description: String?,
        location: String?,
        planDate: String?,
        priority: Int,
        onDone: () -> Unit,
    ) {
        if (title.isBlank()) {
            _message.value = "请填写计划标题"
            return
        }
        viewModelScope.launch {
            repository.create(
                title = title.trim(),
                description = description?.trim()?.ifBlank { null },
                location = location?.trim()?.ifBlank { null },
                planDate = planDate,
                priority = priority,
            ).fold(
                onSuccess = { _message.value = "已添加计划"; onDone(); refresh() },
                onFailure = { _message.value = it.message ?: "添加失败" },
            )
        }
    }

    fun toggleComplete(plan: PlanResponse) {
        viewModelScope.launch {
            val result = if (plan.status == "done") {
                repository.reopen(plan.pid)
            } else {
                repository.complete(plan.pid)
            }
            result.fold(
                onSuccess = { refresh() },
                onFailure = { _message.value = it.message ?: "操作失败" },
            )
        }
    }

    fun delete(plan: PlanResponse) {
        viewModelScope.launch {
            repository.delete(plan.pid).fold(
                onSuccess = { _message.value = "已删除"; refresh() },
                onFailure = { _message.value = it.message ?: "删除失败" },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
