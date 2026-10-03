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

package com.lovejournal.app.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Event
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Key
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Public
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.R
import com.lovejournal.app.ui.components.LoveHeroBrush
import com.lovejournal.app.ui.components.asString
import androidx.compose.ui.res.stringResource

@Composable
fun LoginScreen(viewModel: AuthViewModel = hiltViewModel()) {
    val state by viewModel.loginState.collectAsStateWithLifecycle()
    val bootstrapState by viewModel.bootstrapState.collectAsStateWithLifecycle()
    var server by remember { mutableStateOf(viewModel.currentServerAddress()) }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var showBootstrapDialog by remember { mutableStateOf(false) }
    var showRecoveryDialog by remember { mutableStateOf(false) }
    val recoveryState by viewModel.recoveryState.collectAsStateWithLifecycle()
    LaunchedEffect(recoveryState.success) {
        if (recoveryState.success) {
            showRecoveryDialog = false
            viewModel.resetRecoveryState()
        }
    }

    // 站点初始化状态懒加载检查（结果按地址缓存），仅在未初始化时展示引导入口。
    LaunchedEffect(server) { viewModel.checkBootstrapStatus(server) }
    // 初始化成功后预填登录用户名并回到登录表单。
    LaunchedEffect(bootstrapState.bootstrappedUsername) {
        bootstrapState.bootstrappedUsername?.let {
            username = it
            password = ""
            showBootstrapDialog = false
        }
    }

    Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.background)))) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.Center) {
            Box(Modifier.align(Alignment.CenterHorizontally).clip(MaterialTheme.shapes.extraLarge).background(LoveHeroBrush).padding(20.dp)) { Icon(Icons.Default.Favorite, null, tint = Color.White) }
            Text(stringResource(R.string.app_name), Modifier.align(Alignment.CenterHorizontally).padding(top = 14.dp), style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
            Text(stringResource(R.string.login_tagline), Modifier.align(Alignment.CenterHorizontally).padding(top = 4.dp, bottom = 24.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f)), elevation = CardDefaults.cardElevation(6.dp)) {
                Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Text(stringResource(R.string.login_welcome_back), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    OutlinedTextField(server, { server = it }, label = { Text(stringResource(R.string.login_server_address)) }, leadingIcon = { Icon(Icons.Default.Public, null) }, supportingText = { Text(viewModel.serverAddressHint().asString()) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) { OutlinedButton(onClick = { viewModel.testConnection(server) }, enabled = !state.loading && !state.testingConnection) { if (state.testingConnection) CircularProgressIndicator(Modifier.padding(2.dp), strokeWidth = 2.dp) else Text(stringResource(R.string.login_test_connection)) } }
                    OutlinedTextField(username, { username = it }, label = { Text(stringResource(R.string.login_username)) }, leadingIcon = { Icon(Icons.Default.Person, null) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(password, { password = it }, label = { Text(stringResource(R.string.login_password)) }, leadingIcon = { Icon(Icons.Default.Lock, null) }, visualTransformation = PasswordVisualTransformation(), singleLine = true, modifier = Modifier.fillMaxWidth())
                    state.connectionOk?.let { Text(it.asString(), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall) }
                    state.error?.let { Text(it.asString(), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                    Button(onClick = { viewModel.login(server, username, password) }, enabled = !state.loading && !state.testingConnection && username.isNotBlank() && password.isNotBlank(), modifier = Modifier.fillMaxWidth()) { if (state.loading) CircularProgressIndicator(strokeWidth = 2.dp) else Text(stringResource(R.string.btn_login)) }
                    TextButton(
                        onClick = { showRecoveryDialog = true },
                        enabled = !state.loading,
                        modifier = Modifier.align(Alignment.End),
                    ) { Text(stringResource(R.string.login_forgot_password)) }
                    if (state.showBootstrapEntry) {
                        Text(
                            stringResource(R.string.login_bootstrap_entry_hint),
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(top = 2.dp),
                        )
                        OutlinedButton(onClick = { showBootstrapDialog = true }, enabled = !state.loading && !state.testingConnection, modifier = Modifier.fillMaxWidth()) {
                            Text(stringResource(R.string.login_bootstrap_entry_btn))
                        }
                    }
                }
            }
        }
    }

    if (showRecoveryDialog) {
        PasswordRecoveryDialog(
            serverAddress = server,
            state = recoveryState,
            onSubmit = { user, pass, token -> viewModel.recoverPassword(server, user, pass, token) },
            onDismiss = {
                showRecoveryDialog = false
                viewModel.resetRecoveryState()
            },
        )
    }

    if (showBootstrapDialog) {
        BootstrapDialog(
            viewModel = viewModel,
            serverAddress = server,
            onDismiss = {
                showBootstrapDialog = false
                viewModel.resetBootstrapState()
            },
        )
    }
}

/**
 * 首次初始化引导弹窗：持有初始化令牌的一方创建 PartnerA 账号并设置站点信息。
 * 成功后服务器不会自动登录，直接回到登录表单（用户名已预填）。
 */
@Composable
private fun BootstrapDialog(
    viewModel: AuthViewModel,
    serverAddress: String,
    onDismiss: () -> Unit,
) {
    val state by viewModel.bootstrapState.collectAsStateWithLifecycle()
    val defaultSiteName = stringResource(R.string.app_name)
    var token by remember { mutableStateOf("") }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var nickname by remember { mutableStateOf("") }
    var siteName by remember { mutableStateOf(defaultSiteName) }
    var loveStartDate by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.bootstrap_dialog_title)) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    stringResource(R.string.bootstrap_dialog_desc),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall,
                )
                OutlinedTextField(token, { token = it }, label = { Text(stringResource(R.string.bootstrap_label_token)) }, leadingIcon = { Icon(Icons.Default.Key, null) }, visualTransformation = PasswordVisualTransformation(), singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(username, { username = it }, label = { Text(stringResource(R.string.login_username)) }, leadingIcon = { Icon(Icons.Default.Person, null) }, supportingText = { Text(stringResource(R.string.auth_username_hint)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(password, { password = it }, label = { Text(stringResource(R.string.login_password)) }, leadingIcon = { Icon(Icons.Default.Lock, null) }, visualTransformation = PasswordVisualTransformation(), supportingText = { Text(stringResource(R.string.auth_password_hint)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(nickname, { nickname = it }, label = { Text(stringResource(R.string.bootstrap_label_nickname)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(siteName, { siteName = it }, label = { Text(stringResource(R.string.settings_site_name)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(loveStartDate, { loveStartDate = it }, label = { Text(stringResource(R.string.bootstrap_label_love_start_date)) }, leadingIcon = { Icon(Icons.Default.Event, null) }, placeholder = { Text("yyyy-MM-dd") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                state.error?.let { Text(it.asString(), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            }
        },
        confirmButton = {
            Button(
                onClick = { viewModel.bootstrap(serverAddress, token, username, password, nickname, siteName, loveStartDate.ifBlank { null }) },
                enabled = !state.submitting && token.isNotBlank() && username.isNotBlank() && password.isNotBlank() && nickname.isNotBlank(),
            ) {
                if (state.submitting) CircularProgressIndicator(Modifier.padding(2.dp), strokeWidth = 2.dp) else Text(stringResource(R.string.bootstrap_dialog_title))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !state.submitting) { Text(stringResource(R.string.btn_cancel)) }
        },
    )
}

/**
 * 忘记密码自助找回：与网页端一致，凭部署时设定的恢复令牌
 * （BOOTSTRAP_SETUP_TOKEN）重置指定账号的密码。成功后该账号全部
 * 会话失效，用新密码重新登录即可。
 */
@Composable
private fun PasswordRecoveryDialog(
    serverAddress: String,
    state: RecoveryUiState,
    onSubmit: (String, String, String) -> Unit,
    onDismiss: () -> Unit,
) {
    var username by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var token by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = { if (!state.submitting) onDismiss() },
        title = { Text(stringResource(R.string.recovery_dialog_title)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    stringResource(R.string.recovery_dialog_desc),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(username, { username = it }, label = { Text(stringResource(R.string.login_username)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(newPassword, { newPassword = it }, label = { Text(stringResource(R.string.security_new_password)) }, visualTransformation = PasswordVisualTransformation(), singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(confirmPassword, { confirmPassword = it }, label = { Text(stringResource(R.string.security_confirm_password)) }, visualTransformation = PasswordVisualTransformation(), singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(token, { token = it }, label = { Text(stringResource(R.string.recovery_label_token)) }, visualTransformation = PasswordVisualTransformation(), singleLine = true, modifier = Modifier.fillMaxWidth())
                if (state.error != null) {
                    Text(state.error!!.asString(), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
                if (serverAddress.isBlank()) {
                    Text(stringResource(R.string.auth_error_no_server), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onSubmit(username, newPassword, token) },
                enabled = !state.submitting && username.isNotBlank() && newPassword.isNotBlank() && token.isNotBlank(),
            ) {
                if (state.submitting) CircularProgressIndicator(Modifier.padding(2.dp), strokeWidth = 2.dp) else Text(stringResource(R.string.recovery_btn_reset))
            }
        },
        dismissButton = { TextButton(onClick = onDismiss, enabled = !state.submitting) { Text(stringResource(R.string.btn_cancel)) } },
    )
}
