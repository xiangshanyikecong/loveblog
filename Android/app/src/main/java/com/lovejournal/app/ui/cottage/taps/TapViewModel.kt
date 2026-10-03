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

package com.lovejournal.app.ui.cottage.taps

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.dto.TapResponse
import com.lovejournal.app.data.repository.TapRepository
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class TapUiState(
    val loading: Boolean = false,
    val sending: Boolean = false,
    val items: List<TapResponse> = emptyList(),
    val totalKept: Int = 0,
    val error: UiText? = null,
    // 一次性提示（发送成功 / 404 / 429 等），由 UI 展示后清除。
    val message: UiText? = null,
    val messageIsError: Boolean = false,
    // 每次发送成功自增，驱动 UI 的爱心动画与触觉反馈；0 表示尚未发送过。
    val sentCount: Int = 0,
    val lastKind: String = "tap",
)

@HiltViewModel
class TapViewModel @Inject constructor(
    private val repository: TapRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(TapUiState(loading = true))
    val state: StateFlow<TapUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.recent().fold(
                onSuccess = {
                    _state.value = _state.value.copy(loading = false, items = it.items, totalKept = it.total_kept)
                },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.toUiText()) },
            )
        }
    }

    /** kind: "tap"（敲一敲）| "heartbeat"（心跳）。 */
    fun send(kind: String) {
        val current = _state.value
        if (current.sending) return
        _state.value = current.copy(sending = true, message = null)
        viewModelScope.launch {
            repository.send(kind).fold(
                onSuccess = { tap ->
                    _state.value = _state.value.copy(
                        sending = false,
                        sentCount = _state.value.sentCount + 1,
                        lastKind = tap.kind,
                        message = uiText(if (tap.kind == "heartbeat") R.string.tap_sent_heartbeat else R.string.tap_sent_tap),
                        messageIsError = false,
                    )
                    // 成功后立即拉取最近记录，把新轻触顶到列表最前。
                    repository.recent().fold(
                        onSuccess = { _state.value = _state.value.copy(items = it.items, totalKept = it.total_kept) },
                        onFailure = { /* 保留旧列表，静默失败 */ },
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(sending = false, message = it.toUiText(), messageIsError = true)
                },
            )
        }
    }

    fun clearMessage() {
        _state.value = _state.value.copy(message = null)
    }
}
