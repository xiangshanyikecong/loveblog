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

package com.lovejournal.app.ui.cottage.games

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.dto.GamePlayerStat
import com.lovejournal.app.data.remote.dto.GameStateResponse
import com.lovejournal.app.data.repository.GameRepository
import com.lovejournal.app.data.repository.GameWsEvent
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class GameUiState(
    val state: GameStateResponse? = null,
    val selfUid: String? = null,
    val connected: Boolean = false,
    val stats: List<GamePlayerStat> = emptyList(),
    val gameKey: String = "gomoku",
)

@HiltViewModel
class GameViewModel @Inject constructor(
    private val repository: GameRepository,
    private val session: SessionManager,
) : ViewModel() {

    private val _state = MutableStateFlow(GameUiState())
    val state: StateFlow<GameUiState> = _state.asStateFlow()

    private val _toast = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val toast: SharedFlow<String> = _toast.asSharedFlow()

    private var started = false

    fun start(gameKey: String) {
        if (started) return
        started = true
        _state.update { it.copy(gameKey = gameKey) }
        viewModelScope.launch { _state.update { it.copy(selfUid = session.sessionFlow.first().uid) } }
        viewModelScope.launch {
            repository.events.collect { ev ->
                when (ev) {
                    is GameWsEvent.State -> _state.update { it.copy(state = ev.state) }
                    is GameWsEvent.Connection -> _state.update { it.copy(connected = ev.connected) }
                    is GameWsEvent.Error -> _toast.tryEmit(ev.message)
                    is GameWsEvent.Emote -> _toast.tryEmit("${ev.fromNickname} ${ev.emote}")
                    is GameWsEvent.UndoResult -> _toast.tryEmit(if (ev.accepted) "对方同意了悔棋" else "对方拒绝了悔棋")
                }
            }
        }
        repository.connect(gameKey)
        loadStats()
    }

    private fun loadStats() {
        viewModelScope.launch {
            repository.matches(_state.value.gameKey).onSuccess { res ->
                _state.update { it.copy(stats = res.stats) }
            }
        }
    }

    fun tapCell(x: Int, y: Int) {
        val s = _state.value.state ?: return
        if (s.phase != "playing") return
        if (s.turn_uid != _state.value.selfUid) {
            _toast.tryEmit("还没轮到你")
            return
        }
        val idx = y * s.size + x
        if (idx in s.cells.indices && s.cells[idx] != 0) return
        repository.move(x, y)
    }

    fun newGame() = repository.newGame(defaultSize(_state.value.gameKey))
    fun surrender() = repository.surrender()
    fun requestUndo() = repository.requestUndo()
    fun respondUndo(accept: Boolean) = repository.respondUndo(accept)

    fun invite() {
        viewModelScope.launch {
            repository.invite(_state.value.gameKey)
                .onSuccess { _toast.tryEmit("已邀请对方来玩") }
        }
    }

    private fun defaultSize(key: String): Int = when (key) {
        "tictactoe" -> 3
        "reversi" -> 8
        else -> 15
    }

    override fun onCleared() {
        repository.disconnect()
        super.onCleared()
    }
}
