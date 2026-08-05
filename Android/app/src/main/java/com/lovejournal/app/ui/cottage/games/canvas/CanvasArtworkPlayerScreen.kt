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
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Brush
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import org.json.JSONObject

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CanvasArtworkPlayerScreen(
    caid: String,
    viewModel: CanvasArtworkPlayerViewModel = hiltViewModel(),
    onBack: () -> Unit = {},
) {
    val ui by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(caid) { viewModel.load(caid) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.Brush, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.size(8.dp))
                        Text(
                            text = ui.artwork?.title?.takeIf { it.isNotBlank() } ?: "作品回放",
                            maxLines = 1,
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "返回作品集")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f),
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            when {
                ui.loading -> Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
                ui.errorMessage != null -> Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = ui.errorMessage ?: "加载失败",
                        color = MaterialTheme.colorScheme.error,
                    )
                }
                else -> {
                    // The drawing surface — same 16:10 ratio as the live canvas.
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .aspectRatio(16f / 10f)
                            .background(Color.White, RoundedCornerShape(14.dp))
                            .clip(RoundedCornerShape(14.dp)),
                    ) {
                        ArtworkCanvas(strokesJson = ui.artwork?.strokes_json)
                    }
                    val author = ui.artwork?.author_nickname.orEmpty()
                    val createdAt = ui.artwork?.created_at.orEmpty()
                    Text(
                        text = "由 $author 保存 · ${createdAt}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (!ui.artwork?.collaborators.isNullOrEmpty()) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = "合作者：",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            ui.artwork?.collaborators?.forEach { c ->
                                Surface(
                                    color = MaterialTheme.colorScheme.primaryContainer,
                                    shape = CircleShape,
                                    modifier = Modifier.size(26.dp),
                                ) {
                                    Box(contentAlignment = Alignment.Center) {
                                        Text(
                                            text = c.nickname.take(1).ifBlank { "·" },
                                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = FontWeight.SemiBold,
                                        )
                                    }
                                }
                                Spacer(Modifier.size(4.dp))
                                Text(
                                    text = "${c.nickname}（${c.stroke_count} 笔）",
                                    style = MaterialTheme.typography.labelSmall,
                                )
                                Spacer(Modifier.size(8.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ArtworkCanvas(strokesJson: String?) {
    val parsed = remember(strokesJson) { parseArtworkStrokes(strokesJson) }
    Canvas(modifier = Modifier.fillMaxSize()) {
        // No white-fill: the box above already paints the white background.
        // For each stroke draw the segments. Eraser segments use BlendMode.Clear
        // to match the live canvas behaviour.
        for (stroke in parsed) {
            val color = stroke.color
            val width = stroke.size
            for (seg in stroke.segments) {
                if (seg.eraser) {
                    drawLine(
                        color = Color.Transparent,
                        start = Offset(seg.x0 * size.width, seg.y0 * size.height),
                        end = Offset(seg.x1 * size.width, seg.y1 * size.height),
                        strokeWidth = width,
                        cap = StrokeCap.Round,
                        blendMode = BlendMode.Clear,
                    )
                } else {
                    drawLine(
                        color = color,
                        start = Offset(seg.x0 * size.width, seg.y0 * size.height),
                        end = Offset(seg.x1 * size.width, seg.y1 * size.height),
                        strokeWidth = width,
                        cap = StrokeCap.Round,
                    )
                }
            }
        }
        // Outer border to mirror the live canvas outline.
        drawRect(
            color = Color(0x6694A3B8),
            style = Stroke(width = 1f),
        )
    }
}

private data class ParsedStroke(
    val color: Color,
    val size: Float,
    val segments: List<ParsedSegment>,
)

private data class ParsedSegment(
    val x0: Float, val y0: Float, val x1: Float, val y1: Float,
    val eraser: Boolean,
)

private fun parseArtworkStrokes(json: String?): List<ParsedStroke> {
    if (json.isNullOrBlank()) return emptyList()
    return try {
        val root = JSONObject(json)
        val strokes = root.optJSONArray("strokes") ?: return emptyList()
        val out = mutableListOf<ParsedStroke>()
        for (i in 0 until strokes.length()) {
            val stroke = strokes.optJSONObject(i) ?: continue
            val segs = stroke.optJSONArray("segs") ?: continue
            // The first segment of the stroke carries the brush colour; the
            // web app's stroke format doesn't carry per-segment colour.
            val first = segs.optJSONObject(0)
            val hex = first?.optString("color", "#1e293b") ?: "#1e293b"
            val color = try {
                Color(android.graphics.Color.parseColor(hex))
            } catch (_: Exception) {
                Color(0xFF1E293B)
            }
            val size = (first?.optDouble("size", 4.0) ?: 4.0).toFloat()
            val segList = mutableListOf<ParsedSegment>()
            for (j in 0 until segs.length()) {
                val seg = segs.optJSONObject(j) ?: continue
                segList.add(
                    ParsedSegment(
                        x0 = seg.optDouble("x0", 0.0).toFloat(),
                        y0 = seg.optDouble("y0", 0.0).toFloat(),
                        x1 = seg.optDouble("x1", 0.0).toFloat(),
                        y1 = seg.optDouble("y1", 0.0).toFloat(),
                        eraser = seg.optBoolean("eraser", false),
                    ),
                )
            }
            out.add(ParsedStroke(color = color, size = size, segments = segList))
        }
        out
    } catch (_: Exception) {
        emptyList()
    }
}
