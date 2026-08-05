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

package com.lovejournal.app.ui.cottage.coupons

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.data.remote.dto.CouponResponse

@Composable
fun CouponScreen(viewModel: CouponViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()
    var editorOpen by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<CouponResponse?>(null) }

    Box(modifier = Modifier.fillMaxSize().background(
        Brush.verticalGradient(
            listOf(
                MaterialTheme.colorScheme.background,
                MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.12f),
            ),
        ),
    )) {
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
                state.loading && state.items.isEmpty() ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                state.error != null && state.items.isEmpty() ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("加载失败：${state.error}", color = MaterialTheme.colorScheme.error)
                    }
                state.items.isEmpty() ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("还没有兑换券，点右下角送 TA 一张吧")
                    }
                else -> LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    item {
                        Text(
                            "有效 ${state.active} · 已兑换 ${state.redeemed}",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    items(state.items, key = { it.cpid }) { coupon ->
                        CouponCard(
                            coupon = coupon,
                            onRedeem = { viewModel.redeem(coupon) },
                            onEdit = { editing = coupon; editorOpen = true },
                            onDelete = { viewModel.delete(coupon) },
                        )
                    }
                }
            }
        }

        FloatingActionButton(
            onClick = { editing = null; editorOpen = true },
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(20.dp),
        ) {
            Icon(Icons.Filled.Add, contentDescription = "送一张券")
        }
    }

    if (editorOpen) {
        val current = editing
        CouponEditorDialog(
            initial = current,
            onDismiss = { editorOpen = false },
            onSave = { title, desc, icon ->
                if (current == null) {
                    viewModel.add(title, desc, icon) { editorOpen = false }
                } else {
                    viewModel.updateCoupon(current.cpid, title, desc, icon) { editorOpen = false }
                }
            },
        )
    }
}

@Composable
private fun CouponCard(coupon: CouponResponse, onRedeem: () -> Unit, onEdit: () -> Unit, onDelete: () -> Unit) {
    val redeemed = coupon.status == "redeemed"
    val canEdit = coupon.is_mine && !redeemed
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = if (redeemed) {
            CardDefaults.cardColors()
        } else {
            CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
        },
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                coupon.icon?.takeIf { it.isNotBlank() } ?: "🎟️",
                style = MaterialTheme.typography.headlineMedium,
            )
            Column(
                modifier = Modifier
                    .weight(1f)
                    .then(if (canEdit) Modifier.clickable { onEdit() } else Modifier),
            ) {
                Text(
                    coupon.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    textDecoration = if (redeemed) TextDecoration.LineThrough else TextDecoration.None,
                )
                coupon.description?.takeIf { it.isNotBlank() }?.let {
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    if (coupon.is_mine) "我送出的券" else "${coupon.author_nickname} 送给你",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (redeemed && coupon.redeemed_by_nickname != null) {
                    Text(
                        "已由 ${coupon.redeemed_by_nickname} 兑换",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.outline,
                    )
                }
            }
            Column(horizontalAlignment = Alignment.End) {
                if (!coupon.is_mine && !redeemed) {
                    FilledTonalButton(onClick = onRedeem) { Text("兑换") }
                }
                IconButton(onClick = onDelete) {
                    Icon(Icons.Filled.Delete, contentDescription = "删除", tint = MaterialTheme.colorScheme.error)
                }
            }
        }
    }
}

@Composable
private fun CouponEditorDialog(
    initial: CouponResponse?,
    onDismiss: () -> Unit,
    onSave: (title: String, description: String?, icon: String?) -> Unit,
) {
    var title by remember { mutableStateOf(initial?.title ?: "") }
    var description by remember { mutableStateOf(initial?.description ?: "") }
    var icon by remember { mutableStateOf(initial?.icon?.takeIf { it.isNotBlank() } ?: "🎟️") }
    val iconChoices = listOf("🎟️", "🤗", "💋", "🧹", "🍚", "☕", "🎁", "💆", "🛌", "🎮")

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (initial == null) "送 TA 一张券" else "编辑兑换券") },
        text = {
            Column {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("券名，如 一次免做家务券") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("使用说明（可选）") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                Text("图标", style = MaterialTheme.typography.labelMedium)
                Spacer(Modifier.height(4.dp))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    iconChoices.forEach { choice ->
                        FilterChip(
                            selected = icon == choice,
                            onClick = { icon = choice },
                            label = { Text(choice) },
                        )
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(title, description, icon) }) {
                Text(if (initial == null) "送出" else "保存")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
