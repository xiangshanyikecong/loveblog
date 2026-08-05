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

package com.lovejournal.app.ui.cottage.games.draw

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.repository.DrawRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import javax.inject.Inject

data class DrawSegment(val x0: Float, val y0: Float, val x1: Float, val y1: Float)
data class DrawUiState(val connected: Boolean = false, val selfUid: String? = null, val snapshot: JsonObject? = null, val segments: List<DrawSegment> = emptyList())

@HiltViewModel
class DrawViewModel @Inject constructor(private val repository: DrawRepository, session: SessionManager) : ViewModel() {
    private val _state = MutableStateFlow(DrawUiState())
    val state: StateFlow<DrawUiState> = _state.asStateFlow()
    private val _toast = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val toast: SharedFlow<String> = _toast
    init {
        viewModelScope.launch { _state.value = _state.value.copy(selfUid = session.sessionFlow.first().uid) }
        viewModelScope.launch { repository.state().onSuccess { _state.value = _state.value.copy(snapshot = it) } }
        viewModelScope.launch { repository.connected.collect { _state.value = _state.value.copy(connected = it) } }
        viewModelScope.launch { repository.events.collect(::handle) }
        repository.connect()
    }
    private fun handle(event: JsonObject) {
        val type = event["type"]?.jsonPrimitive?.contentOrNull ?: return
        val payload = event["payload"]?.jsonObject
        when (type) {
            "STATE", "ROUND_END", "GAME_OVER" -> if (payload != null) _state.value = _state.value.copy(snapshot = payload, segments = if (type == "STATE") emptyList() else _state.value.segments)
            "CLEAR" -> _state.value = _state.value.copy(segments = emptyList())
            "STROKE" -> {
                val segs = payload?.get("segs")?.toString() ?: return
                Regex("\\\"x0\\\":([0-9.]+).*?\\\"y0\\\":([0-9.]+).*?\\\"x1\\\":([0-9.]+).*?\\\"y1\\\":([0-9.]+)").findAll(segs).forEach { m ->
                    _state.value = _state.value.copy(segments = _state.value.segments + DrawSegment(m.groupValues[1].toFloat(), m.groupValues[2].toFloat(), m.groupValues[3].toFloat(), m.groupValues[4].toFloat()))
                }
            }
            "ERROR" -> _toast.tryEmit(payload?.get("message")?.jsonPrimitive?.contentOrNull ?: "操作失败")
        }
    }
    fun stroke(segment: DrawSegment) { _state.value = _state.value.copy(segments = _state.value.segments + segment); repository.send("""{"type":"STROKE","payload":{"segs":[{"sid":"android","x0":${segment.x0},"y0":${segment.y0},"x1":${segment.x1},"y1":${segment.y1},"color":"#1e293b","size":5,"eraser":false}]}}""") }
    fun clear() { _state.value = _state.value.copy(segments = emptyList()); repository.send("""{"type":"CLEAR","payload":{}}""") }
    fun newGame() = repository.send("""{"type":"NEW_GAME","payload":{}}""")
    fun nextRound() = repository.send("""{"type":"NEXT_ROUND","payload":{}}""")
    fun guess(text: String) { if (text.isNotBlank()) repository.send("""{"type":"GUESS","payload":{"text":${jsonString(text.trim())}}}""") }
    fun invite() = viewModelScope.launch { repository.invite().fold(onSuccess = { _toast.tryEmit("已邀请对方") }, onFailure = { _toast.tryEmit(it.message ?: "邀请失败") }) }
    override fun onCleared() { repository.disconnect(); super.onCleared() }
    private fun jsonString(value: String): String = "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
}
