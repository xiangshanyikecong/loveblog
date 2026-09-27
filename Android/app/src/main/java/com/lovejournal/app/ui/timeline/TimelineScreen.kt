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

package com.lovejournal.app.ui.timeline

import android.net.Uri
import android.os.Parcelable
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import coil.compose.AsyncImagePainter
import coil.request.ImageRequest
import com.lovejournal.app.BuildConfig
import com.lovejournal.app.data.remote.dto.CommentNodeResponse
import com.lovejournal.app.data.remote.dto.MomentResponse
import androidx.compose.runtime.saveable.listSaver
import androidx.compose.runtime.saveable.rememberSaveable
import com.lovejournal.app.ui.components.LoveConfirmDialog
import com.lovejournal.app.ui.components.LoveEmptyState
import com.lovejournal.app.util.formatDateTime

private val VISIBILITY_OPTIONS = listOf("PartnersOnly" to "仅彼此", "Public" to "公开")

/** 发动态时最多可选择的图片张数（与后端单条动态图片上限一致）。 */
private const val MAX_MEDIA_PER_MOMENT = 9

private fun visibilityLabel(value: String): String = when (value) {
    "Public" -> "公开"
    "PartnersOnly" -> "仅彼此"
    "Encrypted" -> "加密"
    else -> value
}

private fun mediaUrl(path: String): String =
    if (path.startsWith("http")) path else BuildConfig.MEDIA_BASE_URL + path

private val IMAGE_EXT_REGEX = Regex("""\.(jpe?g|png|webp)(\?.*)?$""", RegexOption.IGNORE_CASE)

/** Derives the server-side `_thumb` variant for /uploads image paths
 *  (mirrors the web `toThumbnailUrl` helper). Returns the input untouched
 *  for non-upload paths, GIFs or already-thumbnailed URLs. */
private fun deriveThumbnailPath(path: String): String {
    if (!path.contains("/uploads/")) return path
    if (path.contains("_thumb")) return path
    if (!IMAGE_EXT_REGEX.containsMatchIn(path)) return path
    return path.replace(IMAGE_EXT_REGEX, "_thumb$1$2")
}

/** 从 ISO 时间戳提取年份（"2023-10-01T..." -> 2023），解析失败返回 null。 */
private fun yearOf(iso: String): Int? = iso.take(4).toIntOrNull()

@Composable
fun TimelineScreen(viewModel: TimelineViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()
    var editorOpen by rememberSaveable { mutableStateOf(false) }
    var previewUrl by remember { mutableStateOf<String?>(null) }
    var pendingDelete by remember { mutableStateOf<MomentResponse?>(null) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(
                        MaterialTheme.colorScheme.background,
                        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.10f),
                    ),
                ),
            ),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            message?.let {
                Text(
                    text = it,
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                )
            }
            TimelineModeSwitch(
                selected = state.selectedTab,
                onSelect = viewModel::selectTab,
            )
            when (state.selectedTab) {
                TimelineTab.MOMENTS -> MomentsContent(
                    state = state,
                    onRetry = viewModel::refresh,
                    onDelete = { pendingDelete = it },
                    onComment = { mid, content, parentCid -> viewModel.comment(mid, content, parentCid) },
                    onPreviewImage = { previewUrl = it },
                )
                TimelineTab.MEMORIES -> MemoriesContent(
                    state = state,
                    onRetry = viewModel::refresh,
                    onPreviewImage = { previewUrl = it },
                )
            }
        }

        if (state.selectedTab == TimelineTab.MOMENTS) {
            FloatingActionButton(
                onClick = { editorOpen = true },
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(20.dp),
            ) {
                Icon(Icons.Filled.Add, contentDescription = "发动态")
            }
        }
    }

    if (editorOpen) {
        MomentEditorDialog(
            posting = state.posting,
            onDismiss = { editorOpen = false },
            onSave = { content, visibility, imageUris ->
                viewModel.post(content, visibility, imageUris) { editorOpen = false }
            },
        )
    }

    previewUrl?.let { url ->
        FullScreenImageDialog(url = url, onDismiss = { previewUrl = null })
    }

    pendingDelete?.let { moment ->
        LoveConfirmDialog(
            title = "删除这条动态？",
            message = "动态的文字与图片、以及下面的评论都会一起删除，无法恢复。",
            onConfirm = {
                viewModel.delete(moment)
                pendingDelete = null
            },
            onDismiss = { pendingDelete = null },
        )
    }
}

