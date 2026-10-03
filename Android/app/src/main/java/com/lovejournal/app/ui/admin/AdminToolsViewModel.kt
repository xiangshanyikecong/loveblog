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
import com.lovejournal.app.R
import com.lovejournal.app.data.repository.AdminRepository
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AdminToolsUiState(
    val loading: Boolean = true,
    val health: UiText? = null,
    val audit: UiText? = null,
    val users: UiText? = null,
    val storage: UiText? = null,
    val backup: UiText? = null,
    val storageUsage: List<UiText> = emptyList(),
    val healthHistory: UiText? = null,
    val remediating: Boolean = false,
    val message: UiText? = null,
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
            health = health.await().fold({ UiText.Raw(it.toString()) }, { adminError(it) }),
            audit = audit.await().fold({ UiText.Raw(it.toString()) }, { adminError(it) }),
            users = users.await().fold({ UiText.Raw(it.toString()) }, { adminError(it) }),
            storage = storage.await().fold({ UiText.Raw(it.toString()) }, { adminError(it) }),
            backup = backup.await().fold(
                { uiText(R.string.admin_backup_summary, it.first.toString(), it.second.toString()) },
                { adminError(it) },
            ),
        )
    }
    fun runBackup() = viewModelScope.launch { repository.runBackup().fold(onSuccess = { _state.value = _state.value.copy(message = uiText(R.string.admin_msg_backup_done, it.toString())); refresh() }, onFailure = { _state.value = _state.value.copy(message = it.toUiText()) }) }

    fun loadMore() = viewModelScope.launch {
        val usage = async { repository.storageUsage() }
        val history = async { repository.healthHistory() }
        _state.value = _state.value.copy(
            storageUsage = usage.await().fold(
                { resp ->
                    val mb = { b: Long -> "%.1f MB".format(b / 1024.0 / 1024.0) }
                    buildList {
                        add(uiText(R.string.admin_storage_disk, mb(resp.disk.used_bytes), mb(resp.disk.total_bytes), "%.1f".format(resp.disk.percent)))
                        add(uiText(R.string.admin_storage_uploads, mb(resp.uploads.total_bytes), resp.uploads.file_count))
                        resp.database.size_bytes?.let { add(uiText(R.string.admin_storage_database, mb(it))) }
                        add(uiText(R.string.admin_storage_breakdown_title))
                        resp.breakdown.forEach { add(uiText(R.string.admin_storage_breakdown_item, it.category, mb(it.bytes), it.file_count)) }
                    }
                },
                { listOf(adminError(it)) },
            ),
            healthHistory = history.await().fold(
                { UiText.Raw(it.toString().take(1500)) },
                { adminError(it) },
            ),
        )
    }

    fun remediateNow() = viewModelScope.launch {
        _state.value = _state.value.copy(remediating = true)
        repository.remediate().fold(
            onSuccess = { el ->
                _state.value = _state.value.copy(remediating = false, message = uiText(R.string.admin_msg_remediated, el.toString().take(300)))
                refresh()
            },
            onFailure = {
                _state.value = _state.value.copy(remediating = false, message = it.toUiText())
            },
        )
    }

    fun clearMessage() { _state.value = _state.value.copy(message = null) }

    private companion object {
        /** 管理员接口对普通伴侣账号返回 403，缺省提示需保留「无权限」语义。 */
        fun adminError(t: Throwable): UiText =
            t.message?.let { UiText.Raw(it) } ?: uiText(R.string.admin_msg_no_permission_or_failed)
    }
}
