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

package com.lovejournal.app.ui.cottage.chat

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.TextButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.lovejournal.app.data.remote.dto.ChatMessageResponse
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.theme.LoveMint

@Composable
fun ChatScreen(viewModel: ChatViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    val listState = rememberLazyListState()
    var draft by remember { mutableStateOf("") }
    // "寄给未来" — when non-null, the next send() schedules the message
    // for this instant instead of sending immediately. Reset after each send.
    var scheduleAt by remember { mutableStateOf<Instant?>(null) }
    var showScheduleDialog by remember { mutableStateOf(false) }
    // 点击消息里的图片后进入全屏预览的绝对 URL；null 表示关闭。
    var previewUrl by remember { mutableStateOf<String?>(null) }
    // 图片消息：系统相册选择器，选完即以当前输入框文字为说明发送。
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        uri?.let {
            viewModel.sendImage(it, draft)
            draft = ""
        }
    }
    if (state.toolsOpen) ChatToolsDialog(state, viewModel::closeTools, viewModel::clearPin)
    if (showScheduleDialog) {
        ScheduleDialog(
            initial = scheduleAt ?: Instant.now().plusSeconds(60 * 60),
            onDismiss = { showScheduleDialog = false },
            onConfirm = { picked ->
                scheduleAt = picked
                showScheduleDialog = false
            },
        )
    }
    // 全屏图片预览：点击气泡里的图片打开，点击任意处关闭。
    previewUrl?.let { url ->
        Dialog(
            onDismissRequest = { previewUrl = null },
            properties = DialogProperties(usePlatformDefaultWidth = false),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color.Black.copy(alpha = 0.92f))
                    .clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = null,
                    ) { previewUrl = null },
                contentAlignment = Alignment.Center,
            ) {
                AsyncImage(
                    model = url,
                    contentDescription = "图片预览",
                    contentScale = ContentScale.Fit,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
    }

    LaunchedEffect(Unit) {
        viewModel.toast.collect { snackbar.showSnackbar(it) }
    }
    // Only auto-scroll when the user is already near the bottom — same
    // pattern as the Web client (isNearBottom, <120px threshold). This
    // avoids yanking the user back to the latest message when they're
    // scrolling up to read history and a new message lands.
    LaunchedEffect(state.messages.size) {
        if (state.messages.isEmpty()) return@LaunchedEffect
        val info = listState.layoutInfo
        val total = info.totalItemsCount
        if (total == 0) return@LaunchedEffect
        val lastVisible = info.visibleItemsInfo.lastOrNull()?.index ?: -1
        // "Near bottom" = last visible item is within the last 3 messages.
        val nearBottom = lastVisible >= total - 3 || lastVisible == -1
        if (nearBottom) {
            listState.animateScrollToItem(state.messages.size - 1)
        }
    }

    Scaffold(snackbarHost = { SnackbarHost(snackbar) }) { padding ->
        LovePage(modifier = Modifier.padding(padding)) {
        Column(modifier = Modifier.fillMaxSize()) {
            PresenceHeader(
                nickname = state.partnerNickname,
                online = state.partnerOnline,
                typing = state.partnerTyping,
                connected = state.connected,
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                IconButton(onClick = viewModel::openTools) { Icon(Icons.Default.MoreVert, "聊天工具") }
            }
            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                items(state.messages, key = { it.mid }) { msg ->
                    MessageBubble(
                        msg,
                        isSelf = msg.sender_uid == state.selfUid,
                        mediaUrl = viewModel::mediaUrl,
                        onImageClick = { previewUrl = it },
                        onFavorite = { viewModel.toggleFavorite(msg) },
                        onRecall = { viewModel.recall(msg) },
                        onPin = { viewModel.pin(msg) },
                    )
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = { viewModel.poke() }) {
                    Icon(Icons.Filled.Favorite, contentDescription = "戳一戳", tint = MaterialTheme.colorScheme.primary)
                }
                OutlinedTextField(
                    value = draft,
                    onValueChange = {
                        draft = it
                        viewModel.onInputChanged(it)
                    },
                    placeholder = { Text("发条悄悄话…") },
                    modifier = Modifier.weight(1f),
                )
                IconButton(
                    onClick = {
                        imagePicker.launch(
                            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
                        )
                    },
                    enabled = !state.uploadingImage,
                ) {
                    if (state.uploadingImage) {
                        CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                    } else {
                        Icon(
                            Icons.Outlined.Image,
                            contentDescription = "发送图片",
                            tint = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
                IconButton(onClick = { showScheduleDialog = true }) {
                    Icon(
                        Icons.Filled.Schedule,
                        contentDescription = "寄给未来",
                        tint = if (scheduleAt != null) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                IconButton(onClick = {
                    viewModel.send(draft, visibleAt = scheduleAt)
                    draft = ""
                    scheduleAt = null
                }) {
                    Icon(
                        Icons.AutoMirrored.Filled.Send,
                        contentDescription = if (scheduleAt == null) "发送" else "寄给未来",
                        tint = if (scheduleAt != null) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.primary,
                    )
                }
            }
            if (scheduleAt != null) {
                Text(
                    text = "✉️ 这条悄悄话会在 ${formatScheduleLabel(scheduleAt!!)} 出现",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.tertiary,
                    modifier = Modifier.padding(horizontal = 12.dp),
                )
            }
        }
        }
    }
}

@Composable
private fun PresenceHeader(nickname: String?, online: Boolean, typing: Boolean, connected: Boolean) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .background(
                    color = if (online) LoveMint else MaterialTheme.colorScheme.outline,
                    shape = CircleShape,
                ),
        )
        Text(nickname ?: "TA", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        val status = when {
            !connected -> "连接中…"
            typing -> "正在输入…"
            online -> "在线"
            else -> "离线"
        }
        Text(status, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/**
 * 按消息类型渲染气泡：图片/贴纸走 Coil 直接展示媒体（无气泡底色），
 * 语音展示时长占位（本期不做播放），其余仍为纯文本气泡。
 * 已撤回或媒体地址缺失时回退到占位文本。
 */
@Composable
private fun MessageBubble(
    message: ChatMessageResponse,
    isSelf: Boolean,
    mediaUrl: (String?) -> String?,
    onImageClick: (String) -> Unit,
    onFavorite: () -> Unit,
    onRecall: () -> Unit,
    onPin: () -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    val bubbleColor = if (isSelf) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant
    val resolvedUrl = if (message.is_recalled) null else mediaUrl(message.media_url)
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isSelf) Arrangement.End else Arrangement.Start,
    ) {
        Column {
            when {
                // 图片消息：圆角大图 + 可选说明文字，点击全屏预览。
                message.type == "image" && resolvedUrl != null -> {
                    if (!isSelf) SenderName(message.sender_nickname)
                    AsyncImage(
                        model = resolvedUrl,
                        contentDescription = "图片消息",
                        contentScale = ContentScale.Fit,
                        modifier = Modifier
                            .widthIn(max = 240.dp)
                            .heightIn(max = 280.dp)
                            .clip(RoundedCornerShape(14.dp))
                            .clickable { onImageClick(resolvedUrl) },
                    )
                    message.content?.takeIf { it.isNotBlank() }?.let { caption ->
                        Text(
                            caption,
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                    }
                }
                // 贴纸消息：小尺寸表情图，不带气泡底色。
                message.type == "sticker" && resolvedUrl != null -> {
                    if (!isSelf) SenderName(message.sender_nickname)
                    AsyncImage(
                        model = resolvedUrl,
                        contentDescription = "贴纸消息",
                        contentScale = ContentScale.Fit,
                        modifier = Modifier.widthIn(max = 120.dp).heightIn(max = 120.dp),
                    )
                }
                // 语音消息：仅展示时长占位，不做播放。
                message.type == "voice" && !message.is_recalled -> ChatBubble(
                    bubbleColor,
                    isSelf,
                    message.sender_nickname,
                    if (message.audio_duration_sec != null) "♪ 语音消息 · ${message.audio_duration_sec}s" else "♪ 语音消息",
                )
                // 文本消息 + 各类兜底（已撤回 / 媒体地址缺失）。
                else -> ChatBubble(
                    bubbleColor,
                    isSelf,
                    message.sender_nickname,
                    when {
                        message.is_recalled -> "消息已撤回"
                        message.type == "image" -> "[图片]"
                        message.type == "sticker" -> "[贴纸]"
                        else -> message.content ?: ""
                    },
                )
            }
        IconButton(onClick = { menu = true }) {
            if (message.is_favorite) {
                Icon(Icons.Filled.Star, contentDescription = "收藏", tint = Color(0xFFFFD700))
            } else {
                Icon(Icons.Default.MoreHoriz, contentDescription = "更多")
            }
        }
        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
            DropdownMenuItem(text = { Text(if (message.is_favorite) "取消收藏" else "收藏") }, onClick = { menu = false; onFavorite() })
            DropdownMenuItem(text = { Text("置顶语录") }, onClick = { menu = false; onPin() })
            if (message.can_recall && !message.is_recalled) DropdownMenuItem(text = { Text("撤回") }, onClick = { menu = false; onRecall() })
        }
        }
    }
}

/** 纯文本气泡（文本/语音/撤回占位），沿用原有 78% 宽度 + 圆角 + 昵称样式。 */
@Composable
private fun ChatBubble(color: Color, isSelf: Boolean, sender: String, text: String) {
    Surface(
        color = color,
        shape = RoundedCornerShape(14.dp),
        modifier = Modifier.fillMaxWidth(0.78f),
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
            if (!isSelf) SenderName(sender)
            Text(text, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

/** 对方消息顶部的昵称小字。 */
@Composable
private fun SenderName(nickname: String) {
    Text(
        nickname,
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.primary,
    )
}

@Composable
private fun ChatToolsDialog(state: ChatUiState, onDismiss: () -> Unit, onClearPin: () -> Unit) {
    val memory = state.memoryCard
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("聊天回忆") },
        text = { LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            state.pinnedQuote?.message?.let { item { Text("置顶：${it.content ?: "[媒体消息]"}"); TextButton(onClick = onClearPin) { Text("取消置顶") } } }
            memory?.let { item { Text("今日 ${it.total_messages} 条 · 我 ${it.self_messages} · TA ${it.partner_messages}"); Text("关键词：${it.keywords.joinToString("、") { word -> "${word.keyword}(${word.count})" }}") } }
            if (state.favorites.isNotEmpty()) { item { Text("收藏", fontWeight = FontWeight.Bold) }; items(state.favorites, key = { "fav-${it.mid}" }) { Text(it.content ?: "[媒体消息]") } }
            if (state.future.isNotEmpty()) { item { Text("未来消息", fontWeight = FontWeight.Bold) }; items(state.future, key = { "future-${it.mid}" }) { Text(it.content ?: "[媒体消息]") } }
            state.mediaPanel?.let { panel -> item { Text("媒体：图片 ${panel.images.size} · 贴纸 ${panel.stickers.size} · 语音 ${panel.voices.size}") } }
        } },
        confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
    )
}

/**
 * "寄给未来" — pick a date+time, the next outgoing message is held by the
 * server until that instant. The picker is intentionally minimal: a date
 * row, a time row, and three quick presets (1h / 1d / next 00:00).
 */
@Composable
private fun ScheduleDialog(
    initial: Instant,
    onDismiss: () -> Unit,
    onConfirm: (Instant) -> Unit,
) {
    val zone = remember { ZoneId.systemDefault() }
    val initialLocal = remember(initial) {
        LocalDateTime.ofInstant(initial, zone)
    }
    var pickedDate by remember { mutableStateOf(initialLocal.toLocalDate()) }
    var pickedTime by remember { mutableStateOf(initialLocal.toLocalTime().withSecond(0).withNano(0)) }
    val combined = remember(pickedDate, pickedTime) { LocalDateTime.of(pickedDate, pickedTime) }
    val candidate = remember(combined) { combined.atZone(zone).toInstant() }

    val formatter = remember { DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.Schedule, contentDescription = null, tint = MaterialTheme.colorScheme.tertiary)
                Spacer(Modifier.size(8.dp))
                Text("寄给未来")
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    text = "把此刻的话藏到以后。消息会在你指定的时间准时出现，仅你们两人可见。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    AssistChip(
                        onClick = {
                            val now = LocalDateTime.now(zone)
                            pickedDate = now.toLocalDate()
                            pickedTime = now.plusHours(1).toLocalTime().withSecond(0).withNano(0)
                        },
                        label = { Text("1 小时后") },
                    )
                    AssistChip(
                        onClick = {
                            val now = LocalDateTime.now(zone)
                            pickedDate = now.toLocalDate()
                            pickedTime = now.plusDays(1).toLocalTime().withSecond(0).withNano(0)
                        },
                        label = { Text("明天现在") },
                    )
                    AssistChip(
                        onClick = {
                            val tomorrow = LocalDateTime.now(zone).plusDays(1)
                            pickedDate = tomorrow.toLocalDate()
                            pickedTime = LocalDateTime.of(tomorrow.toLocalDate(), java.time.LocalTime.of(0, 0))
                                .toLocalTime()
                        },
                        label = { Text("明天 0 点") },
                    )
                }
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedTextField(
                        value = pickedDate.toString(),
                        onValueChange = { raw ->
                            runCatching { java.time.LocalDate.parse(raw) }.getOrNull()?.let { pickedDate = it }
                        },
                        label = { Text("日期 (YYYY-MM-DD)") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = pickedTime.toString().take(5),
                        onValueChange = { raw ->
                            runCatching { java.time.LocalTime.parse(raw) }.getOrNull()?.let { pickedTime = it }
                        },
                        label = { Text("时间 (HH:mm)") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                }
                Text(
                    text = "将于 ${formatter.format(combined)} 出现",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.tertiary,
                )
            }
        },
        confirmButton = {
            val isFuture = candidate.isAfter(Instant.now())
            TextButton(
                enabled = isFuture,
                onClick = { onConfirm(candidate) },
            ) { Text(if (isFuture) "确认" else "请选未来时间") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

/** Render a future Instant in the user's local timezone, e.g. "11/12 14:30". */
private fun formatScheduleLabel(instant: Instant): String {
    val zone = ZoneId.systemDefault()
    val ldt = instant.atZone(zone)
    val pattern = if (ldt.year == LocalDateTime.now(zone).year) "MM-dd HH:mm" else "yyyy-MM-dd HH:mm"
    return ldt.format(DateTimeFormatter.ofPattern(pattern))
}
