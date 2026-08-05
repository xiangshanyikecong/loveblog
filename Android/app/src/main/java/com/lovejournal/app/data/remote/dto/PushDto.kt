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

@Serializable
data class FcmTokenUpsertRequest(
    val token: String,
    val platform: String = "android",
    val device_name: String? = null,
    val app_version: String? = null,
)

@Serializable
data class FcmTokenDeleteRequest(
    val token: String,
)

@Serializable
data class FcmTokenResponse(
    val tid: String = "",
    val platform: String = "android",
    val device_name: String? = null,
    val app_version: String? = null,
    val is_active: Boolean = true,
)
