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

package com.lovejournal.app.ui.cottage.period

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.ui.components.LoveConfirmDialog
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.data.remote.dto.PeriodResponse
import com.lovejournal.app.data.remote.dto.PeriodSummaryResponse
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

private fun phaseLabel(phase: String): String = when (phase) {
    "in_period" -> "经期中"
    "due_soon" -> "即将到来"
    "overdue" -> "已推迟"
    "normal" -> "平稳期"
    else -> "暂无预测"
}

private fun daysHint(days: Int): String = when {
    days > 0 -> "还有 $days 天"
    days == 0 -> "就是今天"
    else -> "已推迟 ${-days} 天"
}

@Composable
fun PeriodScreen(viewModel: PeriodViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()
    var editorOpen by rememberSaveable { mutableStateOf(false) }
    // PeriodResponse 不可 Bundle 化，只存 id，旋转后从已加载列表还原。
    var editingId by rememberSaveable { mutableStateOf<String?>(null) }
    val editing = editingId?.let { id -> state.items.firstOrNull { it.pcid == id } }
    var pendingDelete by remember { mutableStateOf<PeriodResponse?>(null) }
    // 隐私遮挡：生理期属于敏感信息，默认整屏遮挡，需要时再显式展开。
    var privacyOn by rememberSaveable { mutableStateOf(true) }

    LovePage(contentPadding = PaddingValues(0.dp)) {
    Box(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = if (privacyOn) "内容已隐藏，仅自己可见" else "内容显示中",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                IconButton(onClick = { privacyOn = !privacyOn }) {
                    Icon(
                        imageVector = if (privacyOn) Icons.Filled.Visibility else Icons.Filled.VisibilityOff,
                        contentDescription = if (privacyOn) "显示生理期内容" else "隐藏生理期内容",
                        tint = MaterialTheme.colorScheme.primary,
                    )
                }
            }
            message?.let {
                Text(
                    text = it,
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                )
            }
            when {
                privacyOn -> Box(
                    Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            "🌸",
                            style = MaterialTheme.typography.displaySmall,
                        )
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "生理期内容已隐藏",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            "点右上角眼睛图标查看",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                state.loading && state.items.isEmpty() && state.summary == null ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                state.error != null && state.items.isEmpty() ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("加载失败：${state.error}", color = MaterialTheme.colorScheme.error)
                    }
                else -> LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    state.summary?.let { summary ->
                        item { PeriodSummaryCard(summary) }
                    }
                    if (state.items.isEmpty()) {
                        item { Text("还没有记录，点右下角记一次吧") }
                    }
                    items(state.items, key = { it.pcid }) { cycle ->
                        PeriodCard(
                            cycle = cycle,
                            onEdit = { editingId = cycle.pcid },
                            onDelete = { pendingDelete = cycle },
                        )
                    }
                }
            }
        }

        FloatingActionButton(
            onClick = { editorOpen = true },
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(20.dp),
        ) {
            Icon(Icons.Filled.Add, contentDescription = "记录")
        }
    }
    }

    if (editorOpen) {
        PeriodEditorDialog(
            onDismiss = { editorOpen = false },
            onSave = { start, end, note -> viewModel.add(start, end, note) { editorOpen = false } },
        )
    }

    editing?.let { cycle ->
        PeriodEditorDialog(
            initial = cycle,
            onDismiss = { editingId = null },
            onSave = { start, end, note ->
                viewModel.update(cycle, start, end, note) { editingId = null }
            },
        )
    }

    pendingDelete?.let { cycle ->
        LoveConfirmDialog(
            title = "删除这条生理期记录？",
            message = "记录区间 ${cycle.start_date}${cycle.end_date?.let { " ~ $it" } ?: ""} 将被删除，无法恢复。",
            onConfirm = {
                viewModel.delete(cycle)
                pendingDelete = null
            },
            onDismiss = { pendingDelete = null },
        )
    }
}

