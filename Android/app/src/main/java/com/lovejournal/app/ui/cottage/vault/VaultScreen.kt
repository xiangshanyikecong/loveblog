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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.R
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.asString

@Composable
fun VaultScreen(viewModel: VaultViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var passphrase by remember { mutableStateOf("") }
    var editing by remember { mutableStateOf<VaultEntryUi?>(null) }
    var creating by remember { mutableStateOf(false) }
    var changing by remember { mutableStateOf(false) }
    var resetting by remember { mutableStateOf(false) }
    state.message?.let { AlertDialog(onDismissRequest = viewModel::clearMessage, confirmButton = { TextButton(onClick = viewModel::clearMessage) { Text(stringResource(R.string.btn_confirm)) } }, text = { Text(it.asString()) }) }
    if (creating || editing != null) VaultEditor(editing, { creating = false; editing = null }) { title, body -> viewModel.save(editing?.vid, title, body); creating = false; editing = null }
    if (changing) PassphraseDialog(stringResource(R.string.vault_change_passphrase_title), { changing = false }) { viewModel.changePassphrase(it); changing = false }
    if (resetting) AlertDialog(onDismissRequest = { resetting = false }, title = { Text(stringResource(R.string.vault_reset_title)) }, text = { Text(stringResource(R.string.vault_reset_desc)) }, confirmButton = { TextButton(onClick = { resetting = false; viewModel.reset() }) { Text(stringResource(R.string.btn_permanent_delete)) } }, dismissButton = { TextButton(onClick = { resetting = false }) { Text(stringResource(R.string.btn_cancel)) } })

    if (state.loading) { Column(Modifier.fillMaxSize().padding(24.dp)) { CircularProgressIndicator() }; return }
    if (state.meta?.initialized != true) {
        VaultGate(stringResource(R.string.vault_create_title), stringResource(R.string.vault_create_desc), passphrase, { passphrase = it }, state.busy) { viewModel.setup(passphrase); passphrase = "" }
        return
    }
    if (!state.unlocked) {
        VaultGate(stringResource(R.string.vault_unlock_title), stringResource(R.string.vault_unlock_desc), passphrase, { passphrase = it }, state.busy) { viewModel.unlock(passphrase); passphrase = "" }
        return
    }
    Scaffold(floatingActionButton = { ExtendedFloatingActionButton(onClick = { creating = true; viewModel.touch() }, icon = { Icon(Icons.Default.Add, null) }, text = { Text(stringResource(R.string.vault_add_entry)) }) }) { padding ->
        LovePage(modifier = Modifier.padding(padding)) {
        LazyColumn(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Column { Text(stringResource(R.string.vault_private_space), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold); Text(stringResource(R.string.vault_e2e_desc)) }; IconButton(onClick = viewModel::lock) { Icon(Icons.Default.Lock, stringResource(R.string.vault_lock)) } }; Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { OutlinedButton(onClick = { changing = true }) { Text(stringResource(R.string.vault_change_passphrase)) }; TextButton(onClick = { resetting = true }) { Text(stringResource(R.string.vault_reset)) } } }
            if (state.entries.isEmpty()) item { Text(stringResource(R.string.vault_no_entries)) }
            items(state.entries, key = { it.vid }) { entry -> Card(Modifier.fillMaxWidth().clickable { editing = entry; viewModel.touch() }) { Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween) { Column(Modifier.weight(1f)) { Text(entry.title.ifBlank { stringResource(R.string.vault_untitled) }, fontWeight = FontWeight.Bold); Text(entry.body, maxLines = 3) }; IconButton(onClick = { viewModel.delete(entry.vid) }) { Icon(Icons.Default.Delete, stringResource(R.string.btn_delete)) } } } }
        }
        }
    }
}

@Composable
private fun VaultGate(title: String, subtitle: String, passphrase: String, onChange: (String) -> Unit, busy: Boolean, action: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) { Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold); Text(subtitle, modifier = Modifier.padding(vertical = 12.dp)); OutlinedTextField(passphrase, onChange, label = { Text(stringResource(R.string.vault_passphrase)) }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth()); Button(action, enabled = !busy && passphrase.length >= 6, modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) { Text(if (busy) stringResource(R.string.status_processing) else title) } }
}

@Composable
private fun VaultEditor(entry: VaultEntryUi?, onDismiss: () -> Unit, onSave: (String, String) -> Unit) { var title by remember(entry?.vid) { mutableStateOf(entry?.title.orEmpty()) }; var body by remember(entry?.vid) { mutableStateOf(entry?.body.orEmpty()) }; AlertDialog(onDismissRequest = onDismiss, title = { Text(if (entry == null) stringResource(R.string.vault_add_title) else stringResource(R.string.vault_edit_title)) }, text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { OutlinedTextField(title, { title = it }, label = { Text(stringResource(R.string.vault_title_label)) }); OutlinedTextField(body, { body = it }, label = { Text(stringResource(R.string.vault_content_label)) }, minLines = 5) } }, confirmButton = { Button(onClick = { onSave(title, body) }) { Text(stringResource(R.string.btn_encrypt_save)) } }, dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.btn_cancel)) } }) }

@Composable
private fun PassphraseDialog(title: String, onDismiss: () -> Unit, onSave: (String) -> Unit) { var value by remember { mutableStateOf("") }; AlertDialog(onDismissRequest = onDismiss, title = { Text(title) }, text = { OutlinedTextField(value, { value = it }, label = { Text(stringResource(R.string.vault_new_passphrase)) }, visualTransformation = PasswordVisualTransformation()) }, confirmButton = { Button(onClick = { onSave(value) }, enabled = value.length >= 6) { Text(stringResource(R.string.vault_confirm)) } }, dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.btn_cancel)) } }) }
