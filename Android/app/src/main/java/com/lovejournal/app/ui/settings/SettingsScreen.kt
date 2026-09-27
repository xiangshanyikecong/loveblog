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

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.saveable.rememberSaveable
import com.lovejournal.app.ui.components.LoveConfirmDialog
import coil.compose.AsyncImage
import com.lovejournal.app.data.remote.dto.SiteSettingResponse
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSectionTitle
import com.lovejournal.app.ui.components.LoveSoftCard
import java.time.Instant
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneOffset

private fun parseDate(iso: String?): LocalDate? {
    if (iso.isNullOrBlank()) return null
    return runCatching { OffsetDateTime.parse(iso).toLocalDate() }
        .recoverCatching { Instant.parse(iso).atZone(ZoneOffset.UTC).toLocalDate() }
        .recoverCatching { LocalDate.parse(iso.take(10)) }
        .getOrNull()
}

@Composable
fun SettingsScreen(
    onLogout: () -> Unit,
    onOpenSecurity: () -> Unit = {},
    onOpenPrivacy: () -> Unit = {},
    onOpenRecycleBin: () -> Unit = {},
    onOpenAdminTools: () -> Unit = {},
    onOpenLicenses: () -> Unit = {},
    onOpenPushSetup: () -> Unit = {},
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()
    val inviteMessage by viewModel.inviteMessage.collectAsStateWithLifecycle()

    val avatarPicker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        uri?.let(viewModel::uploadAvatar)
    }

    LovePage {
        when {
            state.loading && state.setting == null ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("加载中…")
                }
            state.setting == null ->
                Column(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    state.error?.let { Text("加载失败：$it", color = MaterialTheme.colorScheme.error) }
                    AccountEntryButtons(onOpenSecurity, onOpenPrivacy, onOpenRecycleBin, onOpenAdminTools, onOpenLicenses)
                    LogoutButton(onLogout)
                }
            else -> {
                val setting = state.setting!!
                // 我的头像：站点设置里按角色读取，读不到时退回会话记录的头像。
                val myAvatarPath = when (state.role) {
                    "PartnerA" -> setting.partner_a_avatar ?: state.sessionAvatar
                    "PartnerB" -> setting.partner_b_avatar ?: state.sessionAvatar
                    else -> state.sessionAvatar
                }
                SettingsForm(
                    setting = setting,
                    avatarUrl = viewModel.mediaUrl(myAvatarPath),
                    saving = state.saving,
                    uploadingAvatar = state.uploadingAvatar,
                    inviting = state.inviting,
                    inviteSucceeded = state.inviteSucceeded,
                    message = message,
                    inviteMessage = inviteMessage,
                    onSave = { name, dateIso, allowReg -> viewModel.save(name, dateIso, allowReg) },
                    onPickAvatar = {
                        avatarPicker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
                    },
                    onInvite = { username, password, nickname -> viewModel.invitePartner(username, password, nickname) },
                    onClearInviteSuccess = { viewModel.clearInviteSuccess() },
                    onOpenSecurity = onOpenSecurity,
                    onOpenPrivacy = onOpenPrivacy,
                    onOpenRecycleBin = onOpenRecycleBin,
                    onOpenAdminTools = onOpenAdminTools,
                    onOpenLicenses = onOpenLicenses,
                    onOpenPushSetup = onOpenPushSetup,
                    onLogout = onLogout,
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SettingsForm(
    setting: SiteSettingResponse,
    avatarUrl: String?,
    saving: Boolean,
    uploadingAvatar: Boolean,
    inviting: Boolean,
    inviteSucceeded: Boolean,
    message: String?,
    inviteMessage: String?,
    onSave: (siteName: String?, loveStartDateIso: String?, allowRegistration: Boolean?) -> Unit,
    onPickAvatar: () -> Unit,
    onInvite: (username: String, password: String, nickname: String) -> Unit,
    onClearInviteSuccess: () -> Unit,
    onOpenSecurity: () -> Unit,
    onOpenPrivacy: () -> Unit,
    onOpenRecycleBin: () -> Unit,
    onOpenAdminTools: () -> Unit,
    onOpenLicenses: () -> Unit,
    onOpenPushSetup: () -> Unit,
    onLogout: () -> Unit,
) {
    var siteName by remember(setting) { mutableStateOf(setting.site_name) }
    var allowReg by remember(setting) { mutableStateOf(setting.allow_registration) }
    var loveDate by remember(setting) { mutableStateOf(parseDate(setting.love_start_date)) }
    // 邀请密码同样不进 savedInstanceState；用户名/昵称保留 saveable。
    var inviteUsername by rememberSaveable { mutableStateOf("") }
    var invitePassword by remember { mutableStateOf("") }
    var inviteNickname by rememberSaveable { mutableStateOf("") }
    var showDatePicker by remember { mutableStateOf(false) }

    LaunchedEffect(inviteSucceeded) {
        if (inviteSucceeded) {
            inviteUsername = ""
            invitePassword = ""
            inviteNickname = ""
            onClearInviteSuccess()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        LoveSectionTitle("站点设置", "管理名称、纪念日和注册权限")
        message?.let { Text(it, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall) }
        LoveSoftCard(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("基础信息", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            OutlinedTextField(value = siteName, onValueChange = { siteName = it }, label = { Text("站点名称") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedButton(onClick = { showDatePicker = true }, modifier = Modifier.fillMaxWidth()) { Text("恋爱开始日 · ${loveDate?.toString() ?: "未设置"}") }
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) { Column { Text("允许新用户注册"); Text("关闭后仅现有账号可登录", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }; Switch(checked = allowReg, onCheckedChange = { allowReg = it }) }
        } }
        Button(
            onClick = {
                onSave(
                    siteName.trim().ifBlank { null },
                    loveDate?.atStartOfDay(ZoneOffset.UTC)?.toInstant()?.toString(),
                    allowReg,
                )
            },
            enabled = !saving,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (saving) "保存中…" else "保存设置")
        }
        LoveSectionTitle("个人资料", "头像与邀请另一半")
        AvatarCard(
            avatarUrl = avatarUrl,
            uploading = uploadingAvatar,
            onPickAvatar = onPickAvatar,
        )
        InvitePartnerCard(
            inviting = inviting,
            inviteSucceeded = inviteSucceeded,
            inviteMessage = inviteMessage,
            inviteUsername = inviteUsername,
            onInviteUsernameChange = { inviteUsername = it },
            invitePassword = invitePassword,
            onInvitePasswordChange = { invitePassword = it },
            inviteNickname = inviteNickname,
            onInviteNicknameChange = { inviteNickname = it },
            onInvite = onInvite,
        )
        LoveSectionTitle("通知与推送", "自托管服务器的消息推送（FCM）")
        PushStatusCard(onOpenSetup = onOpenPushSetup)
        LoveSectionTitle("账户与维护")
        LoveSoftCard(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) { AccountEntryButtons(onOpenSecurity, onOpenPrivacy, onOpenRecycleBin, onOpenAdminTools, onOpenLicenses) } }
        LogoutButton(onLogout)
    }

    if (showDatePicker) {
        val dateState = androidx.compose.material3.rememberDatePickerState(
            initialSelectedDateMillis = (loveDate ?: LocalDate.now())
                .atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
        )
        DatePickerDialog(
            onDismissRequest = { showDatePicker = false },
            confirmButton = {
                TextButton(onClick = {
                    dateState.selectedDateMillis?.let { millis ->
                        loveDate = Instant.ofEpochMilli(millis).atZone(ZoneOffset.UTC).toLocalDate()
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

/** 「我的头像」一行：圆形头像预览 + 换头像按钮（系统照片选择器）。 */
@Composable
private fun AvatarCard(
    avatarUrl: String?,
    uploading: Boolean,
    onPickAvatar: () -> Unit,
) {
    LoveSoftCard(Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(16.dp).fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (avatarUrl.isNullOrBlank()) {
                Box(
                    Modifier
                        .size(56.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primaryContainer),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Default.Person, contentDescription = null, tint = MaterialTheme.colorScheme.onPrimaryContainer)
                }
            } else {
                AsyncImage(
                    model = avatarUrl,
                    contentDescription = "我的头像",
                    modifier = Modifier
                        .size(56.dp)
                        .clip(CircleShape),
                    contentScale = ContentScale.Crop,
                )
            }
            Column(Modifier.weight(1f)) {
                Text("我的头像", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text("上传后对方也会看到你的新头像", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            OutlinedButton(onClick = onPickAvatar, enabled = !uploading) {
                if (uploading) {
                    CircularProgressIndicator(Modifier.size(16.dp).padding(2.dp), strokeWidth = 2.dp)
                } else {
                    Text("换头像")
                }
            }
        }
    }
}

/** 「邀请另一半」：为唯一空缺的对方伴侣名额开通账号。 */
@Composable
private fun InvitePartnerCard(
    inviting: Boolean,
    inviteSucceeded: Boolean,
    inviteMessage: String?,
    inviteUsername: String,
    onInviteUsernameChange: (String) -> Unit,
    invitePassword: String,
    onInvitePasswordChange: (String) -> Unit,
    inviteNickname: String,
    onInviteNicknameChange: (String) -> Unit,
    onInvite: (username: String, password: String, nickname: String) -> Unit,
) {
    LoveSoftCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("邀请另一半", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(
                "站点有且仅有两个伴侣名额。填写下方信息为对方开通账号，开通后 TA 即可用该账号登录。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = inviteUsername,
                onValueChange = onInviteUsernameChange,
                label = { Text("对方用户名") },
                supportingText = { Text("3-32 位小写字母、数字或下划线") },
                enabled = !inviting,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = invitePassword,
                onValueChange = onInvitePasswordChange,
                label = { Text("对方密码") },
                visualTransformation = PasswordVisualTransformation(),
                supportingText = { Text("至少 8 位，且同时包含字母和数字") },
                enabled = !inviting,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = inviteNickname,
                onValueChange = onInviteNicknameChange,
                label = { Text("对方昵称") },
                enabled = !inviting,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            inviteMessage?.let {
                Text(
                    it,
                    color = if (inviteSucceeded) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Button(
                onClick = { onInvite(inviteUsername, invitePassword, inviteNickname) },
                enabled = !inviting && inviteUsername.isNotBlank() && invitePassword.isNotBlank() && inviteNickname.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (inviting) "开通中…" else "为 TA 开通账号")
            }
        }
    }
}

@Composable
private fun AccountEntryButtons(
    onOpenSecurity: () -> Unit,
    onOpenPrivacy: () -> Unit,
    onOpenRecycleBin: () -> Unit,
    onOpenAdminTools: () -> Unit,
    onOpenLicenses: () -> Unit,
) {
    OutlinedButton(onClick = onOpenSecurity, modifier = Modifier.fillMaxWidth()) {
        Text("账号安全（修改密码 / 两步验证 / 登录设备）")
    }
    OutlinedButton(onClick = onOpenPrivacy, modifier = Modifier.fillMaxWidth()) {
        Text("隐私中心（数据与加密状态）")
    }
    OutlinedButton(onClick = onOpenRecycleBin, modifier = Modifier.fillMaxWidth()) {
        Text("回收站")
    }
    OutlinedButton(onClick = onOpenAdminTools, modifier = Modifier.fillMaxWidth()) {
        Text("服务器工具（健康 / 审计 / 用户 / 备份）")
    }
    OutlinedButton(onClick = onOpenLicenses, modifier = Modifier.fillMaxWidth()) {
        Text("开源许可证与版权声明")
    }
}

@Composable
private fun LogoutButton(onLogout: () -> Unit) {
    var confirmLogout by remember { mutableStateOf(false) }
    OutlinedButton(onClick = { confirmLogout = true }, modifier = Modifier.fillMaxWidth()) {
        Text("退出登录", color = MaterialTheme.colorScheme.error)
    }
    if (confirmLogout) {
        LoveConfirmDialog(
            title = "退出登录？",
            message = "退出后需要重新输入服务器地址与密码才能再次进入，未同步的数据会在下次登录后继续同步。",
            confirmText = "退出登录",
            onConfirm = {
                confirmLogout = false
                onLogout()
            },
            onDismiss = { confirmLogout = false },
        )
    }
}