/** 「动态 / 回忆」分段切换。 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TimelineModeSwitch(selected: TimelineTab, onSelect: (TimelineTab) -> Unit) {
    SingleChoiceSegmentedButtonRow(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        SegmentedButton(
            selected = selected == TimelineTab.MOMENTS,
            onClick = { onSelect(TimelineTab.MOMENTS) },
            shape = SegmentedButtonDefaults.itemShape(index = 0, count = 2),
        ) { Text("动态") }
        SegmentedButton(
            selected = selected == TimelineTab.MEMORIES,
            onClick = { onSelect(TimelineTab.MEMORIES) },
            shape = SegmentedButtonDefaults.itemShape(index = 1, count = 2),
        ) { Text("回忆") }
    }
}

/** 动态流分栏：列表 / 加载 / 错误 / 空态。 */
@Composable
private fun MomentsContent(
    state: TimelineUiState,
    onRetry: () -> Unit,
    onDelete: (MomentResponse) -> Unit,
    onComment: (mid: String, content: String, parentCid: String?) -> Unit,
    onPreviewImage: (String) -> Unit,
) {
    when {
        state.loading && state.items.isEmpty() ->
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        state.error != null && state.items.isEmpty() ->
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("加载失败：${state.error}", color = MaterialTheme.colorScheme.error)
                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(onClick = onRetry) { Text("重试") }
                }
            }
        state.items.isEmpty() ->
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                LoveEmptyState("✍️", "还没有动态", "把此刻的心情记录下来吧")
            }
        else -> LazyColumn(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            items(state.items, key = { it.mid }) { moment ->
                MomentCard(
                    moment = moment,
                    onDelete = { onDelete(moment) },
                    onComment = { content, parentCid -> onComment(moment.mid, content, parentCid) },
                    onPreviewImage = onPreviewImage,
                )
            }
        }
    }
}

/** 动态卡片：作者信息、正文（图片 / 语音 / 地点 / 标签）、评论树与评论输入。 */
@Composable
private fun MomentCard(
    moment: MomentResponse,
    onDelete: () -> Unit,
    onComment: (content: String, parentCid: String?) -> Unit,
    onPreviewImage: (String) -> Unit,
) {
    // 本卡片的回复目标；点某条评论的「回复」后进入回复模式，随下一条评论提交。
    var replyTo by remember(moment.mid) { mutableStateOf<CommentNodeResponse?>(null) }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(moment.author_nickname, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                    Text(
                        "${formatDateTime(moment.timestamp)} · ${visibilityLabel(moment.visibility)}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.outline,
                    )
                }
                IconButton(onClick = onDelete) {
                    Icon(Icons.Filled.Delete, contentDescription = "删除", tint = MaterialTheme.colorScheme.error)
                }
            }

            MomentBody(moment = moment, onPreviewImage = onPreviewImage)

            if (moment.comments.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    "评论 ${moment.comments.size}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            moment.comments.forEach { comment ->
                CommentNode(comment = comment, depth = 0, onReply = { replyTo = it })
            }

            Spacer(Modifier.height(4.dp))
            CommentInputBar(
                replyTo = replyTo,
                onDismissReply = { replyTo = null },
                onSend = { text ->
                    onComment(text, replyTo?.cid)
                    replyTo = null
                },
            )
        }
    }
}

