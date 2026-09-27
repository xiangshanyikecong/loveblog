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
            val bytes = compressImage(context.contentResolver, uri, MAX_EDGE, QUALITY)
            val body = bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
            val part = MultipartBody.Part.createFormData("file", "upload.jpg", body)
            api.uploadCheckinImage(part)
        }
    }

    suspend fun uploadAlbumImage(uri: Uri): Result<UploadResponse> = uploadCompressed(uri, api::uploadAlbumImage)

    suspend fun uploadArticleImage(uri: Uri): Result<UploadResponse> = uploadCompressed(uri, api::uploadArticleImage)

    /**
     * Uploads a local image (photo picker pick) to the timeline (moments)
     * endpoint. Shares the same down-sample + JPEG re-encode pipeline as the
     * album/article uploads so a multi-megapixel pick stays a few hundred KB.
     */
    suspend fun uploadTimelineImage(uri: Uri): Result<UploadResponse> = uploadCompressed(uri, api::uploadTimeline)

    private suspend fun uploadCompressed(
        uri: Uri,
        uploader: suspend (MultipartBody.Part) -> UploadResponse,
    ): Result<UploadResponse> = withContext(Dispatchers.IO) {
        runCatching {
            val bytes = compressImage(context.contentResolver, uri, MAX_EDGE, QUALITY)
            val body = bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
            uploader(MultipartBody.Part.createFormData("file", "upload.jpg", body))
        }
    }

    /**
     * 压缩本地图片到指定档位，产出 JPEG 字节（E2EE 加密聊天图片在加密前
     * 调用）。与明文上传共用两遍 decode 管线，档位可调以支持服务端密文
     * 25MB 上限的降质重压阶梯。
     */
    suspend fun compressChatImage(uri: Uri, maxEdge: Int = MAX_EDGE, quality: Int = QUALITY): ByteArray =
        withContext(Dispatchers.IO) { compressImage(context.contentResolver, uri, maxEdge, quality) }

    /**
     * 上传密文媒体字节到 /v1/uploads/chat-encrypted-media（application/
     * octet-stream，.enc 文件名）。密文即随机字节，服务端不做 MIME 白名单
     * 或图像处理；超限（25MB，HTTP 413）由调用方降档重压后重试。
     */
    suspend fun uploadEncryptedChatMedia(cipherBytes: ByteArray): Result<UploadResponse> =
        withContext(Dispatchers.IO) {
            runCatching {
                val body = cipherBytes.toRequestBody("application/octet-stream".toMediaTypeOrNull())
                api.uploadChatEncryptedMedia(
                    MultipartBody.Part.createFormData("file", "image.enc", body),
                )
            }
        }

    private fun compressImage(resolver: ContentResolver, uri: Uri, maxEdge: Int, quality: Int): ByteArray {
        // Pass 1: read just the dimensions so we never allocate the full bitmap.
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
            ?: throw IllegalStateException("无法读取所选图片")

        // Pass 2: decode down-sampled so the longest edge is ~maxEdge.
        val decodeOptions = BitmapFactory.Options().apply {
            inSampleSize = calcInSampleSize(bounds.outWidth, bounds.outHeight, maxEdge)
        }
        val bitmap = resolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, decodeOptions)
        } ?: throw IllegalStateException("无法解码所选图片")

        return try {
            ByteArrayOutputStream().use { out ->
                bitmap.compress(Bitmap.CompressFormat.JPEG, quality, out)
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
