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

package com.lovejournal.app.ui.cottage.games.canvas

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.CanvasArtworkResponse
import com.lovejournal.app.data.repository.CanvasRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CanvasGalleryUiState(
    val loading: Boolean = false,
    val items: List<CanvasArtworkResponse> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    val hasNext: Boolean = false,
    val deletingCaid: String = "",
    val errorMessage: String? = null,
)

@HiltViewModel
class CanvasGalleryViewModel @Inject constructor(
    private val repository: CanvasRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CanvasGalleryUiState())
    val state: StateFlow<CanvasGalleryUiState> = _state.asStateFlow()

    private val _toast = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val toast: SharedFlow<String> = _toast

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, errorMessage = null) }
            repository.listArtworks(page = _state.value.page, pageSize = 20)
                .onSuccess { resp ->
                    _state.update {
                        it.copy(
                            loading = false,
                            items = resp.items,
                            total = resp.total,
                            hasNext = resp.has_next,
                        )
                    }
                }
                .onFailure { err ->
                    _state.update { it.copy(loading = false, errorMessage = err.message ?: "加载失败") }
                }
        }
    }

    fun loadMore() {
        if (_state.value.loading || !_state.value.hasNext) return
        viewModelScope.launch {
            _state.update { it.copy(loading = true, page = it.page + 1) }
            repository.listArtworks(page = _state.value.page, pageSize = 20)
                .onSuccess { resp ->
                    _state.update {
                        it.copy(
                            loading = false,
                            items = it.items + resp.items,
                            total = resp.total,
                            hasNext = resp.has_next,
                        )
                    }
                }
                .onFailure { err ->
                    _state.update { it.copy(loading = false, errorMessage = err.message ?: "加载失败") }
                }
        }
    }

    fun delete(artwork: CanvasArtworkResponse) {
        if (_state.value.deletingCaid.isNotEmpty()) return
        _state.update { it.copy(deletingCaid = artwork.caid) }
        viewModelScope.launch {
            repository.deleteArtwork(artwork.caid)
                .onSuccess {
                    _state.update {
                        it.copy(
                            items = it.items.filterNot { item -> item.caid == artwork.caid },
                            deletingCaid = "",
                        )
                    }
                    _toast.tryEmit("已删除")
                }
                .onFailure { err ->
                    _state.update { it.copy(deletingCaid = "", errorMessage = err.message ?: "删除失败") }
                    _toast.tryEmit(err.message ?: "删除失败")
                }
        }
    }
}
