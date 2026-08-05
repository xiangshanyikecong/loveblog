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

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

private val palette = listOf(
    "#1e293b", "#ef4444", "#f59e0b", "#10b981",
    "#3b82f6", "#a855f7", "#ec4899", "#ffffff",
)

@Composable
fun CanvasScreen(
    viewModel: CanvasViewModel = hiltViewModel(),
    onOpenGallery: () -> Unit = {},
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    val context = LocalContext.current

    LaunchedEffect(Unit) {
        viewModel.toast.collect { snackbar.showSnackbar(it) }
    }

    var currentSid by remember { mutableStateOf<String?>(null) }
    var lastPos by remember { mutableStateOf<Offset?>(null) }
    var canvasSize by remember { mutableStateOf(IntSize.Zero) }

    Scaffold(snackbarHost = { SnackbarHost(snackbar) }) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            // ── Header ──────────────────────────────────────────────────────
            Row(
                Modifier.fillMaxWidth().padding(top = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("协作画板", style = MaterialTheme.typography.titleLarge)
                Text(
                    if (state.partnerOnline) "对方在线" else "对方不在线",
                    style = MaterialTheme.typography.labelSmall,
                    color = if (state.partnerOnline) Color(0xFF16A34A) else Color(0xFF64748B),
                    modifier = Modifier
                        .background(
                            if (state.partnerOnline) Color(0x3316A34A) else Color(0x3364748B),
                            MaterialTheme.shapes.small,
                        )
                        .padding(horizontal = 10.dp, vertical = 4.dp),
                )
            }
            Text(
                "和 Ta 一起在同一块画布上涂鸦，落笔实时同步。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            // ── Color palette + size slider ─────────────────────────────────
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                palette.forEach { c ->
                    Box(
                        Modifier
                            .size(24.dp)
                            .clip(CircleShape)
                            .background(parseColor(c))
                            .border(
                                width = if (state.color == c && !state.eraser) 3.dp else 1.5.dp,
                                color = if (state.color == c && !state.eraser) Color(0xFF0F172A) else Color(0x6694A3B8),
                                shape = CircleShape,
                            )
                            .clickable { viewModel.setColor(c) },
                    )
                }
                Spacer(Modifier.width(8.dp))
                Text("粗细", style = MaterialTheme.typography.labelSmall)
                Slider(
                    value = state.size,
                    onValueChange = { viewModel.setSize(it) },
                    valueRange = 1f..40f,
                    modifier = Modifier.width(80.dp),
                    colors = SliderDefaults.colors(
                        thumbColor = MaterialTheme.colorScheme.primary,
                        activeTrackColor = MaterialTheme.colorScheme.primary,
                    ),
                )
                Text("${state.size.toInt()}", style = MaterialTheme.typography.labelSmall, modifier = Modifier.width(20.dp))
            }

            // ── Tool buttons ────────────────────────────────────────────────
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                TextButton(
                    onClick = { viewModel.toggleEraser() },
                    modifier = Modifier.then(
                        if (state.eraser) Modifier.background(Color(0xFFFDE68A), MaterialTheme.shapes.small)
                        else Modifier,
                    ),
                ) { Text(if (state.eraser) "橡皮(开)" else "橡皮") }
                OutlinedButton(onClick = { viewModel.undo() }) { Text("撤销") }
                OutlinedButton(onClick = { viewModel.clear() }) { Text("清空") }
                OutlinedButton(
                    onClick = { viewModel.saveToTimeline(context.cacheDir) },
                    enabled = !state.saving,
                ) { Text(if (state.saving) "保存中…" else "保存到时间轴") }
                OutlinedButton(
                    onClick = { viewModel.saveToGallery(context.cacheDir) },
                    enabled = !state.savingToGallery,
                ) { Text(if (state.savingToGallery) "保存中…" else "存入作品集") }
                OutlinedButton(onClick = { onOpenGallery() }) { Text("作品集") }
            }

            // ── Canvas (no scroll — fills remaining space) ──────────────────
            Box(
                Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(bottom = 8.dp)
                    .onSizeChanged { canvasSize = it },
            ) {
                Canvas(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(Color.White, MaterialTheme.shapes.medium)
                        .border(1.dp, Color(0x6694A3B8), MaterialTheme.shapes.medium)
                        .pointerInput(Unit) {
                            detectDragGestures(
                                onDragStart = { offset ->
                                    val sz = size
                                    val x = (offset.x / sz.width).coerceIn(0f, 1f)
                                    val y = (offset.y / sz.height).coerceIn(0f, 1f)
                                    val sid = viewModel.newSid()
                                    currentSid = sid
                                    lastPos = Offset(x, y)
                                    viewModel.onStrokeStart(x, y, sid)
                                },
                                onDragEnd = {
                                    currentSid = null
                                    lastPos = null
                                },
                                onDragCancel = {
                                    currentSid = null
                                    lastPos = null
                                },
                            ) { change, _ ->
                                val sz = size
                                val x = (change.position.x / sz.width).coerceIn(0f, 1f)
                                val y = (change.position.y / sz.height).coerceIn(0f, 1f)
                                val prev = lastPos ?: Offset(x, y)
                                viewModel.onStrokeMove(x, y, currentSid ?: "", prev.x, prev.y)
                                lastPos = Offset(x, y)
                                viewModel.onCursorMove(x, y)
                            }
                        },
                ) {
                    drawRect(Color.White)
                    for (stroke in state.strokes) {
                        for (seg in stroke.segs) {
                            val start = Offset(seg.x0 * size.width, seg.y0 * size.height)
                            val end = Offset(seg.x1 * size.width, seg.y1 * size.height)
                            val sw = seg.size * (size.width / 960f)
                            if (seg.eraser) {
                                drawLine(
                                    color = Color.Transparent,
                                    start = start, end = end,
                                    strokeWidth = sw,
                                    cap = androidx.compose.ui.graphics.StrokeCap.Round,
                                    blendMode = BlendMode.Clear,
                                )
                            } else {
                                drawLine(
                                    color = parseColor(seg.color),
                                    start = start, end = end,
                                    strokeWidth = sw,
                                    cap = androidx.compose.ui.graphics.StrokeCap.Round,
                                )
                            }
                        }
                    }
                    drawRect(Color(0x6694A3B8), style = Stroke(1f))
                }

                // Ghost cursor — percentage-positioned inside the canvas Box
                if (state.remoteCursor.visible) {
                    Box(
                        Modifier
                            .offset {
                                IntOffset(
                                    (state.remoteCursor.x * canvasSize.width - 7.dp.toPx()).toInt(),
                                    (state.remoteCursor.y * canvasSize.height - 7.dp.toPx()).toInt(),
                                )
                            }
                            .size(14.dp)
                            .clip(CircleShape)
                            .background(Color(0x40EC4899))
                            .border(2.dp, Color(0xFFEC4899), CircleShape),
                    )
                }
            }
        }
    }
}

private fun parseColor(hex: String): Color = try {
    Color(android.graphics.Color.parseColor(hex))
} catch (_: Exception) {
    Color(0xFF1E293B)
}
