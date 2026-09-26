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

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.BuildConfig
import com.lovejournal.app.data.prefs.SessionState
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.repository.AuthRepository
import com.lovejournal.app.util.isEmulator
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.ZoneOffset
import javax.inject.Inject

data class LoginUiState(
    val loading: Boolean = false,
    val testingConnection: Boolean = false,
    val connectionOk: String? = null,
    val error: String? = null,
    /** 站点尚未初始化时为 true，登录表单下方展示「首次使用？初始化站点」入口。 */
    val showBootstrapEntry: Boolean = false,
)

/** 首次初始化引导弹窗的状态。成功后 [bootstrappedUsername] 用于预填登录用户名。 */
data class BootstrapUiState(
    val submitting: Boolean = false,
    val error: String? = null,
    val bootstrappedUsername: String? = null,
)

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val serverConfig: ServerConfig,
) : ViewModel() {

    val session: StateFlow<SessionState> = authRepository.sessionFlow
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), SessionState())

    private val _loginState = MutableStateFlow(LoginUiState())
    val loginState: StateFlow<LoginUiState> = _loginState.asStateFlow()

    private val _bootstrapState = MutableStateFlow(BootstrapUiState())
    val bootstrapState: StateFlow<BootstrapUiState> = _bootstrapState.asStateFlow()

    /** 上次已检查初始化状态的服务器地址，用于按地址懒加载并缓存结果。 */
    private var bootstrapCheckedFor: String? = null

    fun currentServerAddress(): String = serverConfig.displayAddress()

    /** Hint text under the server field — differs for emulator vs real device. */
    fun serverAddressHint(): String =
        if (BuildConfig.ALLOW_CLEARTEXT_LOCAL && isEmulator()) {
            "模拟器调试可填 http://10.0.2.2:8000，若走域名反代则填 https://你的域名 或 https://你的域名/api"
        } else if (BuildConfig.ALLOW_CLEARTEXT_LOCAL) {
            "调试版可连接局域网私有地址；正式部署请填写 https://你的域名 或 https://你的域名/api"
        } else {
            "请填写启用 TLS 的地址，例如 https://你的域名 或 https://你的域名/api"
        }

    fun serverAddressPlaceholder(): String =
        if (BuildConfig.ALLOW_CLEARTEXT_LOCAL && isEmulator()) {
            "http://10.0.2.2:8000 或 https://example.com/api"
        } else {
            "https://example.com/api"
        }

    /**
     * 懒加载检查站点初始化状态（结果按地址缓存）。仅当填写了合法地址且与
     * 当前生效的服务器一致时才发起请求，避免把请求打到尚未确认的新地址上。
     */
    fun checkBootstrapStatus(serverAddress: String) {
        val invalid = serverAddress.isBlank() ||
            serverConfig.validateAddressInput(serverAddress) != null ||
            serverAddress.trim() != serverConfig.displayAddress().trim()
        if (invalid) {
            bootstrapCheckedFor = serverAddress
            hideBootstrapEntry()
            return
        }
        if (bootstrapCheckedFor == serverAddress) return
        bootstrapCheckedFor = serverAddress
        viewModelScope.launch {
            val notBootstrapped = authRepository.bootstrapStatus().getOrNull() == false
            _loginState.value = _loginState.value.copy(showBootstrapEntry = notBootstrapped)
        }
    }

    /**
     * 提交首次初始化：创建 PartnerA 并写入站点名称 / 恋爱开始日。
     * 成功后不会自动登录，[BootstrapUiState.bootstrappedUsername] 供登录表单预填。
     */
    fun bootstrap(
        serverAddress: String,
        bootstrapToken: String,
        username: String,
        password: String,
        nickname: String,
        siteName: String,
        loveStartDate: String?,
    ) {
        serverConfig.validateAddressInput(serverAddress)?.let { msg ->
            _bootstrapState.value = BootstrapUiState(error = msg)
            return
        }
        if (bootstrapToken.isBlank()) {
            _bootstrapState.value = BootstrapUiState(error = "请输入初始化令牌")
            return
        }
        if (!USERNAME_PATTERN.matches(username.trim())) {
            _bootstrapState.value = BootstrapUiState(error = "用户名需为 3-32 位小写字母、数字或下划线")
            return
        }
        if (password.length < 8 || !password.any { it.isLetter() } || !password.any { it.isDigit() }) {
            _bootstrapState.value = BootstrapUiState(error = "密码至少 8 位，且需同时包含字母和数字")
            return
        }
        if (nickname.isBlank()) {
            _bootstrapState.value = BootstrapUiState(error = "请输入昵称")
            return
        }
        val startDateIso = loveStartDate?.trim()?.takeIf { it.isNotEmpty() }?.let { raw ->
            runCatching { LocalDate.parse(raw).atStartOfDay(ZoneOffset.UTC).toInstant().toString() }
                .getOrElse {
                    _bootstrapState.value = BootstrapUiState(error = "恋爱开始日格式应为 yyyy-MM-dd")
                    return
                }
        }
        serverConfig.setAddress(serverAddress)
        _bootstrapState.value = BootstrapUiState(submitting = true)
        viewModelScope.launch {
            authRepository.bootstrap(
                bootstrapToken = bootstrapToken,
                username = username.trim(),
                password = password,
                nickname = nickname.trim(),
                siteName = siteName.trim().ifBlank { null },
                loveStartDateIso = startDateIso,
            ).fold(
                onSuccess = {
                    _bootstrapState.value = BootstrapUiState(bootstrappedUsername = username.trim())
                    // 站点已完成初始化，登录页不再显示引导入口。
                    bootstrapCheckedFor = null
                    _loginState.value = _loginState.value.copy(
                        showBootstrapEntry = false,
                        connectionOk = "初始化成功，请使用新账号登录",
                        error = null,
                    )
                },
                onFailure = { _bootstrapState.value = BootstrapUiState(error = it.message ?: "初始化失败") },
            )
        }
    }

    /** 关闭引导弹窗时清理其临时状态。 */
    fun resetBootstrapState() {
        if (_bootstrapState.value.bootstrappedUsername == null) {
            _bootstrapState.value = BootstrapUiState()
        }
    }

    private fun hideBootstrapEntry() {
        if (_loginState.value.showBootstrapEntry) {
            _loginState.value = _loginState.value.copy(showBootstrapEntry = false)
        }
    }

    fun testConnection(serverAddress: String) {
        serverConfig.validateAddressInput(serverAddress)?.let { msg ->
            _loginState.value = LoginUiState(error = msg)
            return
        }
        _loginState.value = LoginUiState(testingConnection = true)
        viewModelScope.launch {
            val result = authRepository.testConnection(serverAddress)
            _loginState.value = result.fold(
                onSuccess = {
                    serverConfig.setAddress(serverAddress)
                    // 地址已生效，重新检查初始化状态（原缓存按旧地址键控）。
                    bootstrapCheckedFor = null
                    checkBootstrapStatus(serverConfig.displayAddress())
                    LoginUiState(connectionOk = it)
                },
                onFailure = { LoginUiState(error = it.message ?: "连接失败") },
            )
        }
    }

    fun login(serverAddress: String, username: String, password: String) {
        serverConfig.validateAddressInput(serverAddress)?.let { msg ->
            _loginState.value = LoginUiState(error = msg)
            return
        }
        if (username.isBlank() || password.isBlank()) {
            _loginState.value = LoginUiState(error = "请输入用户名和密码")
            return
        }
        serverConfig.setAddress(serverAddress)
        _loginState.value = LoginUiState(loading = true)
        viewModelScope.launch {
            val result = authRepository.login(username, password)
            _loginState.value = result.fold(
                onSuccess = { LoginUiState() },
                onFailure = { LoginUiState(error = it.message ?: "登录失败") },
            )
        }
    }

    fun logout() {
        viewModelScope.launch { authRepository.logout() }
    }

    private companion object {
        /** 与服务器校验保持一致：3-32 位小写字母、数字或下划线。 */
        val USERNAME_PATTERN = Regex("^[a-z0-9_]{3,32}$")
    }
}
