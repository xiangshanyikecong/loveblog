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

package com.lovejournal.app.ui.cottage.vault

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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Lock
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.ui.components.LovePage

@Composable
fun VaultScreen(viewModel: VaultViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var passphrase by remember { mutableStateOf("") }
    var editing by remember { mutableStateOf<VaultEntryUi?>(null) }
    var creating by remember { mutableStateOf(false) }
    var changing by remember { mutableStateOf(false) }
    var resetting by remember { mutableStateOf(false) }
    state.message?.let { AlertDialog(onDismissRequest = viewModel::clearMessage, confirmButton = { TextButton(onClick = viewModel::clearMessage) { Text("确定") } }, text = { Text(it) }) }
    if (creating || editing != null) VaultEditor(editing, { creating = false; editing = null }) { title, body -> viewModel.save(editing?.vid, title, body); creating = false; editing = null }
    if (changing) PassphraseDialog("更换保险箱口令", { changing = false }) { viewModel.changePassphrase(it); changing = false }
    if (resetting) AlertDialog(onDismissRequest = { resetting = false }, title = { Text("永久重置？") }, text = { Text("所有加密内容将永久删除，无法从回收站恢复。") }, confirmButton = { TextButton(onClick = { resetting = false; viewModel.reset() }) { Text("永久删除") } }, dismissButton = { TextButton(onClick = { resetting = false }) { Text("取消") } })

    if (state.loading) { Column(Modifier.fillMaxSize().padding(24.dp)) { CircularProgressIndicator() }; return }
    if (state.meta?.initialized != true) {
        VaultGate("创建私密空间", "口令只在本机用于派生密钥，服务器只保存密文。", passphrase, { passphrase = it }, state.busy) { viewModel.setup(passphrase); passphrase = "" }
        return
    }
    if (!state.unlocked) {
        VaultGate("解锁私密空间", "输入与网页端相同的口令即可读取同一份加密内容。", passphrase, { passphrase = it }, state.busy) { viewModel.unlock(passphrase); passphrase = "" }
        return
    }
    Scaffold(floatingActionButton = { ExtendedFloatingActionButton(onClick = { creating = true; viewModel.touch() }, icon = { Icon(Icons.Default.Add, null) }, text = { Text("新增加密内容") }) }) { padding ->
        LovePage(modifier = Modifier.padding(padding)) {
        LazyColumn(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Column { Text("私密空间", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold); Text("端到端加密 · 5 分钟自动锁定") }; IconButton(onClick = viewModel::lock) { Icon(Icons.Default.Lock, "锁定") } }; Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { OutlinedButton(onClick = { changing = true }) { Text("更换口令") }; TextButton(onClick = { resetting = true }) { Text("重置") } } }
            if (state.entries.isEmpty()) item { Text("还没有加密内容。") }
            items(state.entries, key = { it.vid }) { entry -> Card(Modifier.fillMaxWidth().clickable { editing = entry; viewModel.touch() }) { Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween) { Column(Modifier.weight(1f)) { Text(entry.title.ifBlank { "无标题" }, fontWeight = FontWeight.Bold); Text(entry.body, maxLines = 3) }; IconButton(onClick = { viewModel.delete(entry.vid) }) { Icon(Icons.Default.Delete, "删除") } } } }
        }
        }
    }
}

@Composable
private fun VaultGate(title: String, subtitle: String, passphrase: String, onChange: (String) -> Unit, busy: Boolean, action: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) { Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold); Text(subtitle, modifier = Modifier.padding(vertical = 12.dp)); OutlinedTextField(passphrase, onChange, label = { Text("口令") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth()); Button(action, enabled = !busy && passphrase.length >= 6, modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) { Text(if (busy) "处理中…" else title) } }
}

@Composable
private fun VaultEditor(entry: VaultEntryUi?, onDismiss: () -> Unit, onSave: (String, String) -> Unit) { var title by remember(entry?.vid) { mutableStateOf(entry?.title.orEmpty()) }; var body by remember(entry?.vid) { mutableStateOf(entry?.body.orEmpty()) }; AlertDialog(onDismissRequest = onDismiss, title = { Text(if (entry == null) "新增加密内容" else "编辑加密内容") }, text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { OutlinedTextField(title, { title = it }, label = { Text("标题") }); OutlinedTextField(body, { body = it }, label = { Text("内容") }, minLines = 5) } }, confirmButton = { Button(onClick = { onSave(title, body) }) { Text("加密保存") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } }) }

@Composable
private fun PassphraseDialog(title: String, onDismiss: () -> Unit, onSave: (String) -> Unit) { var value by remember { mutableStateOf("") }; AlertDialog(onDismissRequest = onDismiss, title = { Text(title) }, text = { OutlinedTextField(value, { value = it }, label = { Text("新口令") }, visualTransformation = PasswordVisualTransformation()) }, confirmButton = { Button(onClick = { onSave(value) }, enabled = value.length >= 6) { Text("确认") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } }) }
