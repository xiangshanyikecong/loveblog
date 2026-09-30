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

package com.lovejournal.app.ui.settings

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSectionTitle
import com.lovejournal.app.ui.components.LoveSoftCard

// ---------------------------------------------------------------------------
// 服务端配置命令模板（向导内一键复制）
// ---------------------------------------------------------------------------

private const val CMD_SINGLE_LINE_BASH =
    "python3 -c \"import json,sys;print(json.dumps(json.load(open(sys.argv[1])),separators=(',',':')))\" serviceAccountKey.json"

private const val CMD_SINGLE_LINE_POWERSHELL =
    "(Get-Content serviceAccountKey.json -Raw | ConvertFrom-Json | ConvertTo-Json -Compress -Depth 100)"

private const val ENV_LINES =
    "FCM_PUSH_ENABLED=true\nFCM_SERVICE_ACCOUNT_JSON=<上一步得到的单行 JSON>"

private const val CMD_RESTART = "docker compose up -d"

/**
 * 设置页「通知与推送」状态卡：四态可辨（双缺 / 仅缺服务端 / 仅缺客户端 /
 * 就绪），共用 [PushSetupViewModel]，详细步骤在 [PushSetupScreen]。
 */
@Composable
fun PushStatusCard(
    onOpenSetup: () -> Unit,
    viewModel: PushSetupViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    PushStatusCardContent(state = state, onOpenSetup = onOpenSetup, onRefresh = viewModel::refresh)
}

