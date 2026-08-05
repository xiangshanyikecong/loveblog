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

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.ui.Alignment
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.data.remote.dto.GameStateResponse
import com.lovejournal.app.ui.components.LovePage

@Composable
fun GameScreen(gameKey: String, viewModel: GameViewModel = hiltViewModel()) {
    LaunchedEffect(gameKey) { viewModel.start(gameKey) }
    val ui by viewModel.state.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(Unit) { viewModel.toast.collect { snackbar.showSnackbar(it) } }

    val s = ui.state

    Scaffold(snackbarHost = { SnackbarHost(snackbar) }) { padding ->
        LovePage(modifier = Modifier.padding(padding)) {
        Column(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text(statusText(ui.connected, s, ui.selfUid), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)

            if (s != null && s.size > 0) {
                if (gameKey == "memory" || gameKey == "linklink") {
                    TileBoard(s, gameKey) { x, y -> viewModel.tapCell(x, y) }
                } else {
                    Board(s) { x, y -> viewModel.tapCell(x, y) }
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { viewModel.newGame() }) { Text(if (s?.phase == "playing") "重开" else "新对局") }
                OutlinedButton(onClick = { viewModel.surrender() }, enabled = s?.phase == "playing") { Text("认输") }
                OutlinedButton(onClick = { viewModel.requestUndo() }, enabled = s?.phase == "playing") { Text("悔棋") }
                OutlinedButton(onClick = { viewModel.invite() }) { Text("邀请") }
            }

            if (s?.undo_request_by != null && s.undo_request_by != ui.selfUid && s.phase == "playing") {
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("对方请求悔棋")
                    TextButton(onClick = { viewModel.respondUndo(true) }) { Text("同意") }
                    TextButton(onClick = { viewModel.respondUndo(false) }) { Text("拒绝") }
                }
            }

            if (ui.stats.isNotEmpty()) {
                Text(
                    ui.stats.joinToString("   ") { "${it.nickname} ${it.wins}胜" },
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        }
    }
}

@Composable
private fun TileBoard(s: GameStateResponse, gameKey: String, onTap: (Int, Int) -> Unit) {
    val cols = s.cols ?: s.size
    val rows = s.rows ?: ((s.tiles ?: s.cells).size / cols).coerceAtLeast(1)
    val values = s.tiles ?: s.cells
    val states = s.states.orEmpty()
    val icons = s.icons.orEmpty()
    LazyVerticalGrid(
        columns = GridCells.Fixed(cols),
        modifier = Modifier.fillMaxWidth().aspectRatio(cols.toFloat() / rows.toFloat()),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
        userScrollEnabled = false,
    ) {
        itemsIndexed(values) { index, value ->
            val x = index % cols
            val y = index / cols
            val tileState = states.getOrNull(index) ?: if (value == 0) 2 else 1
            val visible = gameKey == "linklink" || tileState > 0
            val removed = value == 0 || tileState == 2
            val label = if (removed) "" else if (visible) icons.getOrNull(value) ?: icons.getOrNull(value - 1) ?: value.toString() else "?"
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1f)
                    .background(if (removed) MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.25f) else MaterialTheme.colorScheme.primaryContainer, MaterialTheme.shapes.small)
                    .clickable(enabled = !removed && s.phase == "playing") { onTap(x, y) },
                contentAlignment = Alignment.Center,
            ) {
                Text(label, style = MaterialTheme.typography.titleLarge)
            }
        }
    }
}

private fun statusText(connected: Boolean, s: GameStateResponse?, selfUid: String?): String {
    if (!connected) return "连接中…"
    if (s == null) return "加载中…"
    return when (s.phase) {
        "waiting" -> "等待开始，点「新对局」"
        "playing" -> if (s.turn_uid == selfUid) "轮到你落子" else "对方思考中…"
        "finished" -> when {
            s.winner == "draw" -> "平局 🤝"
            (s.winner == "black" && s.black_uid == selfUid) ||
                (s.winner == "white" && s.white_uid == selfUid) -> "你赢了 🎉"
            else -> "这局对方赢了，再来一局？"
        }
        else -> ""
    }
}

@Composable
private fun Board(s: GameStateResponse, onTap: (Int, Int) -> Unit) {
    val n = s.size
    val lineColor = MaterialTheme.colorScheme.outline
    val blackStone = Color(0xFF222222)
    val whiteStone = Color(0xFFFAFAFA)
    val boardColor = Color(0xFFE9C188)
    val lastColor = MaterialTheme.colorScheme.primary

    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .aspectRatio(1f)
            .pointerInput(n) {
                detectTapGestures { offset ->
                    val cell = size.width.toFloat() / n
                    if (cell <= 0f) return@detectTapGestures
                    val x = (offset.x / cell).toInt().coerceIn(0, n - 1)
                    val y = (offset.y / cell).toInt().coerceIn(0, n - 1)
                    onTap(x, y)
                }
            },
    ) {
        val cell = size.width / n
        drawRect(color = boardColor)
        for (i in 0..n) {
            val p = i * cell
            drawLine(lineColor, Offset(p, 0f), Offset(p, size.height), strokeWidth = 1.5f)
            drawLine(lineColor, Offset(0f, p), Offset(size.width, p), strokeWidth = 1.5f)
        }
        val r = cell * 0.40f
        for (y in 0 until n) {
            for (x in 0 until n) {
                when (s.cells.getOrElse(y * n + x) { 0 }) {
                    1 -> drawCircle(blackStone, r, Offset((x + 0.5f) * cell, (y + 0.5f) * cell))
                    2 -> {
                        val center = Offset((x + 0.5f) * cell, (y + 0.5f) * cell)
                        drawCircle(whiteStone, r, center)
                        drawCircle(lineColor, r, center, style = Stroke(width = 1.5f))
                    }
                }
            }
        }
        s.last_move?.let { lm ->
            drawCircle(lastColor, cell * 0.12f, Offset((lm.x + 0.5f) * cell, (lm.y + 0.5f) * cell))
        }
    }
}
