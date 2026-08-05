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

import android.content.Context
import android.os.Build
import com.google.android.gms.tasks.Task
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.lovejournal.app.BuildConfig
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.FcmTokenDeleteRequest
import com.lovejournal.app.data.remote.dto.FcmTokenUpsertRequest
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine

@Singleton
class PushRepository @Inject constructor(
    @ApplicationContext private val context: Context,
    private val api: LoveApiService,
) {
    suspend fun registerCurrentFcmToken(): Result<Unit> = runCatching {
        val token = currentFcmToken() ?: return@runCatching
        registerFcmToken(token).getOrThrow()
    }

    suspend fun unregisterCurrentFcmToken(): Result<Unit> = runCatching {
        if (FirebaseApp.getApps(context).isEmpty()) return@runCatching
        val messaging = FirebaseMessaging.getInstance()
        val token = runCatching { messaging.token.await() }.getOrNull()
        val serverFailure = token?.let { unregisterFcmToken(it).exceptionOrNull() }

        // Always rotate the local token. If the unregister request could not
        // reach the server, any stale record there can no longer receive pushes.
        val localFailure = deleteLocalFcmToken().exceptionOrNull()
        serverFailure?.let { throw it }
        localFailure?.let { throw it }
        Unit
    }

    /**
     * Invalidates this installation's token without making an authenticated
     * API call. Used after a server-side session revocation: attempting the
     * unregister endpoint there would itself return 401 and emit another
     * session-expired event indefinitely.
     */
    suspend fun deleteLocalFcmToken(): Result<Unit> = runCatching {
        if (FirebaseApp.getApps(context).isEmpty()) return@runCatching
        FirebaseMessaging.getInstance().deleteToken().await()
    }

    suspend fun registerFcmToken(token: String): Result<Unit> = runCatching {
        if (token.isBlank()) return@runCatching
        api.upsertFcmToken(
            FcmTokenUpsertRequest(
                token = token,
                device_name = "${Build.MANUFACTURER} ${Build.MODEL}".trim(),
                app_version = BuildConfig.VERSION_NAME,
            ),
        )
    }

    suspend fun unregisterFcmToken(token: String): Result<Unit> = runCatching {
        if (token.isBlank()) return@runCatching
        val response = api.deleteFcmToken(FcmTokenDeleteRequest(token))
        if (!response.isSuccessful) {
            throw IllegalStateException("注销推送设备失败 (${response.code()})")
        }
    }

    private suspend fun currentFcmToken(): String? {
        if (FirebaseApp.getApps(context).isEmpty()) return null
        return FirebaseMessaging.getInstance().token.await()
    }
}

private suspend fun <T> Task<T>.await(): T =
    suspendCancellableCoroutine { continuation ->
        addOnSuccessListener { result -> continuation.resume(result) }
        addOnFailureListener { error -> continuation.resumeWithException(error) }
        addOnCanceledListener { continuation.cancel() }
    }
