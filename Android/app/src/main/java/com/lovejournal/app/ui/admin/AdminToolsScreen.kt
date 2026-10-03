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

package com.lovejournal.app.ui.admin

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.foundation.layout.Row
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.R
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.asString

@Composable
fun AdminToolsScreen(viewModel: AdminToolsViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    state.message?.let { AlertDialog(onDismissRequest = viewModel::clearMessage, confirmButton = { TextButton(onClick = viewModel::clearMessage) { Text(stringResource(R.string.btn_confirm)) } }, text = { Text(it.asString()) }) }
    LovePage(modifier = Modifier.verticalScroll(rememberScrollState())) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(stringResource(R.string.admin_title), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(stringResource(R.string.admin_desc))
        if (state.loading) CircularProgressIndicator()
        AdminCard(stringResource(R.string.admin_health), state.health)
        AdminCard(stringResource(R.string.admin_storage), state.storage)
        AdminCard(stringResource(R.string.admin_storage_usage), state.storageUsage)
        AdminCard(stringResource(R.string.admin_health_history), state.healthHistory)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = viewModel::remediateNow, enabled = !state.remediating, modifier = Modifier.weight(1f)) {
                if (state.remediating) CircularProgressIndicator(Modifier.padding(2.dp), strokeWidth = 2.dp) else Text(stringResource(R.string.admin_remediate))
            }
        }
        AdminCard(stringResource(R.string.admin_backup), state.backup)
        Button(onClick = viewModel::runBackup, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.admin_run_backup)) }
        AdminCard(stringResource(R.string.admin_users), state.users)
        AdminCard(stringResource(R.string.admin_audit), state.audit)
        OutlinedButton(onClick = viewModel::refresh, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.btn_refresh)) }
        LaunchedEffect(Unit) { viewModel.loadMore() }
        }
    }
}

@Composable private fun AdminCard(title: String, value: UiText?) { Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { Text(title, fontWeight = FontWeight.Bold); Text(value?.asString() ?: stringResource(R.string.msg_no_data), style = MaterialTheme.typography.bodySmall) } } }

@Composable private fun AdminCard(title: String, lines: List<UiText>) { Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { Text(title, fontWeight = FontWeight.Bold); lines.forEach { Text(it.asString(), style = MaterialTheme.typography.bodySmall) } } } }
