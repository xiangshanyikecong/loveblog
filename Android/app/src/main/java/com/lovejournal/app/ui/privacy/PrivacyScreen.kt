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

package com.lovejournal.app.ui.privacy

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSoftCard

/**
 * 隐私中心（对齐网页端 /privacy）：本站存了你们哪些数据、各自的可见范围、
 * 端到端加密状态、备份导出策略，以及最近与隐私相关的审计事件。
 * 只读展示；数据来自 /v1/privacy/summary。
 */
@Composable
fun PrivacyScreen(viewModel: PrivacyViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LovePage(modifier = Modifier.verticalScroll(rememberScrollState())) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            when {
                state.loading -> Row(
                    Modifier.fillMaxWidth().padding(24.dp),
                    horizontalArrangement = Arrangement.Center,
                ) { CircularProgressIndicator() }

                state.error != null -> Card(Modifier.fillMaxWidth()) {
                    Text(
                        "加载失败：${state.error}",
                        Modifier.padding(16.dp),
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }

                else -> {
                    PrivacyBlock("账号快照") {
                        InfoRow("昵称", state.accountNickname)
                        InfoRow("最近登录", state.lastLogin)
                        InfoRow("最近登录 IP", state.lastLoginIp)
                        InfoRow("密码最近修改", state.passwordChangedAt)
                        InfoRow("会话版本", state.sessionVersion)
                    }
                    PrivacyBlock("内容可见范围（全部模块）") {
                        InfoRow("公开可见", state.totalsPublic)
                        InfoRow("需登录", state.totalsSignedIn)
                        InfoRow("仅伴侣", state.totalsPartners)
                        InfoRow("仅作者", state.totalsAuthorOnly)
                        InfoRow("密码保护", state.totalsPassword)
                    }
                    PrivacyBlock("端到端加密状态") {
                        if (state.encryptionRows.isEmpty()) {
                            Text(
                                "尚未启用任何端到端加密模块",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        state.encryptionRows.forEach { row -> InfoRow(row.first, row.second) }
                    }
                    PrivacyBlock("备份导出策略") {
                        InfoRow("备份包加密", state.exportEncrypted)
                        InfoRow("包含上传文件", state.exportUploads)
                        InfoRow("服务器可读内容为明文", state.exportServerReadable)
                        InfoRow("端到端内容为密文", state.exportE2eeCipher)
                    }
                    if (state.recentActivity.isNotEmpty()) {
                        PrivacyBlock("最近的隐私相关事件") {
                            state.recentActivity.forEachIndexed { index, line ->
                                if (index > 0) HorizontalDivider(
                                    thickness = 0.5.dp,
                                    color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f),
                                )
                                Text(line, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                    state.generatedAt?.let {
                        Text(
                            "报告生成于 $it",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(bottom = 8.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PrivacyBlock(title: String, content: @Composable () -> Unit) {
    LoveSoftCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            content()
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            value.ifBlank { "—" },
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Medium,
        )
    }
}
