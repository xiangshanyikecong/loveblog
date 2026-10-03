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
import androidx.compose.ui.res.stringResource
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.R
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.asString

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
            Text(it.asString(), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
        }
        if (state.done) {
            Text(
                stringResource(R.string.security_done_relogin_msg),
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
        }

        Text(stringResource(R.string.security_change_password), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        OutlinedTextField(
            value = oldPassword,
            onValueChange = { oldPassword = it },
            label = { Text(stringResource(R.string.security_current_password)) },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = newPassword,
            onValueChange = { newPassword = it },
            label = { Text(stringResource(R.string.security_new_password)) },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = confirmPassword,
            onValueChange = { confirmPassword = it },
            label = { Text(stringResource(R.string.security_confirm_password)) },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )
        Text(
            stringResource(R.string.security_password_hint),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(
            onClick = { viewModel.changePassword(oldPassword, newPassword, confirmPassword) },
            enabled = !locked,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (state.submitting) stringResource(R.string.status_submitting) else stringResource(R.string.btn_change_password))
        }

        Spacer(Modifier.height(16.dp))

        // ---- 两步验证（TOTP）----
        Text(stringResource(R.string.security_totp_title), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(
            if (state.totpEnabled) {
                stringResource(R.string.security_totp_enabled_desc, state.totpRecoveryRemaining)
            } else {
                stringResource(R.string.security_totp_intro)
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(
            onClick = { showTotpDialog = true },
            enabled = !locked && !state.totpLoading,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (state.totpEnabled) stringResource(R.string.security_totp_manage) else stringResource(R.string.security_totp_enable))
        }
        if (state.totpRecoveryCodes.isNotEmpty()) {
            RecoveryCodesCard(
                codes = state.totpRecoveryCodes,
                onDismiss = viewModel::dismissRecoveryCodes,
            )
        }

        Spacer(Modifier.height(16.dp))

        // ---- 登录设备 ----
        Text(stringResource(R.string.security_login_devices), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(
            stringResource(R.string.security_login_devices_desc),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (state.devices.isEmpty()) {
            Text(
                if (state.devicesLoading) stringResource(R.string.status_loading) else stringResource(R.string.security_no_devices),
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
            Text(stringResource(R.string.btn_logout_all_devices), color = MaterialTheme.colorScheme.error)
        }
    }

    if (confirmRevoke) {
        AlertDialog(
            onDismissRequest = { confirmRevoke = false },
            title = { Text(stringResource(R.string.security_logout_all_confirm_title)) },
            text = { Text(stringResource(R.string.security_logout_all_confirm_msg)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmRevoke = false
                    viewModel.revokeOtherSessions()
                }) { Text(stringResource(R.string.btn_confirm), color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { confirmRevoke = false }) { Text(stringResource(R.string.btn_cancel)) } },
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
            Text(name.ifBlank { stringResource(R.string.security_unknown_device) }, style = MaterialTheme.typography.bodyMedium)
            Text(
                buildString {
                    append(lastLogin)
                    if (!ip.isNullOrBlank()) append(" · $ip")
                },
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        TextButton(onClick = onRevoke, enabled = enabled) { Text(stringResource(R.string.security_device_logout)) }
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
        Text(stringResource(R.string.security_recovery_codes_title), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
        Text(codes.joinToString("  "), style = MaterialTheme.typography.bodySmall)
        TextButton(onClick = onDismiss) { Text(stringResource(R.string.security_recovery_codes_saved)) }
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
        title = { Text(if (state.totpEnabled) stringResource(R.string.security_totp_disable_title) else stringResource(R.string.security_totp_enable)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.totpEnabled) {
                    OutlinedTextField(
                        value = code,
                        onValueChange = { code = it },
                        label = { Text(stringResource(R.string.security_totp_code_label)) },
                        singleLine = true,
                    )
                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = { Text(stringResource(R.string.security_totp_password_label)) },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                    )
                } else {
                    val secret = state.totpSecret
                    if (secret == null) {
                        Text(stringResource(R.string.security_totp_setup_intro))
                        Button(onClick = onStartSetup, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.security_totp_generate_secret)) }
                    } else {
                        Text(stringResource(R.string.security_totp_step_manual), style = MaterialTheme.typography.bodySmall)
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
                        Text(stringResource(R.string.security_totp_step_otpauth), style = MaterialTheme.typography.bodySmall)
                        Text(
                            state.totpUri ?: "",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 3,
                        )
                        Text(stringResource(R.string.security_totp_step_confirm), style = MaterialTheme.typography.bodySmall)
                        OutlinedTextField(
                            value = code,
                            onValueChange = { code = it },
                            label = { Text(stringResource(R.string.security_totp_code_label)) },
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
            ) { Text(if (state.totpEnabled) stringResource(R.string.security_totp_btn_disable) else stringResource(R.string.security_totp_btn_enable)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.btn_cancel)) } },
    )
}