@Composable
private fun PeriodSummaryCard(summary: PeriodSummaryResponse) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("当前状态", style = MaterialTheme.typography.labelMedium)
            Text(phaseLabel(summary.phase), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            summary.predicted_next_start?.let { next ->
                Spacer(Modifier.height(4.dp))
                val hint = summary.predicted_days_until?.let { " · ${daysHint(it)}" } ?: ""
                Text("预计下次 $next$hint", style = MaterialTheme.typography.bodyMedium)
            }
            Spacer(Modifier.height(6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                summary.avg_cycle_days?.let {
                    Text("平均周期 $it 天", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                summary.avg_period_days?.let {
                    Text("平均经期 $it 天", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun PeriodCard(cycle: PeriodResponse, onEdit: () -> Unit, onDelete: () -> Unit) {
    var menuOpen by remember { mutableStateOf(false) }
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    cycle.start_date + (cycle.end_date?.let { " ~ $it" } ?: " 起（进行中）"),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                cycle.length_days?.let {
                    Text("持续 $it 天", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                cycle.note?.takeIf { it.isNotBlank() }?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (cycle.author_nickname.isNotBlank()) {
                    Text("记录人 ${cycle.author_nickname}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
                }
            }
            IconButton(onClick = { menuOpen = true }) {
                Icon(Icons.Filled.MoreHoriz, contentDescription = "更多操作")
            }
            DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                DropdownMenuItem(text = { Text("编辑") }, onClick = { menuOpen = false; onEdit() })
                DropdownMenuItem(text = { Text("删除") }, onClick = { menuOpen = false; onDelete() })
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PeriodEditorDialog(
    onDismiss: () -> Unit,
    onSave: (startDate: String, endDate: String?, note: String?) -> Unit,
    // 传入则为编辑模式：用既有记录预填表单。
    initial: PeriodResponse? = null,
) {
    var startDate by remember(initial?.pcid) {
        mutableStateOf(initial?.start_date?.takeIf { it.isNotBlank() }?.let(LocalDate::parse) ?: LocalDate.now())
    }
    var endDate by remember(initial?.pcid) {
        mutableStateOf(initial?.end_date?.takeIf { it.isNotBlank() }?.let(LocalDate::parse))
    }
    var note by remember(initial?.pcid) { mutableStateOf(initial?.note.orEmpty()) }
    var showStartPicker by remember { mutableStateOf(false) }
    var showEndPicker by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (initial == null) "记录生理期" else "编辑生理期") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                Text("开始日期", style = MaterialTheme.typography.labelMedium)
                OutlinedButton(onClick = { showStartPicker = true }, modifier = Modifier.fillMaxWidth()) {
                    Text(startDate.toString())
                }
                Spacer(Modifier.height(10.dp))
                Text("结束日期（可选，留空表示进行中）", style = MaterialTheme.typography.labelMedium)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { showEndPicker = true }, modifier = Modifier.weight(1f)) {
                        Text(endDate?.toString() ?: "未设置")
                    }
                    if (endDate != null) {
                        TextButton(onClick = { endDate = null }) { Text("清除") }
                    }
                }
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("备注（可选）") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(startDate.toString(), endDate?.toString(), note) }) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )

    if (showStartPicker) {
        val dateState = rememberDatePickerState(
            initialSelectedDateMillis = startDate.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
        )
        DatePickerDialog(
            onDismissRequest = { showStartPicker = false },
            confirmButton = {
                TextButton(onClick = {
                    dateState.selectedDateMillis?.let { millis ->
                        startDate = Instant.ofEpochMilli(millis).atZone(ZoneOffset.UTC).toLocalDate()
                    }
                    showStartPicker = false
                }) { Text("确定") }
            },
            dismissButton = { TextButton(onClick = { showStartPicker = false }) { Text("取消") } },
        ) {
            DatePicker(state = dateState)
        }
    }

    if (showEndPicker) {
        val dateState = rememberDatePickerState(
            initialSelectedDateMillis = (endDate ?: startDate).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
        )
        DatePickerDialog(
            onDismissRequest = { showEndPicker = false },
            confirmButton = {
                TextButton(onClick = {
                    dateState.selectedDateMillis?.let { millis ->
                        endDate = Instant.ofEpochMilli(millis).atZone(ZoneOffset.UTC).toLocalDate()
                    }
                    showEndPicker = false
                }) { Text("确定") }
            },
            dismissButton = { TextButton(onClick = { showEndPicker = false }) { Text("取消") } },
        ) {
            DatePicker(state = dateState)
        }
    }
}
