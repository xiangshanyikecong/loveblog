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
import com.lovejournal.app.R
import com.lovejournal.app.data.repository.SecurityRepository
import com.lovejournal.app.data.remote.dto.LoginDeviceResponse
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import com.lovejournal.app.ui.components.uiText
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

    private val _message = MutableStateFlow<UiText?>(null)
    val message: StateFlow<UiText?> = _message.asStateFlow()

    private fun validNewPassword(pwd: String): Boolean =
        pwd.length in 8..128 && pwd.any { it.isLetter() } && pwd.any { it.isDigit() }

    fun changePassword(oldPassword: String, newPassword: String, confirmPassword: String) {
        when {
            oldPassword.isBlank() -> {
                _message.value = uiText(R.string.security_error_current_password_required)
                return
            }
            !validNewPassword(newPassword) -> {
                _message.value = uiText(R.string.auth_error_password_format)
                return
            }
            newPassword != confirmPassword -> {
                _message.value = uiText(R.string.security_error_password_mismatch)
                return
            }
        }
        _state.value = _state.value.copy(submitting = true)
        viewModelScope.launch {
            repository.changePassword(oldPassword, newPassword).fold(
                onSuccess = {
                    _state.value = _state.value.copy(submitting = false, done = true)
                    _message.value = uiText(R.string.security_msg_password_changed)
                },
                onFailure = {
                    _state.value = _state.value.copy(submitting = false)
                    _message.value = it.toUiText()
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
                    _message.value = uiText(R.string.security_msg_logged_out_all)
                },
                onFailure = {
                    _state.value = _state.value.copy(submitting = false)
                    _message.value = it.toUiText()
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
                    _message.value = it.toUiText()
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
                onFailure = { _message.value = it.toUiText() },
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
                    _message.value = uiText(R.string.security_msg_totp_enabled)
                },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun confirmTotpDisable(code: String, password: String) {
        viewModelScope.launch {
            repository.totpDisable(code, password).fold(
                onSuccess = {
                    _state.value = _state.value.copy(totpEnabled = false, totpRecoveryRemaining = 0)
                    _message.value = uiText(R.string.security_msg_totp_disabled)
                },
                onFailure = { _message.value = it.toUiText() },
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
                    _message.value = it.toUiText()
                },
            )
        }
    }

    fun revokeDevice(did: String) {
        viewModelScope.launch {
            repository.revokeDevice(did).fold(
                onSuccess = {
                    _state.value = _state.value.copy(devices = _state.value.devices.filterNot { it.did == did })
                    _message.value = uiText(R.string.security_msg_device_revoked)
                },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
