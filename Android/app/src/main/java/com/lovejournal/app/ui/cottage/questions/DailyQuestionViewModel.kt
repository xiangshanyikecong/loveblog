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

package com.lovejournal.app.ui.cottage.questions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.dto.DailyQuestionResponse
import com.lovejournal.app.data.repository.DailyQuestionRepository
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DailyQuestionUiState(
    val loading: Boolean = false,
    val question: DailyQuestionResponse? = null,
    val error: UiText? = null,
    val submitting: Boolean = false,
)

@HiltViewModel
class DailyQuestionViewModel @Inject constructor(
    private val repository: DailyQuestionRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(DailyQuestionUiState())
    val state: StateFlow<DailyQuestionUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<UiText?>(null)
    val message: StateFlow<UiText?> = _message.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.today().fold(
                onSuccess = { _state.value = DailyQuestionUiState(question = it) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.toUiText()) },
            )
        }
    }

    /** Set today's question (only allowed when none exists yet). */
    fun createToday(prompt: String) {
        if (prompt.isBlank()) {
            _message.value = uiText(R.string.question_error_prompt_required)
            return
        }
        _state.value = _state.value.copy(submitting = true)
        viewModelScope.launch {
            repository.create(prompt.trim()).fold(
                onSuccess = { _state.value = DailyQuestionUiState(question = it); _message.value = uiText(R.string.msg_published) },
                onFailure = { _state.value = _state.value.copy(submitting = false); _message.value = it.toUiText() },
            )
        }
    }

    fun answer(content: String) {
        val qid = _state.value.question?.qid ?: return
        if (content.isBlank()) {
            _message.value = uiText(R.string.question_error_answer_required)
            return
        }
        _state.value = _state.value.copy(submitting = true)
        viewModelScope.launch {
            repository.answer(qid, content.trim()).fold(
                onSuccess = {
                    _state.value = DailyQuestionUiState(question = it)
                    _message.value = if (it.revealed) uiText(R.string.question_msg_revealed) else uiText(R.string.question_msg_answered)
                },
                onFailure = { _state.value = _state.value.copy(submitting = false); _message.value = it.toUiText() },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
