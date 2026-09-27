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

package com.lovejournal.app.ui.security

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.ui.components.LovePage

@Composable
fun SecurityScreen(viewModel: SecurityViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()

    var oldPassword by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var confirmRevoke by remember { mutableStateOf(false) }
    var showTotpDialog by remember { mutableStateOf(false) }

    // 进入页面即拉取两步验证状态与登录设备列表（对齐网页端安全中心）。
    LaunchedEffect(Unit) {
        viewModel.loadTotpStatus()
        viewModel.loadDevices()
    }

    val locked = state.submitting || state.done

    LovePage(modifier = Modifier.verticalScroll(rememberScrollState())) {
        message?.let {
            Text(it, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
        }
        if (state.done) {
            Text(
                "操作已生效，当前登录已失效，请退出后重新登录。",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
        }

        Text("修改密码", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        OutlinedTextField(
            value = oldPassword,
            onValueChange = { oldPassword = it },
            label = { Text("当前密码") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = newPassword,
            onValueChange = { newPassword = it },
            label = { Text("新密码") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = confirmPassword,
            onValueChange = { confirmPassword = it },
            label = { Text("确认新密码") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )
        Text(
            "新密码至少 8 位，需同时包含字母和数字。",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(
            onClick = { viewModel.changePassword(oldPassword, newPassword, confirmPassword) },
            enabled = !locked,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (state.submitting) "提交中…" else "修改密码")
        }

        Spacer(Modifier.height(16.dp))

        // ---- 两步验证（TOTP）----
        Text("两步验证", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(
            if (state.totpEnabled) {
                "已开启。登录时需输入验证器 App 的 6 位动态码（剩余恢复码 ${state.totpRecoveryRemaining} 个）。"
            } else {
                "绑定验证器 App（如 Google Authenticator）后，登录除了密码还需要动态码，可大幅提升账号安全性。"
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(
            onClick = { showTotpDialog = true },
            enabled = !locked && !state.totpLoading,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (state.totpEnabled) "管理两步验证" else "开启两步验证")
        }
        if (state.totpRecoveryCodes.isNotEmpty()) {
            RecoveryCodesCard(
                codes = state.totpRecoveryCodes,
                onDismiss = viewModel::dismissRecoveryCodes,
            )
        }

        Spacer(Modifier.height(16.dp))

        // ---- 登录设备 ----
        Text("登录设备", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(
            "最近登录过本账号的设备。发现陌生设备可单独将其登出；「登出所有设备」会让包括当前设备在内的全部登录失效。",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (state.devices.isEmpty()) {
            Text(
                if (state.devicesLoading) "加载中…" else "暂无设备记录",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                state.devices.forEach { device ->
                    DeviceRow(
                        name = device.device_name,
                        ip = device.ip,
                        lastLogin = device.last_login_at.take(16).replace('T', ' '),
                        onRevoke = { viewModel.revokeDevice(device.did) },
                        enabled = !locked,
                    )
                }
            }
        }
        OutlinedButton(
            onClick = { confirmRevoke = true },
            enabled = !locked,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("登出所有设备", color = MaterialTheme.colorScheme.error)
        }
    }

    if (confirmRevoke) {
        AlertDialog(
            onDismissRequest = { confirmRevoke = false },
            title = { Text("登出所有设备") },
            text = { Text("将立即让所有登录（含当前设备）失效，需要重新登录。确定继续吗？") },
            confirmButton = {
                TextButton(onClick = {
                    confirmRevoke = false
                    viewModel.revokeOtherSessions()
                }) { Text("确定", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { confirmRevoke = false }) { Text("取消") } },
        )
    }

    if (showTotpDialog) {
        TotpDialog(
            state = state,
            onDismiss = { showTotpDialog = false },
            onStartSetup = viewModel::startTotpSetup,
            onEnable = viewModel::confirmTotpEnable,
            onDisable = viewModel::confirmTotpDisable,
        )
    }
}

@Composable
private fun DeviceRow(name: String, ip: String?, lastLogin: String, onRevoke: () -> Unit, enabled: Boolean) {
    Row(
        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f))
            .padding(horizontal = 10.dp, vertical = 8.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Text(name.ifBlank { "未知设备" }, style = MaterialTheme.typography.bodyMedium)
            Text(
                buildString {
                    append(lastLogin)
                    if (!ip.isNullOrBlank()) append(" · $ip")
                },
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        TextButton(onClick = onRevoke, enabled = enabled) { Text("登出") }
    }
}

@Composable
private fun RecoveryCodesCard(codes: List<String>, onDismiss: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.5f))
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text("一次性恢复码（仅显示这一次，请保存到安全的地方）", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
        Text(codes.joinToString("  "), style = MaterialTheme.typography.bodySmall)
        TextButton(onClick = onDismiss) { Text("我已保存") }
    }
}

@Composable
private fun TotpDialog(
    state: SecurityUiState,
    onDismiss: () -> Unit,
    onStartSetup: () -> Unit,
    onEnable: (String) -> Unit,
    onDisable: (String, String) -> Unit,
) {
    var code by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (state.totpEnabled) "关闭两步验证" else "开启两步验证") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.totpEnabled) {
                    OutlinedTextField(
                        value = code,
                        onValueChange = { code = it },
                        label = { Text("验证器 6 位动态码") },
                        singleLine = true,
                    )
                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = { Text("账号密码") },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                    )
                } else {
                    val secret = state.totpSecret
                    if (secret == null) {
                        Text("首先在验证器 App 中准备一个账户，然后点击下方「生成密钥」获取绑定信息。")
                        Button(onClick = onStartSetup, modifier = Modifier.fillMaxWidth()) { Text("生成密钥") }
                    } else {
                        Text("1. 在验证器 App 中「手动输入密钥」添加账户：", style = MaterialTheme.typography.bodySmall)
                        Text(
                            secret,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp))
                                .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
                                .padding(10.dp),
                        )
                        Text("2. 或在支持 otpauth 的 App 中导入以下链接：", style = MaterialTheme.typography.bodySmall)
                        Text(
                            state.totpUri ?: "",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 3,
                        )
                        Text("3. 输入 App 显示的 6 位动态码完成绑定：", style = MaterialTheme.typography.bodySmall)
                        OutlinedTextField(
                            value = code,
                            onValueChange = { code = it },
                            label = { Text("动态码") },
                            singleLine = true,
                        )
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    if (state.totpEnabled) onDisable(code, password) else onEnable(code)
                    onDismiss()
                },
                enabled = code.isNotBlank() && (!state.totpEnabled || password.isNotBlank()),
            ) { Text(if (state.totpEnabled) "关闭" else "确认开启") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
