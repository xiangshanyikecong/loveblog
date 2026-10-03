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

package com.lovejournal.app.ui.messages

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.ui.platform.LocalContext
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.R
import com.lovejournal.app.data.local.entity.MessageEntity
import com.lovejournal.app.data.remote.dto.ContentVersion
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSoftCard
import com.lovejournal.app.ui.components.asString

@Composable
fun MessagesScreen(viewModel: MessagesViewModel = hiltViewModel()) {
    val messages by viewModel.messages.collectAsStateWithLifecycle()
    val status by viewModel.status.collectAsStateWithLifecycle()
    val selfUid by viewModel.selfUid.collectAsStateWithLifecycle()
    val versions by viewModel.versions.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    val context = LocalContext.current
    var draft by remember { mutableStateOf("") }
    var isPublic by remember { mutableStateOf(true) }
    var editingMessage by remember { mutableStateOf<MessageEntity?>(null) }
    var deletingMessage by remember { mutableStateOf<MessageEntity?>(null) }
    var historyMessage by remember { mutableStateOf<MessageEntity?>(null) }
    var rollingBackVersion by remember { mutableStateOf<Int?>(null) }

    LaunchedEffect(status) {
        status?.let {
            snackbar.showSnackbar(it.asString(context))
            viewModel.clearStatus()
        }
    }

    editingMessage?.let { target ->
        MessageEditor(
            message = target,
            onDismiss = { editingMessage = null },
            onSave = { content, public ->
                editingMessage = null
                viewModel.editMessage(target, content, public)
            },
        )
    }
    deletingMessage?.let { target ->
        AlertDialog(
            onDismissRequest = { deletingMessage = null },
            title = { Text(stringResource(R.string.messages_delete_title)) },
            text = { Text(stringResource(R.string.messages_delete_desc)) },
            confirmButton = {
                TextButton(onClick = { deletingMessage = null; viewModel.deleteMessage(target.msgId) }) { Text(stringResource(R.string.btn_delete)) }
            },
            dismissButton = { TextButton(onClick = { deletingMessage = null }) { Text(stringResource(R.string.btn_cancel)) } },
        )
    }
    historyMessage?.let { target ->
        LaunchedEffect(target.msgId) { viewModel.loadVersions(target.msgId) }
        AlertDialog(
            onDismissRequest = { historyMessage = null; viewModel.clearVersions() },
            title = { Text(stringResource(R.string.messages_history_title)) },
            text = {
                if (versions.isEmpty()) {
                    Text(stringResource(R.string.messages_no_versions))
                } else {
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        items(versions, key = { it.vid }) { version ->
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { rollingBackVersion = version.version },
                            ) {
                                Text(stringResource(R.string.messages_version_label, version.version), style = MaterialTheme.typography.titleSmall)
                                Text(
                                    text = listOfNotNull(version.actor_nickname, version.created_at?.take(16))
                                        .joinToString(" · "),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.outline,
                                )
                                version.note?.let {
                                    Text(
                                        it,
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { historyMessage = null; viewModel.clearVersions() }) { Text(stringResource(R.string.btn_close)) }
            },
        )
    }
    rollingBackVersion?.let { version ->
        AlertDialog(
            onDismissRequest = { rollingBackVersion = null },
            title = { Text(stringResource(R.string.messages_rollback_title, version)) },
            text = { Text(stringResource(R.string.messages_rollback_desc)) },
            confirmButton = {
                TextButton(onClick = {
                    val target = historyMessage
                    rollingBackVersion = null
                    target?.let { viewModel.rollbackMessage(it.msgId, version) }
                    historyMessage = null
                    viewModel.clearVersions()
                }) { Text(stringResource(R.string.btn_rollback)) }
            },
            dismissButton = { TextButton(onClick = { rollingBackVersion = null }) { Text(stringResource(R.string.btn_cancel)) } },
        )
    }

    Scaffold(snackbarHost = { SnackbarHost(snackbar) }) { padding ->
        LovePage(modifier = Modifier.padding(padding)) {
            Column(Modifier.fillMaxSize()) {
                LazyColumn(
                    modifier = Modifier.weight(1f).fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    reverseLayout = true,
                ) {
                    items(messages, key = { it.msgId }) { message ->
                        MessageRow(
                            message = message,
                            isOwn = message.authorUid != null && message.authorUid == selfUid,
                            onEdit = { editingMessage = message },
                            onDelete = { deletingMessage = message },
                            onHistory = { historyMessage = message },
                        )
                    }
                }
                Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(
                            selected = isPublic,
                            onClick = { isPublic = true },
                            label = { Text(stringResource(R.string.messages_public)) },
                        )
                        FilterChip(
                            selected = !isPublic,
                            onClick = { isPublic = false },
                            label = { Text(stringResource(R.string.messages_private)) },
                        )
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                    ) {
                        OutlinedTextField(
                            value = draft,
                            onValueChange = { draft = it },
                            placeholder = { Text(if (isPublic) stringResource(R.string.messages_placeholder_public) else stringResource(R.string.messages_placeholder_private)) },
                            modifier = Modifier.weight(1f),
                        )
                        IconButton(
                            enabled = draft.isNotBlank(),
                            onClick = {
                                viewModel.send(draft, isPublic)
                                draft = ""
                            }) {
                            Icon(Icons.AutoMirrored.Filled.Send, contentDescription = stringResource(R.string.btn_send))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MessageRow(
    message: MessageEntity,
    isOwn: Boolean,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
    onHistory: () -> Unit,
) {
    LoveSoftCard(Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        text = message.authorNickname ?: stringResource(R.string.messages_anonymous),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    if (!message.isPublic) {
                        Text(
                            stringResource(R.string.messages_private_msg),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.tertiary,
                        )
                    }
                }
                Row(
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                ) {
                    if (message.pendingSync) {
                        Text(stringResource(R.string.messages_pending_sync), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
                    }
                    // 仅作者本人可编辑 / 删除 / 查看历史版本（服务端同样校验）。
                    if (isOwn) {
                        var menuOpen by remember { mutableStateOf(false) }
                        IconButton(onClick = { menuOpen = true }) {
                            Icon(Icons.Default.MoreHoriz, contentDescription = stringResource(R.string.common_more_actions))
                        }
                        DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                            DropdownMenuItem(text = { Text(stringResource(R.string.btn_edit)) }, onClick = { menuOpen = false; onEdit() })
                            DropdownMenuItem(text = { Text(stringResource(R.string.btn_delete)) }, onClick = { menuOpen = false; onDelete() })
                            DropdownMenuItem(text = { Text(stringResource(R.string.messages_history_title)) }, onClick = { menuOpen = false; onHistory() })
                        }
                    }
                }
            }
            Text(message.content, style = MaterialTheme.typography.bodyMedium)
            Text(
                text = message.createdAt.take(16),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.outline,
            )
        }
    }
}

@Composable
private fun MessageEditor(
    message: MessageEntity,
    onDismiss: () -> Unit,
    onSave: (content: String, isPublic: Boolean) -> Unit,
) {
    var content by remember(message.msgId) { mutableStateOf(message.content) }
    var isPublic by remember(message.msgId) { mutableStateOf(message.isPublic) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.messages_edit_title)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = content,
                    onValueChange = { content = it },
                    label = { Text(stringResource(R.string.messages_content_label)) },
                    minLines = 3,
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Checkbox(checked = isPublic, onCheckedChange = { isPublic = it })
                    Text(stringResource(R.string.messages_public))
                }
            }
        },
        confirmButton = {
            Button(enabled = content.isNotBlank(), onClick = { onSave(content, isPublic) }) { Text(stringResource(R.string.btn_save)) }
        },
        dismissButton = { OutlinedButton(onClick = onDismiss) { Text(stringResource(R.string.btn_cancel)) } },
    )
}
