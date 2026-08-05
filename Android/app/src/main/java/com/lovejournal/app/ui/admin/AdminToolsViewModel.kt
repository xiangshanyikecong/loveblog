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

package com.lovejournal.app.ui.admin

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.repository.AdminRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AdminToolsUiState(
    val loading: Boolean = true,
    val health: String = "",
    val audit: String = "",
    val users: String = "",
    val storage: String = "",
    val backup: String = "",
    val message: String? = null,
)

@HiltViewModel
class AdminToolsViewModel @Inject constructor(private val repository: AdminRepository) : ViewModel() {
    private val _state = MutableStateFlow(AdminToolsUiState())
    val state: StateFlow<AdminToolsUiState> = _state.asStateFlow()
    init { refresh() }
    fun refresh() = viewModelScope.launch {
        _state.value = _state.value.copy(loading = true)
        val health = async { repository.health() }
        val audit = async { repository.auditLogs() }
        val users = async { repository.users() }
        val storage = async { repository.storage() }
        val backup = async { repository.backupInfo() }
        _state.value = AdminToolsUiState(
            loading = false,
            health = health.await().fold({ it.toString() }, { it.message ?: "无权限或加载失败" }),
            audit = audit.await().fold({ it.toString() }, { it.message ?: "无权限或加载失败" }),
            users = users.await().fold({ it.toString() }, { it.message ?: "无权限或加载失败" }),
            storage = storage.await().fold({ it.toString() }, { it.message ?: "无权限或加载失败" }),
            backup = backup.await().fold({ "计划：${it.first}\n历史：${it.second}" }, { it.message ?: "无权限或加载失败" }),
        )
    }
    fun runBackup() = viewModelScope.launch { repository.runBackup().fold(onSuccess = { _state.value = _state.value.copy(message = "备份任务已执行：$it"); refresh() }, onFailure = { _state.value = _state.value.copy(message = it.message ?: "备份失败") }) }
    fun clearMessage() { _state.value = _state.value.copy(message = null) }
}