/** 动态正文：文字 + 图片行 + 语音胶囊 + 地点 + 标签，动态卡片与回忆卡片共用。 */
@Composable
private fun MomentBody(moment: MomentResponse, onPreviewImage: (String) -> Unit) {
    moment.content.takeIf { it.isNotBlank() }?.let {
        Spacer(Modifier.height(4.dp))
        Text(it, style = MaterialTheme.typography.bodyMedium)
    }

    if (moment.media_urls.isNotEmpty()) {
        Spacer(Modifier.height(8.dp))
        if (moment.media_urls.size == 1) {
            MomentThumb(
                path = moment.media_urls.first(),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(200.dp)
                    .clip(RoundedCornerShape(8.dp)),
                onClick = { onPreviewImage(mediaUrl(moment.media_urls.first())) },
            )
        } else {
            Row(
                modifier = Modifier.horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                moment.media_urls.forEach { path ->
                    MomentThumb(
                        path = path,
                        modifier = Modifier
                            .height(180.dp)
                            .width(140.dp)
                            .clip(RoundedCornerShape(8.dp)),
                        onClick = { onPreviewImage(mediaUrl(path)) },
                    )
                }
            }
        }
    }

    // 语音消息：本轮仅展示胶囊（网页端可播放）。
    moment.audio_url?.let {
        Spacer(Modifier.height(6.dp))
        Surface(
            color = MaterialTheme.colorScheme.secondaryContainer,
            shape = RoundedCornerShape(50),
        ) {
            Text(
                "♪ 语音 ${moment.audio_duration_sec ?: 0}s",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSecondaryContainer,
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
            )
        }
    }

    moment.location?.takeIf { it.isNotBlank() }?.let {
        Spacer(Modifier.height(2.dp))
        Text("📍 $it", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }

    if (moment.tags.isNotEmpty()) {
        Text(
            moment.tags.joinToString(" ") { "#$it" },
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.primary,
        )
    }
}

/** 回忆（往年今日）分栏：只读列表，无发布 / 评论入口。 */
@Composable
private fun MemoriesContent(
    state: TimelineUiState,
    onRetry: () -> Unit,
    onPreviewImage: (String) -> Unit,
) {
    when {
        state.memoriesLoading && state.memories.isEmpty() ->
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        state.memoriesError != null && state.memories.isEmpty() ->
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("加载失败：${state.memoriesError}", color = MaterialTheme.colorScheme.error)
                    TextButton(onClick = onRetry) { Text("重试") }
                }
            }
        state.memories.isEmpty() ->
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("还没有往年今日的回忆")
            }
        else -> LazyColumn(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Column {
                    Text(
                        "回到那一天 · 往年今日",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        "那些同一天里发生过的小事",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            items(state.memories, key = { "memory-${it.mid}" }) { moment ->
                MemoryCard(moment = moment, onPreviewImage = onPreviewImage)
            }
        }
    }
}

/** 回忆卡片：年份醒目展示，正文只读（无删除 / 评论输入）。 */
@Composable
private fun MemoryCard(moment: MomentResponse, onPreviewImage: (String) -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                verticalAlignment = Alignment.Bottom,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text(
                    text = yearOf(moment.timestamp)?.toString() ?: "那一年",
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                )
                Column(modifier = Modifier.padding(bottom = 4.dp)) {
                    Text(moment.author_nickname, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                    Text(
                        "回到那一天 · ${formatDateTime(moment.timestamp)}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.outline,
                    )
                }
            }

            MomentBody(moment = moment, onPreviewImage = onPreviewImage)

            if (moment.comments.isNotEmpty()) {
                Spacer(Modifier.height(6.dp))
                Text(
                    "评论 ${moment.comments.size} 条（到动态里查看）",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/** 单条评论节点（递归渲染回复树），含作者昵称、时间与「回复」入口。 */
@Composable
private fun CommentNode(
    comment: CommentNodeResponse,
    depth: Int,
    onReply: (CommentNodeResponse) -> Unit,
) {
    Column(modifier = Modifier.padding(start = (depth * 14).dp, top = 6.dp)) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                comment.author_nickname,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                formatDateTime(comment.created_at),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.outline,
            )
        }
        Text(
            comment.content,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            "回复",
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier
                .padding(top = 2.dp)
                .clickable { onReply(comment) },
        )
        comment.replies.forEach { reply -> CommentNode(reply, depth + 1, onReply) }
    }
}

/** 评论输入条；[replyTo] 非空时处于回复模式。 */
@Composable
private fun CommentInputBar(
    replyTo: CommentNodeResponse?,
    onDismissReply: () -> Unit,
    onSend: (String) -> Unit,
) {
    var text by remember { mutableStateOf("") }
    Column {
        if (replyTo != null) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    "正在回复 ${replyTo.author_nickname}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    "取消",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.clickable(onClick = onDismissReply),
                )
            }
            Spacer(Modifier.height(2.dp))
        }
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                placeholder = { Text(if (replyTo != null) "回复 ${replyTo.author_nickname}…" else "写评论…") },
                modifier = Modifier.weight(1f),
                textStyle = MaterialTheme.typography.bodySmall,
                singleLine = true,
            )
            TextButton(
                onClick = { onSend(text); text = "" },
                enabled = text.isNotBlank(),
            ) { Text("发送") }
        }
    }
}

