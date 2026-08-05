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

package com.lovejournal.app.ui.cottage.ledger

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.LedgerResponse
import com.lovejournal.app.data.remote.dto.LedgerSummaryResponse
import com.lovejournal.app.data.repository.LedgerRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import kotlin.math.roundToInt

data class LedgerUiState(
    val loading: Boolean = false,
    val items: List<LedgerResponse> = emptyList(),
    val summary: LedgerSummaryResponse? = null,
    val error: String? = null,
)

@HiltViewModel
class LedgerViewModel @Inject constructor(
    private val repository: LedgerRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(LedgerUiState())
    val state: StateFlow<LedgerUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            // 列表是主数据；汇总附带获取，失败不阻塞列表展示。
            val listResult = repository.list()
            val summary = repository.summary().getOrNull()
            listResult.fold(
                onSuccess = { list ->
                    _state.value = LedgerUiState(items = list.items, summary = summary)
                },
                onFailure = {
                    _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败")
                },
            )
        }
    }

    fun add(
        title: String,
        amountYuan: String,
        note: String?,
        category: String?,
        payer: String,
        splitType: String,
        spentOn: String,
        onDone: () -> Unit,
    ) {
        if (title.isBlank()) {
            _message.value = "请填写账目标题"
            return
        }
        val cents = parseYuanToCents(amountYuan)
        if (cents == null || cents <= 0) {
            _message.value = "请填写正确的金额"
            return
        }
        viewModelScope.launch {
            repository.create(
                title = title.trim(),
                amountCents = cents,
                note = note?.trim()?.ifBlank { null },
                category = category?.trim()?.ifBlank { null },
                payer = payer,
                splitType = splitType,
                spentOn = spentOn,
            ).fold(
                onSuccess = { _message.value = "已记一笔"; onDone(); refresh() },
                onFailure = { _message.value = it.message ?: "记账失败" },
            )
        }
    }

    fun delete(entry: LedgerResponse) {
        viewModelScope.launch {
            repository.delete(entry.leid).fold(
                onSuccess = { _message.value = "已删除"; refresh() },
                onFailure = { _message.value = it.message ?: "删除失败" },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}

/** "12.5"（元）-> 1250（分）；非数字或负数返回 null。 */
private fun parseYuanToCents(input: String): Int? {
    val value = input.trim().toDoubleOrNull() ?: return null
    if (value < 0) return null
    return (value * 100).roundToInt()
}
