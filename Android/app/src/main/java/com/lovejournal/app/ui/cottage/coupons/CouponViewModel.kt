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
import com.lovejournal.app.data.remote.dto.CouponResponse
import com.lovejournal.app.data.repository.CouponRepository
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
    val error: String? = null,
)

@HiltViewModel
class CouponViewModel @Inject constructor(
    private val repository: CouponRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CouponUiState())
    val state: StateFlow<CouponUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

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
                    _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败")
                },
            )
        }
    }

    fun add(title: String, description: String?, icon: String?, onDone: () -> Unit) {
        if (title.isBlank()) {
            _message.value = "请填写兑换券名称"
            return
        }
        viewModelScope.launch {
            repository.create(
                title = title.trim(),
                description = description?.trim()?.ifBlank { null },
                icon = icon?.trim()?.ifBlank { null },
            ).fold(
                onSuccess = { _message.value = "已送出兑换券"; onDone(); refresh() },
                onFailure = { _message.value = it.message ?: "添加失败" },
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
            _message.value = "请填写兑换券名称"
            return
        }
        viewModelScope.launch {
            repository.update(
                cpid = cpid,
                title = title.trim(),
                description = description?.trim()?.ifBlank { null },
                icon = icon?.trim()?.ifBlank { null },
            ).fold(
                onSuccess = { _message.value = "已更新兑换券"; onDone(); refresh() },
                onFailure = { _message.value = it.message ?: "更新失败" },
            )
        }
    }

    fun redeem(coupon: CouponResponse) {
        viewModelScope.launch {
            repository.redeem(coupon.cpid).fold(
                onSuccess = { _message.value = "已兑换 🎉"; refresh() },
                onFailure = { _message.value = it.message ?: "兑换失败" },
            )
        }
    }

    fun delete(coupon: CouponResponse) {
        viewModelScope.launch {
            repository.delete(coupon.cpid).fold(
                onSuccess = { _message.value = "已删除"; refresh() },
                onFailure = { _message.value = it.message ?: "删除失败" },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
