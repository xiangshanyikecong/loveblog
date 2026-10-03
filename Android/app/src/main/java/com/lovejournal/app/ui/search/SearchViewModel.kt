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

package com.lovejournal.app.ui.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.AiSemanticSearchResult
import com.lovejournal.app.data.remote.dto.SearchResultItem
import com.lovejournal.app.data.repository.AiFeatures
import com.lovejournal.app.data.repository.AiRepository
import com.lovejournal.app.data.repository.SearchRepository
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SearchUiState(
    val query: String = "",
    val loading: Boolean = false,
    val items: List<SearchResultItem> = emptyList(),
    val total: Int = 0,
    val searched: Boolean = false,
    val error: UiText? = null,
    // ---- AI 语义搜索（status.enabled 且具备 semantic_search 特性时显示开关）----
    val aiEnabled: Boolean = false,
    val aiMode: Boolean = false,
    val aiLoading: Boolean = false,
    val aiResults: List<AiSemanticSearchResult> = emptyList(),
    val aiIndexedCount: Int = 0,
    val aiError: UiText? = null,
)

@HiltViewModel
class SearchViewModel @Inject constructor(
    private val repository: SearchRepository,
    private val aiRepository: AiRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(SearchUiState())
    val state: StateFlow<SearchUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            aiRepository.status().onSuccess {
                _state.value = _state.value.copy(aiEnabled = it.enabled && it.features.contains(AiFeatures.SEMANTIC_SEARCH))
            }
        }
    }

    fun updateQuery(query: String) {
        _state.value = _state.value.copy(query = query)
    }

    /** AI 语义搜索开关：关闭时清空 AI 结果，回到普通关键词搜索。 */
    fun setAiMode(enabled: Boolean) {
        _state.value = _state.value.copy(aiMode = enabled, aiError = null, aiResults = emptyList(), aiIndexedCount = 0)
    }

    fun search() {
        val query = _state.value.query.trim()
        if (query.isEmpty()) return
        if (_state.value.aiMode) {
            searchSemantic(query)
            return
        }
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.search(query).fold(
                onSuccess = {
                    _state.value = _state.value.copy(
                        loading = false,
                        items = it.items,
                        total = it.total,
                        searched = true,
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = it.toUiText(),
                        searched = true,
                    )
                },
            )
        }
    }

    private fun searchSemantic(query: String) {
        _state.value = _state.value.copy(aiLoading = true, aiError = null)
        viewModelScope.launch {
            aiRepository.search(query).fold(
                onSuccess = {
                    _state.value = _state.value.copy(aiLoading = false, aiResults = it.results, aiIndexedCount = it.indexed_count)
                },
                onFailure = {
                    _state.value = _state.value.copy(aiLoading = false, aiError = it.toUiText())
                },
            )
        }
    }
}
