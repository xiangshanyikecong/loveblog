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

package com.lovejournal.app.ui.cottage.period

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.PeriodResponse
import com.lovejournal.app.data.remote.dto.PeriodSummaryResponse
import com.lovejournal.app.data.repository.PeriodRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PeriodUiState(
    val loading: Boolean = false,
    val items: List<PeriodResponse> = emptyList(),
    val summary: PeriodSummaryResponse? = null,
    val error: String? = null,
)

@HiltViewModel
class PeriodViewModel @Inject constructor(
    private val repository: PeriodRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(PeriodUiState())
    val state: StateFlow<PeriodUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            val listResult = repository.list()
            val summary = repository.summary().getOrNull()
            listResult.fold(
                onSuccess = { list ->
                    _state.value = PeriodUiState(items = list.items, summary = summary)
                },
                onFailure = {
                    _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败")
                },
            )
        }
    }

    fun add(startDate: String, endDate: String?, note: String?, onDone: () -> Unit) {
        viewModelScope.launch {
            repository.create(
                startDate = startDate,
                endDate = endDate,
                note = note?.trim()?.ifBlank { null },
            ).fold(
                onSuccess = { _message.value = "已记录"; onDone(); refresh() },
                onFailure = { _message.value = it.message ?: "记录失败" },
            )
        }
    }

    fun delete(cycle: PeriodResponse) {
        viewModelScope.launch {
            repository.delete(cycle.pcid).fold(
                onSuccess = { _message.value = "已删除"; refresh() },
                onFailure = { _message.value = it.message ?: "删除失败" },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
