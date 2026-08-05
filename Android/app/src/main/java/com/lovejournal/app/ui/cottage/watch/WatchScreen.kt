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

package com.lovejournal.app.ui.cottage.watch

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.OptIn
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.BookmarkAdd
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.media3.common.util.UnstableApi
import androidx.media3.ui.PlayerView
import com.lovejournal.app.data.remote.dto.WatchBookmark
import com.lovejournal.app.data.remote.dto.WatchSourceResponse
import com.lovejournal.app.ui.components.LovePage

@OptIn(UnstableApi::class)
@Composable
fun WatchScreen(viewModel: WatchViewModel = hiltViewModel()) {
    val ui by viewModel.state.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    var addOpen by remember { mutableStateOf(false) }
    var bookmarkOpen by remember { mutableStateOf(false) }
    val videoPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let { viewModel.uploadVideo(it) }
    }
    LaunchedEffect(Unit) { viewModel.toast.collect { snackbar.showSnackbar(it) } }

    Scaffold(snackbarHost = { SnackbarHost(snackbar) }) { padding ->
        LovePage(modifier = Modifier.padding(padding)) {
            Column(modifier = Modifier.fillMaxSize()) {
                // ── Status header ──────────────────────────────────────────
                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    StatusDot(connected = ui.connected, partnerOnline = ui.partnerOnline)
                    Spacer(Modifier.size(6.dp))
                    Text(
                        text = when {
                            !ui.connected -> "正在连接…"
                            ui.partnerOnline -> "已连接 · 对方在看"
                            else -> "已连接 · 对方暂时不在线"
                        },
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.size(8.dp))

                // ── Player ─────────────────────────────────────────────────
                AndroidView(
                    factory = { ctx ->
                        PlayerView(ctx).apply {
                            player = viewModel.player
                            useController = true
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(16f / 9f)
                        .background(Color.Black, RoundedCornerShape(14.dp)),
                )
                Spacer(Modifier.size(10.dp))

                // ── Playback row ──────────────────────────────────────────
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Button(onClick = { viewModel.togglePlay() }) {
                        Icon(
                            if (ui.isPlaying) Icons.Filled.Close else Icons.Filled.PlayArrow,
                            contentDescription = if (ui.isPlaying) "暂停" else "播放",
                            modifier = Modifier.size(18.dp),
                        )
                        Spacer(Modifier.size(6.dp))
                        Text(if (ui.isPlaying) "暂停" else "播放")
                    }
                    OutlinedButton(onClick = { viewModel.seekBy(-10_000) }) { Text("−10s") }
                    OutlinedButton(onClick = { viewModel.seekBy(10_000) }) { Text("+10s") }
                    FilledTonalButton(onClick = { viewModel.invite() }) { Text("邀请") }
                }
                Spacer(Modifier.size(8.dp))

                // ── Title / resume pill ────────────────────────────────────
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = ui.currentTitle ?: "从下面片库选一部一起看吧",
                        style = MaterialTheme.typography.titleSmall.copy(fontWeight = FontWeight.SemiBold),
                        modifier = Modifier.weight(1f),
                    )
                    if (ui.currentWsid != null) {
                        AssistChip(
                            onClick = { bookmarkOpen = true },
                            label = { Text("书签 ${ui.currentBookmarks.size}") },
                            leadingIcon = {
                                Icon(
                                    Icons.Filled.BookmarkAdd,
                                    contentDescription = null,
                                    modifier = Modifier.size(18.dp),
                                )
                            },
                            colors = AssistChipDefaults.assistChipColors(),
                        )
                    }
                }
                HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
                Spacer(Modifier.size(6.dp))

                // ── Library list ──────────────────────────────────────────
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("片库", style = MaterialTheme.typography.titleMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        TextButton(
                            onClick = { videoPicker.launch(arrayOf("video/*")) },
                            enabled = !ui.uploading,
                        ) {
                            if (ui.uploading) {
                                CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                            } else {
                                Text("上传视频")
                            }
                        }
                        TextButton(onClick = { addOpen = true }) {
                            Icon(Icons.Filled.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.size(4.dp))
                            Text("添加直链")
                        }
                    }
                }

                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(ui.sources, key = { it.wsid }) { src ->
                        SourceRow(
                            src = src,
                            deleting = ui.deletingWsid == src.wsid,
                            isCurrent = src.wsid == ui.currentWsid,
                            onPlay = { viewModel.loadSource(src) },
                            onDelete = { viewModel.deleteSource(src) },
                        )
                    }
                }
            }
        }
    }

    if (addOpen) {
        AddSourceDialog(
            onDismiss = { addOpen = false },
            onAdd = { title, url -> viewModel.addSource(title, url); addOpen = false },
        )
    }

    if (bookmarkOpen && ui.currentWsid != null) {
        BookmarksDialog(
            bookmarks = ui.currentBookmarks,
            formatTime = viewModel::formatTime,
            onDismiss = { bookmarkOpen = false },
            onAdd = { viewModel.addBookmark() },
            onJump = { viewModel.jumpToBookmark(it); bookmarkOpen = false },
            onDelete = { viewModel.deleteBookmark(it) },
        )
    }
}