@Composable
fun PushStatusCardContent(
    state: PushSetupViewModel.UiState,
    onOpenSetup: () -> Unit,
    onRefresh: () -> Unit,
) {
    LoveSoftCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("推送通知", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(
                        when {
                            state.loading -> "检测中…"
                            state.serverReady && state.clientReady -> "推送已就绪：服务端与本应用均已配置"
                            state.serverReady && !state.clientReady -> "服务端已就绪，本应用尚未配置"
                            state.clientReady && !state.serverReady -> "本应用已配置；服务端推送未启用或状态未知"
                            else -> "推送未启用，点击「配置推送」按引导开启"
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (state.loading) {
                    CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                } else {
                    when {
                        state.serverReady && state.clientReady -> Icon(
                            Icons.Outlined.CheckCircle,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                        )
                        else -> Icon(
                            Icons.Outlined.ErrorOutline,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            if (state.serverReady && state.clientReady && state.devices.isNotEmpty()) {
                Text(
                    "已注册设备：${state.devices.size} 台（" +
                        state.devices.joinToString("、") { it.device_name ?: "未知设备" } + "）",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onOpenSetup, modifier = Modifier.weight(1f)) {
                    Text(if (state.serverReady && state.clientReady) "查看推送状态" else "配置推送")
                }
                OutlinedButton(onClick = onRefresh) { Text("重新检测") }
            }
        }
    }
}

/**
 * FCM 配置向导：S1 服务端（.env + 重启命令）→ S2 本应用（应用内导入
 * google-services.json，免重打包）→ S3 验证（权限 / token / 已注册设备）。
 * 各步骤按探测结果自动显示完成态，可中断后随时续做。
 */
@Composable
fun PushSetupScreen(viewModel: PushSetupViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val clipboard = LocalClipboardManager.current
    val context = androidx.compose.ui.platform.LocalContext.current

    LaunchedEffect(Unit) { viewModel.refresh() }
    LaunchedEffect(Unit) {
        viewModel.toast.collect { message ->
            android.widget.Toast.makeText(context, message, android.widget.Toast.LENGTH_SHORT).show()
        }
    }

    val importLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let(viewModel::importConfig)
    }

    LovePage {
        Column(
            modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            LoveSectionTitle("推送配置向导", "为自托管服务器开启 Android 推送（FCM）")

            PushStatusCardContent(
                state = state,
                onOpenSetup = {},
                onRefresh = viewModel::refresh,
            )

            // ---- S1 服务端 ----
            LoveSectionTitle("第 1 步 · 服务端配置", "让服务器能向 Firebase 发送通知")
            LoveSoftCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    if (state.serverReady) {
                        StepDoneRow("服务端推送已启用")
                    } else {
                        Text(
                            "在 Firebase 控制台 → 项目设置 → 服务账号 → 生成新的私钥，下载得到 serviceAccountKey.json。把它压成单行填入服务端 .env：",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        CopyableCommand(
                            label = "Linux / macOS（压成单行）",
                            command = CMD_SINGLE_LINE_BASH,
                            onCopy = { clipboard.setText(AnnotatedString(it)) },
                        )
                        CopyableCommand(
                            label = "Windows PowerShell（压成单行）",
                            command = CMD_SINGLE_LINE_POWERSHELL,
                            onCopy = { clipboard.setText(AnnotatedString(it)) },
                        )
                        CopyableCommand(
                            label = "写入 .env（与 docker-compose.prod.yml 同目录）",
                            command = ENV_LINES,
                            onCopy = { clipboard.setText(AnnotatedString(it)) },
                        )
                        CopyableCommand(
                            label = "重启服务端",
                            command = CMD_RESTART,
                            onCopy = { clipboard.setText(AnnotatedString(it)) },
                        )
                        Text(
                            "完成后点「重新检测」确认服务端已就绪。私钥文件是敏感凭据，只放在服务器上，不要提交进仓库或发给别人。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
            }

            // ---- S2 本应用 ----
            LoveSectionTitle("第 2 步 · 本应用配置", "应用内导入配置，无需重新构建安装包")
            LoveSoftCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    if (state.clientReady) {
                        StepDoneRow(
                            if (state.diagnostics?.importedConfigExists == true) {
                                "已通过应用内导入的配置启用"
                            } else {
                                "本应用构建时已内置 Firebase 配置"
                            },
                        )
                        if (state.diagnostics?.importedConfigExists == true) {
                            OutlinedButton(onClick = viewModel::removeImportedConfig, enabled = !state.busy) {
                                Text("移除推送配置", color = MaterialTheme.colorScheme.error)
                            }
                        }
                    } else {
                        Text(
                            "在 Firebase 控制台 → 项目设置 → 常规 → 你的应用 → 添加 Android 应用，包名填 com.lovejournal.app，然后下载 google-services.json 并在下方导入。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Button(
                            onClick = {
                                importLauncher.launch(
                                    arrayOf("application/json", "application/octet-stream", "text/plain"),
                                )
                            },
                            enabled = !state.busy,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            if (state.busy) {
                                CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                            } else {
                                Text("导入 google-services.json")
                            }
                        }
                    }
                    state.importError?.let {
                        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                        if (state.clientReady) {
                            TextButton(onClick = viewModel::retryRegister, enabled = !state.busy) {
                                Text("重试设备注册")
                            }
                        }
                    }
                    state.diagnostics?.importedInitError?.let {
                        Text(
                            "上次启动初始化失败：$it",
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }

            // ---- S3 验证 ----
            LoveSectionTitle("第 3 步 · 验证", "通知权限与已注册设备")
            LoveSoftCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    val permission = state.diagnostics?.permissionGranted
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        StepIcon(granted = permission == true)
                        Column(Modifier.weight(1f)) {
                            Text("通知权限（Android 13+）")
                            Text(
                                if (permission == true) "已授予" else "未授予，点此前往系统设置开启",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    if (permission != true) {
                        OutlinedButton(
                            onClick = { openNotificationSettings(context) },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("打开系统通知设置")
                        }
                    }
                    if (state.devices.isEmpty()) {
                        Text(
                            "还没有已注册设备。完成上方步骤后，本机会自动注册。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        Text("已注册设备", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                        state.devices.forEach { device ->
                            Text(
                                "• ${device.device_name ?: "未知设备"} · ${device.app_version ?: "?"}" +
                                    if (device.is_active) "" else "（已停用）",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                    Text(
                        "最后验证：让对方给你发一条留言，通知应出现在系统通知栏。若服务端显示已启用但收不到，请检查服务端日志中的推送投递记录。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun StepDoneRow(text: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(Icons.Outlined.CheckCircle, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
        Text(text, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun StepIcon(granted: Boolean) {
    Icon(
        imageVector = if (granted) Icons.Outlined.CheckCircle else Icons.Outlined.ErrorOutline,
        contentDescription = null,
        tint = if (granted) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

/** 只读命令行 + 复制按钮。 */
@Composable
private fun CopyableCommand(
    label: String,
    command: String,
    onCopy: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            OutlinedTextField(
                value = command,
                onValueChange = {},
                readOnly = true,
                modifier = Modifier.weight(1f),
                textStyle = MaterialTheme.typography.bodySmall,
            )
            IconButton(onClick = { onCopy(command) }) {
                Icon(Icons.Default.ContentCopy, contentDescription = "复制")
            }
        }
    }
}

private fun openNotificationSettings(context: android.content.Context) {
    context.startActivity(
        Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
            .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName),
    )
}
