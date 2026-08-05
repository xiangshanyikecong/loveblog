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

package com.lovejournal.app.ui.albums

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.lovejournal.app.data.remote.dto.AlbumDetail
import com.lovejournal.app.ui.components.LoveEmptyState
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSectionTitle
import com.lovejournal.app.ui.components.LoveSoftCard

@Composable
fun AlbumsScreen(viewModel: AlbumsViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var editing by remember { mutableStateOf(false) }
    var deleting by remember { mutableStateOf(false) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { it?.let(viewModel::upload) }
    BackHandler(state.detail != null) { viewModel.closeDetail() }
    state.message?.let { message -> AlertDialog(onDismissRequest = viewModel::clearMessage, confirmButton = { TextButton(onClick = viewModel::clearMessage) { Text("确定") } }, text = { Text(message) }) }
    if (deleting) AlertDialog(onDismissRequest = { deleting = false }, title = { Text("删除相册？") }, text = { Text("删除后可在回收站恢复。") }, confirmButton = { TextButton(onClick = { deleting = false; viewModel.deleteCurrent() }) { Text("删除") } }, dismissButton = { TextButton(onClick = { deleting = false }) { Text("取消") } })
    if (editing) AlbumEditor(state.detail, state.pendingImageUrl, state.uploading, { picker.launch("image/*") }, { editing = false }) { title, description, tags -> viewModel.save(title, description, tags); editing = false }

    Scaffold(floatingActionButton = { if (state.detail == null) ExtendedFloatingActionButton(onClick = { editing = true }, icon = { Icon(Icons.Default.Add, null) }, text = { Text("新建相册") }) }) { padding ->
        if (state.detail != null) AlbumDetailContent(state.detail!!, viewModel::mediaUrl, viewModel::closeDetail, { editing = true }, { deleting = true }, viewModel::comment, Modifier.padding(padding))
        else LovePage(modifier = Modifier.padding(padding)) {
            LazyColumn(modifier = Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                item { LoveSectionTitle("我们的相册", "收藏每一次见面和共同经历") }
                if (state.loading) item { CircularProgressIndicator() }
                state.error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
                if (!state.loading && state.albums.isEmpty()) item { LoveEmptyState("📷", "还没有相册", "选几张照片，创建你们的第一本相册") }
                items(state.albums, key = { it.alb_id }) { album -> LoveSoftCard(Modifier.fillMaxWidth().clickable { viewModel.open(album.alb_id) }) {
                    Column { album.cover_url?.let { AsyncImage(viewModel.mediaUrl(it), null, Modifier.fillMaxWidth().height(190.dp), contentScale = ContentScale.Crop) }; Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) { Text(album.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold); album.description?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }; Text("${album.media_count} 张照片${album.tags.takeIf { it.isNotEmpty() }?.let { tags -> " · ${tags.joinToString(" · ")}" }.orEmpty()}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary) } }
                } }
            }
        }
    }
}

@Composable
private fun AlbumDetailContent(detail: AlbumDetail, mediaUrl: (String?) -> String?, onBack: () -> Unit, onEdit: () -> Unit, onDelete: () -> Unit, onComment: (String) -> Unit, modifier: Modifier) {
    var comment by remember(detail.alb_id) { mutableStateOf("") }
    LazyColumn(modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") }; Row { IconButton(onClick = onEdit) { Icon(Icons.Default.Edit, "编辑") }; IconButton(onClick = onDelete) { Icon(Icons.Default.Delete, "删除") } } }; Text(detail.title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold); detail.description?.let { Text(it) } }
        items(detail.media_items, key = { it.media_id }) { media -> AsyncImage(mediaUrl(media.file_url), null, Modifier.fillMaxWidth().height(240.dp), contentScale = ContentScale.Crop) }
        item { Text("评论", fontWeight = FontWeight.Bold) }
        items(detail.comments, key = { it.cid }) { Text("${it.author_nickname ?: "用户"}：${it.content}") }
        item { Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { OutlinedTextField(comment, { comment = it }, label = { Text("写评论") }, modifier = Modifier.weight(1f)); Button(onClick = { onComment(comment); comment = "" }, enabled = comment.isNotBlank()) { Text("发送") } } }
    }
}

@Composable
private fun AlbumEditor(detail: AlbumDetail?, pendingImageUrl: String?, uploading: Boolean, onPick: () -> Unit, onDismiss: () -> Unit, onSave: (String, String, String) -> Unit) {
    var title by remember(detail?.alb_id) { mutableStateOf(detail?.title.orEmpty()) }
    var description by remember(detail?.alb_id) { mutableStateOf(detail?.description.orEmpty()) }
    var tags by remember(detail?.alb_id) { mutableStateOf(detail?.tags?.joinToString(",").orEmpty()) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text(if (detail == null) "新建相册" else "编辑相册") }, text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { OutlinedTextField(title, { title = it }, label = { Text("标题") }); OutlinedTextField(description, { description = it }, label = { Text("描述") }); OutlinedTextField(tags, { tags = it }, label = { Text("标签，逗号分隔") }); OutlinedButton(onClick = onPick, enabled = !uploading) { Text(if (uploading) "上传中…" else if (pendingImageUrl != null) "已选图片，重新选择" else "从相册选择图片") } } }, confirmButton = { Button(onClick = { onSave(title, description, tags) }, enabled = !uploading) { Text("保存") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } })
}
