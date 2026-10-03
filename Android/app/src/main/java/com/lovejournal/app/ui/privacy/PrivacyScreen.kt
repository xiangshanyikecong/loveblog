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
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.R
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSoftCard
import com.lovejournal.app.ui.components.asString

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
                    state.error?.let { err ->
                        Text(
                            stringResource(R.string.msg_load_failed_with_error, err.asString()),
                            Modifier.padding(16.dp),
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }

                else -> {
                    PrivacyBlock(stringResource(R.string.privacy_account_snapshot)) {
                        InfoRow(stringResource(R.string.bootstrap_label_nickname), state.accountNickname)
                        InfoRow(stringResource(R.string.privacy_label_last_login), state.lastLogin)
                        InfoRow(stringResource(R.string.privacy_label_last_login_ip), state.lastLoginIp)
                        InfoRow(stringResource(R.string.privacy_label_password_changed), state.passwordChangedAt)
                        InfoRow(stringResource(R.string.privacy_label_session_version), state.sessionVersion)
                    }
                    PrivacyBlock(stringResource(R.string.privacy_visibility_title)) {
                        InfoRow(stringResource(R.string.privacy_visibility_public), state.totalsPublic)
                        InfoRow(stringResource(R.string.privacy_visibility_signed_in), state.totalsSignedIn)
                        InfoRow(stringResource(R.string.privacy_visibility_partners), state.totalsPartners)
                        InfoRow(stringResource(R.string.privacy_visibility_author_only), state.totalsAuthorOnly)
                        InfoRow(stringResource(R.string.privacy_visibility_password), state.totalsPassword)
                    }
                    PrivacyBlock(stringResource(R.string.privacy_encryption_title)) {
                        if (state.encryptionRows.isEmpty()) {
                            Text(
                                stringResource(R.string.privacy_encryption_none),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        state.encryptionRows.forEach { row -> InfoRow(row.first, row.second.asString()) }
                    }
                    PrivacyBlock(stringResource(R.string.privacy_export_title)) {
                        InfoRow(stringResource(R.string.privacy_export_encrypted), state.exportEncrypted.asString())
                        InfoRow(stringResource(R.string.privacy_export_uploads), state.exportUploads.asString())
                        InfoRow(stringResource(R.string.privacy_export_server_readable), state.exportServerReadable.asString())
                        InfoRow(stringResource(R.string.privacy_export_e2ee_cipher), state.exportE2eeCipher.asString())
                    }
                    if (state.recentActivity.isNotEmpty()) {
                        PrivacyBlock(stringResource(R.string.privacy_recent_activity)) {
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
                            stringResource(R.string.privacy_generated_at, it),
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
