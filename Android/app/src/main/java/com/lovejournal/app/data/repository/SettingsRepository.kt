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

import android.content.ContentResolver
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.SiteSettingResponse
import com.lovejournal.app.data.remote.dto.SiteSettingUpdateRequest
import com.lovejournal.app.ui.components.UiTextException
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 主端·设置。仅暴露移动端有意义的字段（站点名 / 恋爱开始日 / 允许注册 / 伴侣头像）；
 * 服务器路径与媒体策略类配置不在移动端修改。网络直连。
 *
 * 注意：[SiteSettingUpdateRequest] 的头像字段为可空且 `explicitNulls=false` 时省略，
 * 因此"不修改"与"清空"无法区分——仅在真正设置头像时传非 null 值。
 */
@Singleton
class SettingsRepository @Inject constructor(
    private val api: LoveApiService,
    @ApplicationContext private val context: Context,
) {
    suspend fun get(): Result<SiteSettingResponse> = runCatching { api.settings() }

    suspend fun update(
        siteName: String?,
        loveStartDateIso: String?,
        allowRegistration: Boolean?,
        partnerAAvatar: String? = null,
        partnerBAvatar: String? = null,
    ): Result<SiteSettingResponse> = runCatching {
        api.updateSettings(
            SiteSettingUpdateRequest(
                site_name = siteName,
                love_start_date = loveStartDateIso,
                allow_registration = allowRegistration,
                partner_a_avatar = partnerAAvatar,
                partner_b_avatar = partnerBAvatar,
            ),
        )
    }

    /**
     * 上传头像到 /v1/uploads/avatars，返回服务器相对 URL。
     * 图片先经下采样并重编码为 JPEG，避免一张十几兆的原图直接占用上传带宽。
     */
    suspend fun uploadAvatar(uri: Uri): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val bytes = compressImage(context.contentResolver, uri)
            val body = bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
            api.uploadAvatar(MultipartBody.Part.createFormData("file", "avatar.jpg", body)).url
        }
    }

    private fun compressImage(resolver: ContentResolver, uri: Uri): ByteArray {
        // Pass 1: 只读尺寸，避免整图解码。
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
            ?: throw UiTextException(uiText(R.string.upload_error_read_image))

        // Pass 2: 下采样解码，最长边限制在约 MAX_EDGE。
        val decodeOptions = BitmapFactory.Options().apply {
            inSampleSize = calcInSampleSize(bounds.outWidth, bounds.outHeight, MAX_EDGE)
        }
        val bitmap = resolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, decodeOptions)
        } ?: throw UiTextException(uiText(R.string.upload_error_decode_image))

        return try {
            ByteArrayOutputStream().use { out ->
                bitmap.compress(Bitmap.CompressFormat.JPEG, QUALITY, out)
                out.toByteArray()
            }
        } finally {
            bitmap.recycle()
        }
    }

    private fun calcInSampleSize(width: Int, height: Int, maxEdge: Int): Int {
        if (width <= 0 || height <= 0) return 1
        var sample = 1
        val longest = maxOf(width, height)
        while (longest / sample > maxEdge) {
            sample *= 2
        }
        return sample
    }

    private companion object {
        const val MAX_EDGE = 1600
        const val QUALITY = 85
    }
}
