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

package com.lovejournal.app.ui.cottage.coupons

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.dto.CouponResponse
import com.lovejournal.app.data.repository.CouponRepository
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CouponUiState(
    val loading: Boolean = false,
    val items: List<CouponResponse> = emptyList(),
    val active: Int = 0,
    val redeemed: Int = 0,
    val error: UiText? = null,
)

@HiltViewModel
class CouponViewModel @Inject constructor(
    private val repository: CouponRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CouponUiState())
    val state: StateFlow<CouponUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<UiText?>(null)
    val message: StateFlow<UiText?> = _message.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.list().fold(
                onSuccess = {
                    _state.value = CouponUiState(
                        items = it.items,
                        active = it.active,
                        redeemed = it.redeemed,
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(loading = false, error = it.toUiText())
                },
            )
        }
    }

    fun add(title: String, description: String?, icon: String?, onDone: () -> Unit) {
        if (title.isBlank()) {
            _message.value = uiText(R.string.coupon_error_name_required)
            return
        }
        viewModelScope.launch {
            repository.create(
                title = title.trim(),
                description = description?.trim()?.ifBlank { null },
                icon = icon?.trim()?.ifBlank { null },
            ).fold(
                onSuccess = { _message.value = uiText(R.string.coupon_msg_sent); onDone(); refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun updateCoupon(
        cpid: String,
        title: String,
        description: String?,
        icon: String?,
        onDone: () -> Unit,
    ) {
        if (title.isBlank()) {
            _message.value = uiText(R.string.coupon_error_name_required)
            return
        }
        viewModelScope.launch {
            repository.update(
                cpid = cpid,
                title = title.trim(),
                description = description?.trim()?.ifBlank { null },
                icon = icon?.trim()?.ifBlank { null },
            ).fold(
                onSuccess = { _message.value = uiText(R.string.coupon_msg_updated); onDone(); refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun redeem(coupon: CouponResponse) {
        viewModelScope.launch {
            repository.redeem(coupon.cpid).fold(
                onSuccess = { _message.value = uiText(R.string.coupon_msg_redeemed); refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun delete(coupon: CouponResponse) {
        viewModelScope.launch {
            repository.delete(coupon.cpid).fold(
                onSuccess = { _message.value = uiText(R.string.msg_deleted); refresh() },
                onFailure = { _message.value = it.toUiText() },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