@Composable
private fun MomentThumb(path: String, modifier: Modifier = Modifier, onClick: (() -> Unit)? = null) {
    // Prefer the 400px server thumbnail; legacy uploads have none and 404,
    // so fall back to the original image on error (mirrors the web helper).
    var url by remember(path) { mutableStateOf(mediaUrl(deriveThumbnailPath(path))) }
    AsyncImage(
        model = ImageRequest.Builder(LocalContext.current).data(url).crossfade(true).build(),
        contentDescription = "动态图片",
        contentScale = ContentScale.Crop,
        onState = { state ->
            if (state is AsyncImagePainter.State.Error && url != mediaUrl(path)) {
                url = mediaUrl(path)
            }
        },
        modifier = modifier.clickable(enabled = onClick != null) { onClick?.invoke() },
    )
}

/** 全屏图片预览：点击任意处或「关闭」退出。 */
@Composable
private fun FullScreenImageDialog(url: String, onDismiss: () -> Unit) {
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.92f))
                .clickable(onClick = onDismiss),
            contentAlignment = Alignment.Center,
        ) {
            AsyncImage(
                model = ImageRequest.Builder(LocalContext.current).data(url).crossfade(true).build(),
                contentDescription = "图片预览",
                contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxSize(),
            )
            TextButton(
                onClick = onDismiss,
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 32.dp),
            ) { Text("关闭", color = Color.White) }
        }
    }
}

/** Uri 列表的 Saver：转屏/进程回收后已选图片不丢（Uri 为 Parcelable）。 */
private val UriListSaver = listSaver<List<Uri>, Parcelable>(
    save = { list -> list },
    restore = { list -> list.map { it as Uri } },
)

/** 发动态对话框：文字 + 可见范围 + 图片多选（最多 9 张，发布时经上传链路换取 URL）。 */
@Composable
private fun MomentEditorDialog(
    posting: Boolean,
    onDismiss: () -> Unit,
    onSave: (content: String, visibility: String, imageUris: List<Uri>) -> Unit,
) {
    var content by rememberSaveable { mutableStateOf("") }
    var visibility by rememberSaveable { mutableStateOf("PartnersOnly") }
    var selectedUris by rememberSaveable(stateSaver = UriListSaver) { mutableStateOf(emptyList<Uri>()) }
    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickMultipleVisualMedia(MAX_MEDIA_PER_MOMENT),
    ) { uris -> selectedUris = uris.take(MAX_MEDIA_PER_MOMENT) }

    AlertDialog(
        onDismissRequest = { if (!posting) onDismiss() },
        title = { Text("发一条动态") },
        text = {
            Column {
                OutlinedTextField(
                    value = content,
                    onValueChange = { content = it },
                    label = { Text("此刻想说的话…") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                OutlinedButton(
                    onClick = {
                        picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
                    },
                    enabled = !posting && selectedUris.size < MAX_MEDIA_PER_MOMENT,
                ) {
                    Text(
                        if (selectedUris.isEmpty()) "添加图片（最多 $MAX_MEDIA_PER_MOMENT 张）"
                        else "已选 ${selectedUris.size} 张，继续添加",
                    )
                }
                if (selectedUris.isNotEmpty()) {
                    Spacer(Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        selectedUris.forEach { uri ->
                            Box {
                                AsyncImage(
                                    model = uri,
                                    contentDescription = "待发布图片",
                                    contentScale = ContentScale.Crop,
                                    modifier = Modifier
                                        .size(64.dp)
                                        .clip(RoundedCornerShape(8.dp)),
                                )
                                Text(
                                    "✕",
                                    color = Color.White,
                                    style = MaterialTheme.typography.labelSmall,
                                    modifier = Modifier
                                        .align(Alignment.TopEnd)
                                        .padding(3.dp)
                                        .clip(CircleShape)
                                        .background(Color.Black.copy(alpha = 0.55f))
                                        .clickable { selectedUris = selectedUris - uri }
                                        .padding(horizontal = 5.dp, vertical = 1.dp),
                                )
                            }
                        }
                    }
                }
                Spacer(Modifier.height(12.dp))
                Text("谁可以看", style = MaterialTheme.typography.labelMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    VISIBILITY_OPTIONS.forEach { (value, label) ->
                        FilterChip(
                            selected = visibility == value,
                            onClick = { visibility = value },
                            label = { Text(label) },
                        )
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onSave(content, visibility, selectedUris) },
                enabled = !posting && (content.isNotBlank() || selectedUris.isNotEmpty()),
            ) { Text(if (posting) "发布中…" else "发布") }
        },
        dismissButton = { TextButton(onClick = onDismiss, enabled = !posting) { Text("取消") } },
    )
}
