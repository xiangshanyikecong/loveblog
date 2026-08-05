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
import javax.inject.Inject

data class LoginUiState(
    val loading: Boolean = false,
    val testingConnection: Boolean = false,
    val connectionOk: String? = null,
    val error: String? = null,
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
}
