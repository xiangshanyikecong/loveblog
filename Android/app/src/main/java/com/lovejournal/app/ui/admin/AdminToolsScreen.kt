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
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.ui.components.LovePage

@Composable
fun AdminToolsScreen(viewModel: AdminToolsViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    state.message?.let { AlertDialog(onDismissRequest = viewModel::clearMessage, confirmButton = { TextButton(onClick = viewModel::clearMessage) { Text("确定") } }, text = { Text(it) }) }
    LovePage(modifier = Modifier.verticalScroll(rememberScrollState())) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("服务器工具", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("仅管理员接口会返回完整内容；普通伴侣账号看到无权限提示属于正常行为。")
        if (state.loading) CircularProgressIndicator()
        AdminCard("系统健康", state.health)
        AdminCard("存储统计", state.storage)
        AdminCard("备份计划与历史", state.backup)
        Button(onClick = viewModel::runBackup, modifier = Modifier.fillMaxWidth()) { Text("立即执行自动备份") }
        AdminCard("安全用户", state.users)
        AdminCard("审计日志", state.audit)
        OutlinedButton(onClick = viewModel::refresh, modifier = Modifier.fillMaxWidth()) { Text("刷新") }
        }
    }
}

@Composable private fun AdminCard(title: String, value: String) { Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { Text(title, fontWeight = FontWeight.Bold); Text(value.ifBlank { "暂无数据" }, style = MaterialTheme.typography.bodySmall) } } }
