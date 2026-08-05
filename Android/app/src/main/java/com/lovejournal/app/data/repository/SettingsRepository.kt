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
import com.lovejournal.app.data.remote.dto.SiteSettingResponse
import com.lovejournal.app.data.remote.dto.SiteSettingUpdateRequest
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 主端·设置。仅暴露移动端有意义的字段（站点名 / 恋爱开始日 / 允许注册）；
 * 服务器路径与媒体策略类配置不在移动端修改。网络直连。
 */
@Singleton
class SettingsRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun get(): Result<SiteSettingResponse> = runCatching { api.settings() }

    suspend fun update(
        siteName: String?,
        loveStartDateIso: String?,
        allowRegistration: Boolean?,
    ): Result<SiteSettingResponse> = runCatching {
        api.updateSettings(
            SiteSettingUpdateRequest(
                site_name = siteName,
                love_start_date = loveStartDateIso,
                allow_registration = allowRegistration,
            ),
        )
    }
}
