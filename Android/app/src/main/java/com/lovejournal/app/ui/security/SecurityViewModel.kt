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

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.repository.SecurityRepository
import com.lovejournal.app.data.remote.dto.LoginDeviceResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SecurityUiState(
    val submitting: Boolean = false,
    // 操作成功后，当前会话已失效，需重新登录；用于禁用按钮并提示。
    val done: Boolean = false,
    // ---- 两步验证（TOTP）----
    val totpEnabled: Boolean = false,
    val totpRecoveryRemaining: Int = 0,
    val totpLoading: Boolean = false,
    /** setup 阶段返回的 secret + otpauth URI，展示给验证器 App 录入。 */
    val totpSecret: String? = null,
    val totpUri: String? = null,
    /** 开启成功的一次性恢复码（仅展示一次）。 */
    val totpRecoveryCodes: List<String> = emptyList(),
    // ---- 登录设备 ----
    val devices: List<LoginDeviceResponse> = emptyList(),
    val devicesLoading: Boolean = false,
)

@HiltViewModel
class SecurityViewModel @Inject constructor(
    private val repository: SecurityRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(SecurityUiState())
    val state: StateFlow<SecurityUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    private fun validNewPassword(pwd: String): Boolean =
        pwd.length in 8..128 && pwd.any { it.isLetter() } && pwd.any { it.isDigit() }

    fun changePassword(oldPassword: String, newPassword: String, confirmPassword: String) {
        when {
            oldPassword.isBlank() -> {
                _message.value = "请输入当前密码"
                return
            }
            !validNewPassword(newPassword) -> {
                _message.value = "新密码至少 8 位，且需同时包含字母和数字"
                return
            }
            newPassword != confirmPassword -> {
                _message.value = "两次输入的新密码不一致"
                return
            }
        }
        _state.value = _state.value.copy(submitting = true)
        viewModelScope.launch {
            repository.changePassword(oldPassword, newPassword).fold(
                onSuccess = {
                    _state.value = _state.value.copy(submitting = false, done = true)
                    _message.value = "密码已修改，请重新登录"
                },
                onFailure = {
                    _state.value = _state.value.copy(submitting = false)
                    _message.value = it.message ?: "修改失败"
                },
            )
        }
    }

    fun revokeOtherSessions() {
        _state.value = _state.value.copy(submitting = true)
        viewModelScope.launch {
            repository.revokeOtherSessions().fold(
                onSuccess = {
                    _state.value = _state.value.copy(submitting = false, done = true)
                    _message.value = "已登出所有设备，请重新登录"
                },
                onFailure = {
                    _state.value = _state.value.copy(submitting = false)
                    _message.value = it.message ?: "操作失败"
                },
            )
        }
    }

    // ---- 两步验证（TOTP）----

    fun loadTotpStatus() {
        viewModelScope.launch {
            _state.value = _state.value.copy(totpLoading = true)
            repository.totpStatus().fold(
                onSuccess = { resp ->
                    _state.value = _state.value.copy(
                        totpEnabled = resp.enabled,
                        totpRecoveryRemaining = resp.recovery_codes_remaining,
                        totpLoading = false,
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(totpLoading = false)
                    _message.value = it.message ?: "无法获取两步验证状态"
                },
            )
        }
    }

    fun startTotpSetup() {
        viewModelScope.launch {
            repository.totpSetup().fold(
                onSuccess = { resp ->
                    _state.value = _state.value.copy(totpSecret = resp.secret, totpUri = resp.uri)
                },
                onFailure = { _message.value = it.message ?: "无法开始绑定" },
            )
        }
    }

    fun confirmTotpEnable(code: String) {
        if (code.isBlank()) return
        viewModelScope.launch {
            repository.totpEnable(code).fold(
                onSuccess = { resp ->
                    _state.value = _state.value.copy(
                        totpEnabled = true,
                        totpSecret = null,
                        totpUri = null,
                        totpRecoveryCodes = resp.recovery_codes,
                    )
                    _message.value = "两步验证已开启，请妥善保存恢复码"
                },
                onFailure = { _message.value = it.message ?: "开启失败" },
            )
        }
    }

    fun confirmTotpDisable(code: String, password: String) {
        viewModelScope.launch {
            repository.totpDisable(code, password).fold(
                onSuccess = {
                    _state.value = _state.value.copy(totpEnabled = false, totpRecoveryRemaining = 0)
                    _message.value = "两步验证已关闭"
                },
                onFailure = { _message.value = it.message ?: "关闭失败" },
            )
        }
    }

    fun dismissRecoveryCodes() {
        _state.value = _state.value.copy(totpRecoveryCodes = emptyList())
    }

    // ---- 登录设备 ----

    fun loadDevices() {
        viewModelScope.launch {
            _state.value = _state.value.copy(devicesLoading = true)
            repository.loginDevices().fold(
                onSuccess = { devices ->
                    _state.value = _state.value.copy(devices = devices, devicesLoading = false)
                },
                onFailure = {
                    _state.value = _state.value.copy(devicesLoading = false)
                    _message.value = it.message ?: "无法获取登录设备"
                },
            )
        }
    }

    fun revokeDevice(did: String) {
        viewModelScope.launch {
            repository.revokeDevice(did).fold(
                onSuccess = {
                    _state.value = _state.value.copy(devices = _state.value.devices.filterNot { it.did == did })
                    _message.value = "该设备已登出"
                },
                onFailure = { _message.value = it.message ?: "撤销失败" },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
