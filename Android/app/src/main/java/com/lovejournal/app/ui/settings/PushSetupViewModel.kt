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
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.FcmTokenResponse
import com.lovejournal.app.data.remote.dto.PushStatusResponse
import com.lovejournal.app.data.repository.PushDiagnostics
import com.lovejournal.app.data.repository.PushRepository
import com.lovejournal.app.push.FirebaseRuntimeConfig
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 推送配置状态卡 + 引导向导的共享状态（见 docs/design/FCM_IN_APP_SETUP_DESIGN.md）。
 * 配置状态全部可在运行时探测（服务端经 /push/status、客户端经 FirebaseApp），
 * 因此不需要持久化向导进度：每次进入都自动落到第一个缺失的步骤。
 */
@HiltViewModel
class PushSetupViewModel @Inject constructor(
    private val api: LoveApiService,
    private val pushRepository: PushRepository,
    private val firebaseRuntime: FirebaseRuntimeConfig,
) : ViewModel() {

    data class UiState(
        val loading: Boolean = true,
        val serverStatus: PushStatusResponse? = null,
        /** 旧版本服务端没有 /push/status：向导退化为展示完整步骤。 */
        val serverStatusUnavailable: Boolean = false,
        val diagnostics: PushDiagnostics? = null,
        val devices: List<FcmTokenResponse> = emptyList(),
        val busy: Boolean = false,
        val importError: String? = null,
        val importedToken: String? = null,
    ) {
        val serverReady: Boolean get() = serverStatus?.fcm?.runtime_ready == true
        val clientReady: Boolean get() = diagnostics?.firebaseInitialized == true
    }

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    private val _toast = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val toast: SharedFlow<String> = _toast.asSharedFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            val diagnostics = pushRepository.diagnostics()
            val status = runCatching { api.pushStatus() }
            val devices = runCatching { api.fcmTokenList().items }.getOrDefault(emptyList())
            _state.update {
                it.copy(
                    loading = false,
                    diagnostics = diagnostics,
                    serverStatus = status.getOrNull(),
                    serverStatusUnavailable = status.isFailure,
                    devices = devices,
                )
            }
        }
    }

    /** 应用内导入 google-services.json：解析 → 初始化 → 取 token → 上报注册。 */
    fun importConfig(uri: Uri) {
        if (_state.value.busy) return
        _state.update { it.copy(busy = true, importError = null) }
        viewModelScope.launch {
            try {
                firebaseRuntime.importConfig(uri)
            } catch (e: Exception) {
                _state.update { it.copy(busy = false, importError = e.message ?: "导入失败") }
                return@launch
            }
            pushRepository.registerAfterImport().fold(
                onSuccess = { token ->
                    _toast.tryEmit("推送配置成功，设备已注册")
                    _state.update { it.copy(busy = false, importedToken = token) }
                    refresh()
                },
                onFailure = { e ->
                    // 初始化已成功、注册失败（多为网络或服务端不可达）：可重试。
                    _state.update {
                        it.copy(
                            busy = false,
                            importError = "配置已生效，但设备注册失败：${e.message}",
                        )
                    }
                    refresh()
                },
            )
        }
    }

    /** 导入后注册失败的重试入口（S3 失败态按钮）。 */
    fun retryRegister() {
        if (_state.value.busy) return
        _state.update { it.copy(busy = true, importError = null) }
        viewModelScope.launch {
            pushRepository.registerAfterImport().fold(
                onSuccess = { token ->
                    _toast.tryEmit("设备已注册")
                    _state.update { it.copy(busy = false, importedToken = token) }
                },
                onFailure = { e ->
                    _state.update { it.copy(busy = false, importError = e.message ?: "注册失败") }
                },
            )
            refresh()
        }
    }

    /** 移除应用内配置：删除私有文件 + 注销 token（服务端 + 本地）+ 进程内重置。 */
    fun removeImportedConfig() {
        if (_state.value.busy) return
        viewModelScope.launch {
            runCatching { pushRepository.deleteLocalFcmToken() }
            firebaseRuntime.removeImportedConfig()
            _toast.tryEmit("已移除推送配置")
            _state.update { it.copy(importedToken = null, importError = null) }
            refresh()
        }
    }
}
