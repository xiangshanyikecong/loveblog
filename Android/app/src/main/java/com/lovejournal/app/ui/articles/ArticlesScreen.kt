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

package com.lovejournal.app.ui.articles

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.History
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.data.remote.dto.ArticleDetail
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.ui.graphics.Brush
import com.lovejournal.app.ui.components.LoveEmptyState
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSectionTitle
import com.lovejournal.app.ui.components.LoveSoftCard
import com.lovejournal.app.ui.theme.LovePeach
import com.lovejournal.app.ui.theme.LoveRose

@Composable
fun ArticlesScreen(viewModel: ArticlesViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var editing by remember { mutableStateOf(false) }
    var deleting by remember { mutableStateOf(false) }
    BackHandler(state.detail != null) { viewModel.closeDetail() }

    state.message?.let { message ->
        AlertDialog(onDismissRequest = viewModel::clearMessage, confirmButton = { TextButton(onClick = viewModel::clearMessage) { Text("确定") } }, text = { Text(message) })
    }
    if (deleting) AlertDialog(
        onDismissRequest = { deleting = false },
        title = { Text("删除文章？") },
        text = { Text("删除后可在回收站恢复。") },
        confirmButton = { TextButton(onClick = { deleting = false; viewModel.deleteCurrent() }) { Text("删除") } },
        dismissButton = { TextButton(onClick = { deleting = false }) { Text("取消") } },
    )
    if (editing) ArticleEditor(state.detail, state.saving, onDismiss = { editing = false }, onSave = { title, excerpt, content, published, tags ->
        viewModel.save(title, excerpt, content, published, tags); editing = false
    })

    Scaffold(
        floatingActionButton = {
            if (state.detail == null) ExtendedFloatingActionButton(onClick = { editing = true }, icon = { Icon(Icons.Default.Add, null) }, text = { Text("写文章") })
        },
    ) { padding ->
        if (state.detail != null) ArticleDetailContent(
            detail = state.detail!!,
            versions = state.versions.map { it.version },
            onBack = viewModel::closeDetail,
            onEdit = { editing = true },
            onDelete = { deleting = true },
            onLoadVersions = viewModel::loadVersions,
            onRollback = viewModel::rollback,
            onComment = viewModel::comment,
            modifier = Modifier.padding(padding),
        ) else LovePage(modifier = Modifier.padding(padding)) {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                item { LoveSectionTitle("我们的文章", "把想说的话，认真写给未来") }
                if (state.loading) item { CircularProgressIndicator() }
                state.error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
                if (!state.loading && state.articles.isEmpty()) item {
                    LoveEmptyState(
                        emoji = "✍️",
                        title = "还没有文章",
                        subtitle = "写下你们的第一个故事",
                        actionLabel = "写文章",
                        onAction = { editing = true },
                    )
                }
                items(state.articles, key = { it.aid }) { article ->
                    LoveSoftCard(Modifier.fillMaxWidth().clickable { viewModel.open(article.aid) }) {
                        Column {
                            // Cover image with graceful gradient fallback (ArticleSummary has no cover field yet).
                            Box(
                                modifier = Modifier.fillMaxWidth().height(96.dp).background(
                                    Brush.linearGradient(listOf(LoveRose.copy(alpha = 0.6f), LovePeach.copy(alpha = 0.6f))),
                                ),
                            )
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text(article.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                                article.excerpt?.let {
                                    Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
                                }
                                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                    Surface(
                                        color = if (article.status == "Published") MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
                                        shape = MaterialTheme.shapes.extraLarge,
                                    ) {
                                        Text(
                                            if (article.status == "Published") "已发布" else "草稿",
                                            Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                            color = if (article.status == "Published") MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = FontWeight.SemiBold,
                                        )
                                    }
                                    article.author_nickname?.let {
                                        Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
                                    }
                                    Spacer(Modifier.weight(1f))
                                    Text((article.published_at ?: article.created_at).orEmpty().take(10), color = MaterialTheme.colorScheme.outline, style = MaterialTheme.typography.labelSmall)
                                }
                                if (article.tags.isNotEmpty()) {
                                    Text(
                                        article.tags.joinToString("  ") { "#$it" },
                                        color = MaterialTheme.colorScheme.tertiary,
                                        style = MaterialTheme.typography.labelSmall,
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ArticleDetailContent(
    detail: ArticleDetail,
    versions: List<Int>,
    onBack: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
    onLoadVersions: () -> Unit,
    onRollback: (Int) -> Unit,
    onComment: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var comment by remember(detail.aid) { mutableStateOf("") }
    LazyColumn(modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") }
                Row {
                    IconButton(onClick = onLoadVersions) { Icon(Icons.Default.History, "版本") }
                    IconButton(onClick = onEdit) { Icon(Icons.Default.Edit, "编辑") }
                    IconButton(onClick = onDelete) { Icon(Icons.Default.Delete, "删除") }
                }
            }
            Text(detail.title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            detail.excerpt?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        items(detail.blocks.sortedBy { it.sort_order }, key = { it.bid }) { Text(it.content, style = MaterialTheme.typography.bodyLarge) }
        if (versions.isNotEmpty()) item {
            Card { Column(Modifier.padding(12.dp)) {
                Text("历史版本", fontWeight = FontWeight.Bold)
                versions.forEach { version -> TextButton(onClick = { onRollback(version) }) { Text("回滚到版本 $version") } }
            } }
        }
        item { Text("评论", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(detail.comments, key = { it.cid }) { Text("${it.author_nickname ?: "用户"}：${it.content}") }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(comment, { comment = it }, label = { Text("写评论") }, modifier = Modifier.weight(1f))
                Button(onClick = { onComment(comment); comment = "" }, enabled = comment.isNotBlank()) { Text("发送") }
            }
        }
    }
}

@Composable
private fun ArticleEditor(
    detail: ArticleDetail?,
    saving: Boolean,
    onDismiss: () -> Unit,
    onSave: (String, String, String, Boolean, String) -> Unit,
) {
    var title by remember(detail?.aid) { mutableStateOf(detail?.title.orEmpty()) }
    var excerpt by remember(detail?.aid) { mutableStateOf(detail?.excerpt.orEmpty()) }
    var content by remember(detail?.aid) { mutableStateOf(detail?.blocks?.joinToString("\n\n") { it.content }.orEmpty()) }
    var tags by remember(detail?.aid) { mutableStateOf(detail?.tags?.joinToString(",").orEmpty()) }
    var published by remember(detail?.aid) { mutableStateOf(detail?.status == "Published") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (detail == null) "新建文章" else "编辑文章") },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(title, { title = it }, label = { Text("标题") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(excerpt, { excerpt = it }, label = { Text("摘要") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(content, { content = it }, label = { Text("正文") }, minLines = 5, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(tags, { tags = it }, label = { Text("标签，逗号分隔") }, modifier = Modifier.fillMaxWidth())
            Row { Checkbox(published, { published = it }); Text("发布") }
        } },
        confirmButton = { Button(onClick = { onSave(title, excerpt, content, published, tags) }, enabled = !saving) { Text("保存") } },
        dismissButton = { OutlinedButton(onClick = onDismiss) { Text("取消") } },
    )
}
