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
import com.lovejournal.app.data.remote.dto.AnnualReportResponse
import com.lovejournal.app.data.remote.dto.CottageMonthlyReportResponse
import com.lovejournal.app.data.repository.AiFeatures
import com.lovejournal.app.data.repository.AiRepository
import com.lovejournal.app.data.repository.ReportRepository
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
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
    val error: UiText? = null,
    // ---- 恋爱年报 ----
    val annualLoading: Boolean = false,
    val annual: AnnualReportResponse? = null,
    val annualError: UiText? = null,
    // ---- AI 月报文案（status.enabled 且具备 monthly_report 特性时显示）----
    val aiEnabled: Boolean = false,
    val aiLoading: Boolean = false,
    val aiText: String? = null,
    val aiError: UiText? = null,
)

@HiltViewModel
class ReportViewModel @Inject constructor(
    private val repository: ReportRepository,
    private val aiRepository: AiRepository,
) : ViewModel() {

    private val today = LocalDate.now()
    private val _state = MutableStateFlow(ReportUiState(year = today.year, month = today.monthValue))
    val state: StateFlow<ReportUiState> = _state.asStateFlow()

    init {
        refresh()
        loadAnnual(today.year)
        viewModelScope.launch {
            aiRepository.status().onSuccess {
                _state.value = _state.value.copy(aiEnabled = it.enabled && it.features.contains(AiFeatures.MONTHLY_REPORT))
            }
        }
    }

    /** AI 按当前选中月份生成一段月报文案。 */
    fun generateAiText() {
        val current = _state.value
        if (current.aiLoading) return
        _state.value = current.copy(aiLoading = true, aiError = null)
        viewModelScope.launch {
            aiRepository.monthlyReport(current.year, current.month).fold(
                onSuccess = { _state.value = _state.value.copy(aiLoading = false, aiText = it.text) },
                onFailure = { _state.value = _state.value.copy(aiLoading = false, aiError = it.toUiText()) },
            )
        }
    }

    fun dismissAiText() {
        _state.value = _state.value.copy(aiText = null, aiError = null)
    }

    /** 恋爱年报（对齐网页端 /reports/annual）。 */
    fun loadAnnual(year: Int = _state.value.year) {
        viewModelScope.launch {
            _state.value = _state.value.copy(annualLoading = true, annualError = null)
            repository.annual(year).fold(
                onSuccess = { _state.value = _state.value.copy(annualLoading = false, annual = it) },
                onFailure = { _state.value = _state.value.copy(annualLoading = false, annualError = it.toUiText()) },
            )
        }
    }

    fun refresh() {
        val current = _state.value
        _state.value = current.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.monthly(current.year, current.month).fold(
                onSuccess = { _state.value = _state.value.copy(loading = false, report = it, error = null) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.toUiText()) },
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
