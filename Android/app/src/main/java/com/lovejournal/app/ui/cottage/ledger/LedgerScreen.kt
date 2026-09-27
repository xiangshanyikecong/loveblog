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

package com.lovejournal.app.ui.cottage.ledger

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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.data.remote.dto.LedgerResponse
import com.lovejournal.app.data.remote.dto.LedgerSummaryResponse
import com.lovejournal.app.ui.components.LoveConfirmDialog
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveEmptyState
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

private fun yuan(cents: Int): String = "¥" + "%.2f".format(cents / 100.0)

private fun splitLabel(value: String): String = when (value) {
    "treat" -> "请客"
    "owed_full" -> "全欠"
    else -> "AA"
}

@Composable
fun LedgerScreen(viewModel: LedgerViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()
    var editorOpen by rememberSaveable { mutableStateOf(false) }
    // LedgerResponse 不可 Bundle 化，只存 id，旋转后从已加载列表还原。
    var editingId by rememberSaveable { mutableStateOf<String?>(null) }
    val editing = editingId?.let { id -> state.items.firstOrNull { it.leid == id } }
    var pendingDelete by remember { mutableStateOf<LedgerResponse?>(null) }

    LovePage(contentPadding = PaddingValues(0.dp)) {
    Box(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize()) {
            message?.let {
                Text(
                    text = it,
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                )
            }
            when {
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
                        item { LedgerSummaryCard(summary) }
                    }
                    if (state.items.isEmpty()) {
                        item { LoveEmptyState("💰", "还没有账目", "记下第一笔共同支出吧", actionLabel = "记一笔", onAction = { editorOpen = true }) }
                    }
                    items(state.items, key = { it.leid }) { entry ->
                        LedgerCard(
                            entry = entry,
                            onEdit = { editingId = entry.leid },
                            onDelete = { pendingDelete = entry },
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
            Icon(Icons.Filled.Add, contentDescription = "记一笔")
        }
    }
    }

    if (editorOpen) {
        LedgerEditorDialog(
            onDismiss = { editorOpen = false },
            onSave = { title, amount, note, category, payer, splitType, spentOn ->
                viewModel.add(title, amount, note, category, payer, splitType, spentOn) { editorOpen = false }
            },
        )
    }

    editing?.let { entry ->
        // 响应里只有 payer_uid，按当前用户换算回「我付 / TA 付」来预填表单。
        LedgerEditorDialog(
            initial = entry,
            initialPayer = if (entry.payer_uid == state.selfUid) "me" else "partner",
            onDismiss = { editingId = null },
            onSave = { title, amount, note, category, payer, splitType, spentOn ->
                viewModel.update(entry, title, amount, note, category, payer, splitType, spentOn) {
                    editingId = null
                }
            },
        )
    }

    pendingDelete?.let { entry ->
        LoveConfirmDialog(
            title = "删除账目「${entry.title}」？",
            message = "删除后这笔记录将从账本中移除，无法恢复。",
            onConfirm = {
                viewModel.delete(entry)
                pendingDelete = null
            },
            onDismiss = { pendingDelete = null },
        )
    }
}

@Composable
private fun LedgerSummaryCard(summary: LedgerSummaryResponse) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("累计支出", style = MaterialTheme.typography.labelMedium)
            Text(
                yuan(summary.total_spent_cents),
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(6.dp))
            val balance = summary.balance
            Text(
                if (balance.settled) {
                    "账目已结清 🎉"
                } else {
                    "${balance.debtor_nickname ?: "TA"} 还欠 ${balance.creditor_nickname ?: "你"} ${yuan(balance.amount_cents)}"
                },
                style = MaterialTheme.typography.bodyMedium,
            )
            if (summary.by_category.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                summary.by_category.take(3).forEach { cat ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(cat.category, style = MaterialTheme.typography.bodySmall)
                        Text(yuan(cat.amount_cents), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
private fun LedgerCard(entry: LedgerResponse, onEdit: () -> Unit, onDelete: () -> Unit) {
    var menuOpen by remember { mutableStateOf(false) }
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(entry.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    entry.category?.takeIf { it.isNotBlank() }?.let {
                        Text("#$it", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                    }
                    Text(splitLabel(entry.split_type), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("${entry.payer_nickname} 付", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text(entry.spent_on, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
            }
            Text(yuan(entry.amount_cents), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
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
private fun LedgerEditorDialog(
    onDismiss: () -> Unit,
    onSave: (title: String, amountYuan: String, note: String?, category: String?, payer: String, splitType: String, spentOn: String) -> Unit,
    // 传入则为编辑模式：用既有账目预填表单；initialPayer 是换算回「me」/「partner」的付款方。
    initial: LedgerResponse? = null,
    initialPayer: String = "me",
) {
    var title by remember(initial?.leid) { mutableStateOf(initial?.title ?: "") }
    var amount by remember(initial?.leid) {
        mutableStateOf(initial?.let { "%.2f".format(it.amount_cents / 100.0) } ?: "")
    }
    var note by remember(initial?.leid) { mutableStateOf(initial?.note.orEmpty()) }
    var category by remember(initial?.leid) { mutableStateOf(initial?.category.orEmpty()) }
    var payer by remember(initial?.leid) { mutableStateOf(initialPayer) }
    var splitType by remember(initial?.leid) { mutableStateOf(initial?.split_type ?: "aa") }
    var spentOn by remember(initial?.leid) {
        mutableStateOf(initial?.spent_on?.takeIf { it.isNotBlank() }?.let(LocalDate::parse) ?: LocalDate.now())
    }
    var showDatePicker by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (initial == null) "记一笔" else "编辑账目") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("买了什么") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = amount,
                    onValueChange = { amount = it },
                    label = { Text("金额（元）") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = category,
                    onValueChange = { category = it },
                    label = { Text("分类，如 餐饮 / 出行（可选）") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("备注（可选）") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(10.dp))
                Text("谁付的", style = MaterialTheme.typography.labelMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(selected = payer == "me", onClick = { payer = "me" }, label = { Text("我付") })
                    FilterChip(selected = payer == "partner", onClick = { payer = "partner" }, label = { Text("TA 付") })
                }
                Spacer(Modifier.height(10.dp))
                Text("怎么算", style = MaterialTheme.typography.labelMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(selected = splitType == "aa", onClick = { splitType = "aa" }, label = { Text("AA") })
                    FilterChip(selected = splitType == "treat", onClick = { splitType = "treat" }, label = { Text("请客") })
                    FilterChip(selected = splitType == "owed_full", onClick = { splitType = "owed_full" }, label = { Text("全欠") })
                }
                Spacer(Modifier.height(10.dp))
                Text("日期", style = MaterialTheme.typography.labelMedium)
                OutlinedButton(onClick = { showDatePicker = true }, modifier = Modifier.fillMaxWidth()) {
                    Text(spentOn.toString())
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(title, amount, note, category, payer, splitType, spentOn.toString()) }) {
                Text("保存")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )

    if (showDatePicker) {
        val dateState = rememberDatePickerState(
            initialSelectedDateMillis = spentOn.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
        )
        DatePickerDialog(
            onDismissRequest = { showDatePicker = false },
            confirmButton = {
                TextButton(onClick = {
                    dateState.selectedDateMillis?.let { millis ->
                        spentOn = Instant.ofEpochMilli(millis).atZone(ZoneOffset.UTC).toLocalDate()
                    }
                    showDatePicker = false
                }) { Text("确定") }
            },
            dismissButton = { TextButton(onClick = { showDatePicker = false }) { Text("取消") } },
        ) {
            DatePicker(state = dateState)
        }
    }
}
