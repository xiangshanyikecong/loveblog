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

package com.lovejournal.app.data.repository

import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.CouponCreateRequest
import com.lovejournal.app.data.remote.dto.CouponListResponse
import com.lovejournal.app.data.remote.dto.CouponUpdateRequest
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 小屋·甜蜜兑换券。共享券册：任一方都可浏览与删除；仅对方（非出券人）可兑换。
 * 网络直连（与 Wishlist 范式一致），离线缓存留作后续增强。
 */
@Singleton
class CouponRepository @Inject constructor(
    private val api: LoveApiService,
) {
    /** @param box all/received/sent；status null=全部，active/redeemed 过滤。 */
    suspend fun list(box: String = "all", status: String? = null): Result<CouponListResponse> =
        runCatching { api.coupons(box, status) }

    suspend fun create(title: String, description: String?, icon: String?): Result<Unit> =
        runCatching {
            api.createCoupon(CouponCreateRequest(title = title, description = description, icon = icon))
            Unit
        }

    suspend fun update(cpid: String, title: String, description: String?, icon: String?): Result<Unit> =
        runCatching {
            api.updateCoupon(cpid, CouponUpdateRequest(title = title, description = description, icon = icon))
            Unit
        }

    suspend fun redeem(cpid: String): Result<Unit> = runCatching { api.redeemCoupon(cpid); Unit }

    suspend fun delete(cpid: String): Result<Unit> = runCatching {
        val response = api.deleteCoupon(cpid)
        if (!response.isSuccessful) throw IllegalStateException("删除失败 (${response.code()})")
        Unit
    }
}
