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
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.dto.SiteSettingResponse
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSectionTitle
import com.lovejournal.app.ui.components.LoveSoftCard
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.asString
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
                    Text(stringResource(R.string.status_loading))
                }
            state.setting == null ->
                Column(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    state.error?.let { Text(stringResource(R.string.msg_load_failed_with_error, it.asString()), color = MaterialTheme.colorScheme.error) }
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
    message: UiText?,
    inviteMessage: UiText?,
    onSave: (siteName: String?, loveStartDateIso: String?, allowRegistration: Boolean?) -> Unit,
    onPickAvatar: () -> Unit,
    onInvite: (username: String, password: String, nickname: String) -> Unit,
    onClearInviteSuccess: () -> Unit,
    onOpenSecurity: () -> Unit,
    onOpenPrivacy: () -> Unit,
    onOpenRecycleBin: () -> Unit,
    onOpenAdminTools: () -> Unit,
    onOpenLicenses: () -> Unit,
    onLogout: () -> Unit,
) {
    var siteName by remember(setting) { mutableStateOf(setting.site_name) }
    var allowReg by remember(setting) { mutableStateOf(setting.allow_registration) }
    var loveDate by remember(setting) { mutableStateOf(parseDate(setting.love_start_date)) }
    var inviteUsername by remember { mutableStateOf("") }
    var invitePassword by remember { mutableStateOf("") }
    var inviteNickname by remember { mutableStateOf("") }
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
        LoveSectionTitle(stringResource(R.string.settings_site_settings), stringResource(R.string.settings_site_settings_sub))
        message?.let { Text(it.asString(), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall) }
        LoveSoftCard(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.settings_basic_info), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            OutlinedTextField(value = siteName, onValueChange = { siteName = it }, label = { Text(stringResource(R.string.settings_site_name)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedButton(onClick = { showDatePicker = true }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.settings_love_start_date, loveDate?.toString() ?: stringResource(R.string.settings_love_start_date_not_set))) }
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) { Column { Text(stringResource(R.string.settings_allow_registration)); Text(stringResource(R.string.settings_allow_registration_sub), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }; Switch(checked = allowReg, onCheckedChange = { allowReg = it }) }
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
            Text(if (saving) stringResource(R.string.status_saving) else stringResource(R.string.btn_save_settings))
        }
        LoveSectionTitle(stringResource(R.string.settings_profile), stringResource(R.string.settings_profile_sub))
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
        LoveSectionTitle(stringResource(R.string.settings_account_maintenance))
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
                }) { Text(stringResource(R.string.btn_confirm)) }
            },
            dismissButton = { TextButton(onClick = { showDatePicker = false }) { Text(stringResource(R.string.btn_cancel)) } },
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
                    contentDescription = stringResource(R.string.settings_my_avatar),
                    modifier = Modifier
                        .size(56.dp)
                        .clip(CircleShape),
                    contentScale = ContentScale.Crop,
                )
            }
            Column(Modifier.weight(1f)) {
                Text(stringResource(R.string.settings_my_avatar), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(stringResource(R.string.settings_my_avatar_sub), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            OutlinedButton(onClick = onPickAvatar, enabled = !uploading) {
                if (uploading) {
                    CircularProgressIndicator(Modifier.size(16.dp).padding(2.dp), strokeWidth = 2.dp)
                } else {
                    Text(stringResource(R.string.settings_change_avatar))
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
    inviteMessage: UiText?,
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
            Text(stringResource(R.string.settings_invite_partner), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(
                stringResource(R.string.settings_invite_partner_desc),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = inviteUsername,
                onValueChange = onInviteUsernameChange,
                label = { Text(stringResource(R.string.settings_partner_username)) },
                supportingText = { Text(stringResource(R.string.auth_username_hint)) },
                enabled = !inviting,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = invitePassword,
                onValueChange = onInvitePasswordChange,
                label = { Text(stringResource(R.string.settings_partner_password)) },
                visualTransformation = PasswordVisualTransformation(),
                supportingText = { Text(stringResource(R.string.auth_password_hint)) },
                enabled = !inviting,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = inviteNickname,
                onValueChange = onInviteNicknameChange,
                label = { Text(stringResource(R.string.settings_partner_nickname)) },
                enabled = !inviting,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            inviteMessage?.let {
                Text(
                    it.asString(),
                    color = if (inviteSucceeded) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Button(
                onClick = { onInvite(inviteUsername, invitePassword, inviteNickname) },
                enabled = !inviting && inviteUsername.isNotBlank() && invitePassword.isNotBlank() && inviteNickname.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (inviting) stringResource(R.string.settings_inviting) else stringResource(R.string.settings_invite_partner_btn))
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
        Text(stringResource(R.string.settings_account_security))
    }
    OutlinedButton(onClick = onOpenPrivacy, modifier = Modifier.fillMaxWidth()) {
        Text(stringResource(R.string.settings_privacy_center))
    }
    OutlinedButton(onClick = onOpenRecycleBin, modifier = Modifier.fillMaxWidth()) {
        Text(stringResource(R.string.settings_recycle_bin))
    }
    OutlinedButton(onClick = onOpenAdminTools, modifier = Modifier.fillMaxWidth()) {
        Text(stringResource(R.string.settings_admin_tools))
    }
    OutlinedButton(onClick = onOpenLicenses, modifier = Modifier.fillMaxWidth()) {
        Text(stringResource(R.string.settings_open_licenses))
    }
}

@Composable
private fun LogoutButton(onLogout: () -> Unit) {
    OutlinedButton(onClick = onLogout, modifier = Modifier.fillMaxWidth()) {
        Text(stringResource(R.string.btn_logout), color = MaterialTheme.colorScheme.error)
    }
}
