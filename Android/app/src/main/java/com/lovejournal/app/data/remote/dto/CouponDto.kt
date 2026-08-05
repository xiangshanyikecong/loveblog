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

package com.lovejournal.app.data.remote.dto

import kotlinx.serialization.Serializable

// ---------------------------------------------------------------------------
// 小屋·甜蜜兑换券 (cottage coupons) — /v1/cottage/coupons
// 字段名严格镜像后端 app.schemas.coupon (snake_case)。
// ---------------------------------------------------------------------------

@Serializable
data class CouponCreateRequest(
    val title: String,
    val description: String? = null,
    val icon: String? = null,
)

@Serializable
data class CouponUpdateRequest(
    val title: String? = null,
    val description: String? = null,
    val icon: String? = null,
)

@Serializable
data class CouponResponse(
    val cpid: String,
    val title: String,
    val description: String? = null,
    val icon: String? = null,
    // "active" | "redeemed" (app.models.coupon.CouponStatus)
    val status: String = "active",
    val author_uid: String = "",
    val author_nickname: String = "",
    // 当前查看者就是出券人时为 true（即「我送出的」券）。
    val is_mine: Boolean = false,
    val redeemed_at: String? = null,
    val redeemed_by_uid: String? = null,
    val redeemed_by_nickname: String? = null,
    val created_at: String = "",
)

@Serializable
data class CouponListResponse(
    val items: List<CouponResponse> = emptyList(),
    val total: Int = 0,
    val active: Int = 0,
    val redeemed: Int = 0,
)
