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

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.dto.SiteSettingResponse
import com.lovejournal.app.data.repository.AuthRepository
import com.lovejournal.app.data.repository.SettingsRepository
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val loading: Boolean = false,
    val saving: Boolean = false,
    val setting: SiteSettingResponse? = null,
    val error: UiText? = null,
    /** 当前登录者的角色（"PartnerA" / "PartnerB" / "Visitor"），来自会话。 */
    val role: String? = null,
    /** 会话中记录的头像；设置页优先展示站点设置里按角色读取的头像。 */
    val sessionAvatar: String? = null,
    val uploadingAvatar: Boolean = false,
    val inviting: Boolean = false,
    /** 邀请成功标志：界面据此清空表单，随后应调用 [SettingsViewModel.clearInviteSuccess]。 */
    val inviteSucceeded: Boolean = false,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repository: SettingsRepository,
    private val authRepository: AuthRepository,
    private val serverConfig: ServerConfig,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<UiText?>(null)
    val message: StateFlow<UiText?> = _message.asStateFlow()

    /** 邀请另一半的专属反馈，显示在邀请卡片内部（避免与顶部全局消息混淆）。 */
    private val _inviteMessage = MutableStateFlow<UiText?>(null)
    val inviteMessage: StateFlow<UiText?> = _inviteMessage.asStateFlow()

    init {
        refresh()
        viewModelScope.launch {
            authRepository.sessionFlow.collect { s ->
                _state.value = _state.value.copy(role = s.role, sessionAvatar = s.avatar)
            }
        }
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.get().fold(
                onSuccess = { _state.value = SettingsUiState(setting = it, role = _state.value.role, sessionAvatar = _state.value.sessionAvatar) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.toUiText()) },
            )
        }
    }

    fun save(siteName: String?, loveStartDateIso: String?, allowRegistration: Boolean?) {
        _state.value = _state.value.copy(saving = true)
        viewModelScope.launch {
            repository.update(siteName, loveStartDateIso, allowRegistration).fold(
                onSuccess = {
                    _state.value = _state.value.copy(saving = false, setting = it)
                    _message.value = uiText(R.string.msg_saved)
                },
                onFailure = {
                    _state.value = _state.value.copy(saving = false)
                    _message.value = it.toUiText()
                },
            )
        }
    }

    /**
     * 上传头像并写回站点设置中当前登录者对应的头像字段
     * （PartnerA → partner_a_avatar，PartnerB → partner_b_avatar）。
     */
    fun uploadAvatar(uri: Uri) {
        if (_state.value.uploadingAvatar) return
        val isPartnerA = when (_state.value.role) {
            "PartnerA" -> true
            "PartnerB" -> false
            else -> {
                _message.value = uiText(R.string.settings_msg_avatar_partner_only)
                return
            }
        }
        _state.value = _state.value.copy(uploadingAvatar = true)
        viewModelScope.launch {
            repository.uploadAvatar(uri).fold(
                onSuccess = { url ->
                    val result = if (isPartnerA) {
                        repository.update(null, null, null, partnerAAvatar = url)
                    } else {
                        repository.update(null, null, null, partnerBAvatar = url)
                    }
                    result.fold(
                        onSuccess = {
                            _state.value = _state.value.copy(uploadingAvatar = false, setting = it)
                            _message.value = uiText(R.string.settings_msg_avatar_updated)
                        },
                        onFailure = {
                            _state.value = _state.value.copy(uploadingAvatar = false)
                            _message.value = it.toUiText()
                        },
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(uploadingAvatar = false)
                    _message.value = it.toUiText()
                },
            )
        }
    }

    /**
     * 为另一半开通账号：角色自动取当前登录者的相反名额（PartnerA↔PartnerB）。
     * 成功后当前会话保持不变，提示对方用新账号登录。
     */
    fun invitePartner(username: String, password: String, nickname: String) {
        if (_state.value.inviting) return
        val targetRole = when (_state.value.role) {
            "PartnerA" -> "PartnerB"
            "PartnerB" -> "PartnerA"
            else -> {
                _inviteMessage.value = uiText(R.string.register_error_not_partner)
                return
            }
        }
        if (!USERNAME_PATTERN.matches(username.trim())) {
            _inviteMessage.value = uiText(R.string.auth_error_username_format)
            return
        }
        if (password.length < 8 || !password.any { it.isLetter() } || !password.any { it.isDigit() }) {
            _inviteMessage.value = uiText(R.string.auth_error_password_format)
            return
        }
        if (nickname.isBlank()) {
            _inviteMessage.value = uiText(R.string.auth_error_nickname_required)
            return
        }
        _state.value = _state.value.copy(inviting = true)
        _inviteMessage.value = null
        viewModelScope.launch {
            authRepository.registerPartner(username.trim(), password, nickname.trim(), targetRole).fold(
                onSuccess = {
                    _state.value = _state.value.copy(inviting = false, inviteSucceeded = true)
                    _inviteMessage.value = uiText(R.string.settings_msg_invite_success)
                },
                onFailure = {
                    _state.value = _state.value.copy(inviting = false)
                    _inviteMessage.value = it.toUiText()
                },
            )
        }
    }

    /** 邀请成功并清空表单后调用，复位成功标志。 */
    fun clearInviteSuccess() {
        if (_state.value.inviteSucceeded) {
            _state.value = _state.value.copy(inviteSucceeded = false)
        }
    }

    /** 将服务器相对媒体路径解析为绝对 URL（如头像）。 */
    fun mediaUrl(path: String?): String? = serverConfig.mediaUrl(path)

    fun clearMessage() {
        _message.value = null
    }

    private companion object {
        /** 与服务器校验保持一致：3-32 位小写字母、数字或下划线。 */
        val USERNAME_PATTERN = Regex("^[a-z0-9_]{3,32}$")
    }
}
