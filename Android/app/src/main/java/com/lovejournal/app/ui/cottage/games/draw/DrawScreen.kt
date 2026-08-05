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

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive
import com.lovejournal.app.ui.components.LovePage

@Composable
fun DrawScreen(viewModel: DrawViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    var guess by remember { mutableStateOf("") }
    var last by remember { mutableStateOf<Offset?>(null) }
    LaunchedEffect(Unit) { viewModel.toast.collect { snackbar.showSnackbar(it) } }
    val snapshot = state.snapshot
    val drawerUid = snapshot?.get("drawer_uid")?.jsonPrimitive?.contentOrNull
    val phase = snapshot?.get("phase")?.jsonPrimitive?.contentOrNull ?: "waiting"
    val canDraw = phase == "drawing" && drawerUid == state.selfUid
    Scaffold(snackbarHost = { SnackbarHost(snackbar) }) { padding -> LovePage(modifier = Modifier.padding(padding)) { Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(if (!state.connected) "连接中…" else if (canDraw) "轮到你画" else if (phase == "drawing") "猜一猜：${snapshot?.get("word_mask")?.jsonPrimitive?.contentOrNull ?: ""}" else "你画我猜", style = MaterialTheme.typography.titleLarge)
        Canvas(Modifier.fillMaxWidth().aspectRatio(1.5f).pointerInput(canDraw) { if (canDraw) detectDragGestures(onDragStart = { last = it }, onDragEnd = { last = null }) { change, _ -> val previous = last ?: change.position; val current = change.position; viewModel.stroke(DrawSegment(previous.x / size.width, previous.y / size.height, current.x / size.width, current.y / size.height)); last = current } }) {
            drawRect(Color.White); state.segments.forEach { drawLine(Color(0xFF1E293B), Offset(it.x0 * size.width, it.y0 * size.height), Offset(it.x1 * size.width, it.y1 * size.height), strokeWidth = 5f) }; drawRect(Color.Gray, style = Stroke(1f))
        }
        if (!canDraw && phase == "drawing") Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { OutlinedTextField(guess, { guess = it }, label = { Text("输入猜测") }, modifier = Modifier.weight(1f)); Button(onClick = { viewModel.guess(guess); guess = "" }) { Text("猜") } }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { if (phase == "waiting" || phase == "finished") Button(onClick = viewModel::newGame) { Text("开始") }; if (phase == "round_end") Button(onClick = viewModel::nextRound) { Text("下一回合") }; if (canDraw) OutlinedButton(onClick = viewModel::clear) { Text("清空") }; OutlinedButton(onClick = viewModel::invite) { Text("邀请") } }
        snapshot?.get("round")?.jsonPrimitive?.intOrNull?.let { Text("第 $it 回合") }
    } } }
}
