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

package com.lovejournal.app.ui.cottage.reports

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.dto.CottageMonthlyReportResponse
import com.lovejournal.app.data.repository.ReportRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.YearMonth
import javax.inject.Inject

data class ReportUiState(
    val loading: Boolean = false,
    val year: Int,
    val month: Int,
    val report: CottageMonthlyReportResponse? = null,
    val error: String? = null,
)

@HiltViewModel
class ReportViewModel @Inject constructor(
    private val repository: ReportRepository,
) : ViewModel() {

    private val today = LocalDate.now()
    private val _state = MutableStateFlow(ReportUiState(year = today.year, month = today.monthValue))
    val state: StateFlow<ReportUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        val current = _state.value
        _state.value = current.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.monthly(current.year, current.month).fold(
                onSuccess = { _state.value = _state.value.copy(loading = false, report = it, error = null) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败") },
            )
        }
    }

    fun prevMonth() = shiftMonth(-1)

    fun nextMonth() = shiftMonth(1)

    private fun shiftMonth(delta: Int) {
        val ym = YearMonth.of(_state.value.year, _state.value.month).plusMonths(delta.toLong())
        _state.value = _state.value.copy(year = ym.year, month = ym.monthValue)
        refresh()
    }
}
