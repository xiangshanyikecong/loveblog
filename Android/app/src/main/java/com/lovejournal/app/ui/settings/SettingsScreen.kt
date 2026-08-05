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

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
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
    onOpenRecycleBin: () -> Unit = {},
    onOpenAdminTools: () -> Unit = {},
    onOpenLicenses: () -> Unit = {},
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()

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
                    AccountEntryButtons(onOpenSecurity, onOpenRecycleBin, onOpenAdminTools, onOpenLicenses)
                    LogoutButton(onLogout)
                }
            else -> SettingsForm(
                setting = state.setting!!,
                saving = state.saving,
                message = message,
                onSave = { name, dateIso, allowReg -> viewModel.save(name, dateIso, allowReg) },
                onOpenSecurity = onOpenSecurity,
                onOpenRecycleBin = onOpenRecycleBin,
                onOpenAdminTools = onOpenAdminTools,
                onOpenLicenses = onOpenLicenses,
                onLogout = onLogout,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SettingsForm(
    setting: SiteSettingResponse,
    saving: Boolean,
    message: String?,
    onSave: (siteName: String?, loveStartDateIso: String?, allowRegistration: Boolean?) -> Unit,
    onOpenSecurity: () -> Unit,
    onOpenRecycleBin: () -> Unit,
    onOpenAdminTools: () -> Unit,
    onOpenLicenses: () -> Unit,
    onLogout: () -> Unit,
) {
    var siteName by remember(setting) { mutableStateOf(setting.site_name) }
    var allowReg by remember(setting) { mutableStateOf(setting.allow_registration) }
    var loveDate by remember(setting) { mutableStateOf(parseDate(setting.love_start_date)) }
    var showDatePicker by remember { mutableStateOf(false) }

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
        LoveSectionTitle("账户与维护")
        LoveSoftCard(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) { AccountEntryButtons(onOpenSecurity, onOpenRecycleBin, onOpenAdminTools, onOpenLicenses) } }
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

@Composable
private fun AccountEntryButtons(
    onOpenSecurity: () -> Unit,
    onOpenRecycleBin: () -> Unit,
    onOpenAdminTools: () -> Unit,
    onOpenLicenses: () -> Unit,
) {
    OutlinedButton(onClick = onOpenSecurity, modifier = Modifier.fillMaxWidth()) {
        Text("账号安全（修改密码 / 登录设备）")
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
    OutlinedButton(onClick = onLogout, modifier = Modifier.fillMaxWidth()) {
        Text("退出登录", color = MaterialTheme.colorScheme.error)
    }
}
