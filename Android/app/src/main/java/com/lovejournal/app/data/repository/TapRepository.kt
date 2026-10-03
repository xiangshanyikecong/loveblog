/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, version 3 of the License.
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

import com.lovejournal.app.R
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.TapCreateRequest
import com.lovejournal.app.data.remote.dto.TapListResponse
import com.lovejournal.app.data.remote.dto.TapResponse
import com.lovejournal.app.ui.components.UiTextException
import com.lovejournal.app.ui.components.uiText
import retrofit2.HttpException
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 小屋·轻触回应（敲一敲 / 心跳）。网络直连。
 * 发送端错误语义固定：404 = 站点还没有伴侣账号，429 = 超过 60 次/小时限频，
 * 两者均映射为三语 [UiTextException]，其余异常原样抛出由 toUiText 兜底。
 */
@Singleton
class TapRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun send(kind: String): Result<TapResponse> = runCatching {
        try {
            api.sendTap(TapCreateRequest(kind))
        } catch (e: HttpException) {
            when (e.code()) {
                404 -> throw UiTextException(uiText(R.string.tap_error_no_partner), e)
                429 -> throw UiTextException(uiText(R.string.tap_error_too_fast), e)
                else -> throw e
            }
        }
    }

    suspend fun recent(limit: Int = 20): Result<TapListResponse> =
        runCatching { api.recentTaps(limit = limit) }
}
