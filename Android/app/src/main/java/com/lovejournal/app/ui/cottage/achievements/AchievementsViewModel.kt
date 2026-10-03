/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

package com.lovejournal.app.ui.cottage.achievements

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.AchievementsResponse
import com.lovejournal.app.data.repository.AchievementsRepository
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AchievementsUiState(
    val loading: Boolean = false,
    val data: AchievementsResponse? = null,
    val error: UiText? = null,
)

@HiltViewModel
class AchievementsViewModel @Inject constructor(
    private val repository: AchievementsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(AchievementsUiState(loading = true))
    val state: StateFlow<AchievementsUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.achievements().fold(
                onSuccess = { _state.value = AchievementsUiState(loading = false, data = it) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.toUiText()) },
            )
        }
    }
}
