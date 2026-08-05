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

package com.lovejournal.app.ui.cottage.footprints

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.FootprintResponse
import com.lovejournal.app.data.repository.FootprintRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FootprintUiState(
    val loading: Boolean = false,
    val data: FootprintResponse? = null,
    val error: String? = null,
)

@HiltViewModel
class FootprintViewModel @Inject constructor(
    private val repository: FootprintRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(FootprintUiState())
    val state: StateFlow<FootprintUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.load().fold(
                onSuccess = { _state.value = FootprintUiState(data = it) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败") },
            )
        }
    }
}
