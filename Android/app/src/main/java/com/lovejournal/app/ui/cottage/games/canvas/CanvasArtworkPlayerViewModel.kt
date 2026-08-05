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
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CanvasArtworkPlayerUiState(
    val loading: Boolean = true,
    val artwork: CanvasArtworkResponse? = null,
    val strokes: List<Pair<Float, List<FloatArray>>> = emptyList(),
    val errorMessage: String? = null,
)

@HiltViewModel
class CanvasArtworkPlayerViewModel @Inject constructor(
    private val repository: CanvasRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CanvasArtworkPlayerUiState())
    val state: StateFlow<CanvasArtworkPlayerUiState> = _state.asStateFlow()

    fun load(caid: String) {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, errorMessage = null) }
            repository.getArtwork(caid)
                .onSuccess { art ->
                    val parsed = parseStrokes(art.strokes_json)
                    _state.update {
                        it.copy(loading = false, artwork = art, strokes = parsed)
                    }
                }
                .onFailure { err ->
                    _state.update { it.copy(loading = false, errorMessage = err.message ?: "加载失败") }
                }
        }
    }

    /**
     * Decode the persisted JSON into a list of (color, segments) pairs that
     * the read-only player can render. Returns empty on parse failure so
     * the screen still loads even if the legacy format differs.
     */
    private fun parseStrokes(json: String?): List<Pair<Float, List<FloatArray>>> {
        if (json.isNullOrBlank()) return emptyList()
        return try {
            val data = org.json.JSONObject(json)
            val strokes = data.optJSONArray("strokes") ?: return emptyList()
            val out = mutableListOf<Pair<Float, List<FloatArray>>>()
            for (i in 0 until strokes.length()) {
                val stroke = strokes.optJSONObject(i) ?: continue
                val segs = stroke.optJSONArray("segs") ?: continue
                val segments = mutableListOf<FloatArray>()
                for (j in 0 until segs.length()) {
                    val seg = segs.optJSONObject(j) ?: continue
                    segments.add(
                        floatArrayOf(
                            seg.optDouble("x0", 0.0).toFloat(),
                            seg.optDouble("y0", 0.0).toFloat(),
                            seg.optDouble("x1", 0.0).toFloat(),
                            seg.optDouble("y1", 0.0).toFloat(),
                        ),
                    )
                }
                out.add(0f to segments) // color rendered via a single helper in the screen
            }
            out
        } catch (_: Exception) {
            emptyList()
        }
    }
}
