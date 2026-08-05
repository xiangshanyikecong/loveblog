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

package com.lovejournal.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.SiteSettingResponse
import com.lovejournal.app.data.repository.SettingsRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val loading: Boolean = false,
    val saving: Boolean = false,
    val setting: SiteSettingResponse? = null,
    val error: String? = null,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repository: SettingsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.get().fold(
                onSuccess = { _state.value = SettingsUiState(setting = it) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败") },
            )
        }
    }

    fun save(siteName: String?, loveStartDateIso: String?, allowRegistration: Boolean?) {
        _state.value = _state.value.copy(saving = true)
        viewModelScope.launch {
            repository.update(siteName, loveStartDateIso, allowRegistration).fold(
                onSuccess = {
                    _state.value = _state.value.copy(saving = false, setting = it)
                    _message.value = "已保存"
                },
                onFailure = {
                    _state.value = _state.value.copy(saving = false)
                    _message.value = it.message ?: "保存失败"
                },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
