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
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.UploadResponse
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class UploadRepository @Inject constructor(
    private val api: LoveApiService,
    @ApplicationContext private val context: Context,
) {
    /**
     * Uploads a local image (camera capture or gallery pick) to the check-in
     * endpoint. The picture is down-sampled and re-encoded to JPEG first so a
     * 12-megapixel photo no longer streams tens of MB (or OOMs via readBytes()).
     */
    suspend fun uploadImage(uri: Uri): Result<UploadResponse> = withContext(Dispatchers.IO) {
        runCatching {
            val bytes = compressImage(context.contentResolver, uri)
            val body = bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
            val part = MultipartBody.Part.createFormData("file", "upload.jpg", body)
            api.uploadCheckinImage(part)
        }
    }

    suspend fun uploadAlbumImage(uri: Uri): Result<UploadResponse> = uploadCompressed(uri, api::uploadAlbumImage)

    suspend fun uploadArticleImage(uri: Uri): Result<UploadResponse> = uploadCompressed(uri, api::uploadArticleImage)

    private suspend fun uploadCompressed(
        uri: Uri,
        uploader: suspend (MultipartBody.Part) -> UploadResponse,
    ): Result<UploadResponse> = withContext(Dispatchers.IO) {
        runCatching {
            val bytes = compressImage(context.contentResolver, uri)
            val body = bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
            uploader(MultipartBody.Part.createFormData("file", "upload.jpg", body))
        }
    }

    private fun compressImage(resolver: ContentResolver, uri: Uri): ByteArray {
        // Pass 1: read just the dimensions so we never allocate the full bitmap.
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
            ?: throw IllegalStateException("无法读取所选图片")

        // Pass 2: decode down-sampled so the longest edge is ~MAX_EDGE.
        val decodeOptions = BitmapFactory.Options().apply {
            inSampleSize = calcInSampleSize(bounds.outWidth, bounds.outHeight, MAX_EDGE)
        }
        val bitmap = resolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, decodeOptions)
        } ?: throw IllegalStateException("无法解码所选图片")

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