@Composable
private fun StatusDot(connected: Boolean, partnerOnline: Boolean) {
    val color = when {
        !connected -> Color(0xFF9CA3AF)
        partnerOnline -> Color(0xFF22C55E)
        else -> Color(0xFFF59E0B)
    }
    Box(
        Modifier
            .size(10.dp)
            .background(color, CircleShape),
    )
}

@Composable
private fun SourceRow(
    src: WatchSourceResponse,
    deleting: Boolean,
    isCurrent: Boolean,
    onPlay: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onPlay),
        colors = CardDefaults.cardColors(
            containerColor = if (isCurrent)
                MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f)
            else
                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f),
        ),
        shape = RoundedCornerShape(14.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(src.title, style = MaterialTheme.typography.titleSmall.copy(fontWeight = FontWeight.SemiBold))
                    if (isCurrent) {
                        Spacer(Modifier.size(8.dp))
                        AssistChip(
                            onClick = {},
                            label = { Text("播放中") },
                            colors = AssistChipDefaults.assistChipColors(
                                containerColor = MaterialTheme.colorScheme.primary,
                                labelColor = MaterialTheme.colorScheme.onPrimary,
                            ),
                        )
                    }
                }
                Spacer(Modifier.size(2.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        if (src.kind == "upload") "本地上传" else "直链",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (src.last_position_ms > 0) {
                        Text(
                            "上次看到 ${viewModelFormatTime(src.last_position_ms)}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Medium,
                        )
                    }
                    if (src.bookmarks.isNotEmpty()) {
                        Text(
                            "🔖 ${src.bookmarks.size}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            TextButton(onClick = onDelete, enabled = !deleting) {
                Text(if (deleting) "删除中…" else "删除")
            }
        }
    }
}

@Composable
private fun BookmarksDialog(
    bookmarks: List<WatchBookmark>,
    formatTime: (Long) -> String,
    onDismiss: () -> Unit,
    onAdd: () -> Unit,
    onJump: (WatchBookmark) -> Unit,
    onDelete: (WatchBookmark) -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.BookmarkAdd, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.size(8.dp))
                Text("书签")
            }
        },
        text = {
            Column {
                Button(
                    onClick = onAdd,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Filled.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.size(6.dp))
                    Text("在当前进度添加书签")
                }
                Spacer(Modifier.size(12.dp))
                if (bookmarks.isEmpty()) {
                    Text(
                        "还没有书签。\n看到心动的一幕，点上面按钮存个位置，随时秒跳回来。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 360.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        items(bookmarks, key = { it.bid }) { bm ->
                            BookmarkRow(
                                bm = bm,
                                formatTime = formatTime,
                                onJump = { onJump(bm) },
                                onDelete = { onDelete(bm) },
                            )
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("完成") } },
    )
}

@Composable
private fun BookmarkRow(
    bm: WatchBookmark,
    formatTime: (Long) -> String,
    onJump: () -> Unit,
    onDelete: () -> Unit,
) {
    Surface(
        color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.5f),
        shape = RoundedCornerShape(10.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    bm.label.ifBlank { "未命名片段" },
                    style = MaterialTheme.typography.bodyMedium,
                )
                Text(
                    formatTime(bm.position_ms),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            TextButton(onClick = onJump) { Text("跳到") }
            IconButton(onClick = onDelete) {
                Icon(
                    Icons.Filled.Close,
                    contentDescription = "删除书签",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun AddSourceDialog(onDismiss: () -> Unit, onAdd: (String, String) -> Unit) {
    var title by remember { mutableStateOf("") }
    var url by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加片源（直链）") },
        text = {
            Column {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("标题") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.size(8.dp))
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it },
                    label = { Text("视频直链 http(s)://") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onAdd(title, url) }) { Text("添加") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

// Local helper so SourceRow doesn't need a VM injected just for time formatting.
@Composable
private fun viewModelFormatTime(ms: Long): String {
    val total = (ms / 1000).coerceAtLeast(0)
    val h = total / 3600
    val m = (total % 3600) / 60
    val s = total % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
}
