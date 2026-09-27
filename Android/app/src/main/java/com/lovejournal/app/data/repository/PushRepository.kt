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

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import com.google.android.gms.tasks.Task
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.lovejournal.app.BuildConfig
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.FcmTokenDeleteRequest
import com.lovejournal.app.data.remote.dto.FcmTokenUpsertRequest
import com.lovejournal.app.push.FirebaseRuntimeConfig
import androidx.core.content.ContextCompat
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine

/** 推送链路自检快照：设置页推送卡片与配置向导共用的唯一数据源。 */
data class PushDiagnostics(
    val firebaseInitialized: Boolean,
    val importedConfigExists: Boolean,
    val importedInitError: String?,
    val permissionGranted: Boolean,
)

@Singleton
class PushRepository @Inject constructor(
    @ApplicationContext private val context: Context,
    private val api: LoveApiService,
    private val firebaseRuntime: FirebaseRuntimeConfig,
) {
    /** 应用启动时用应用内导入的配置手动初始化（默认构建没有 google-services 资源）。 */
    fun initializeFromPersistedConfig() = firebaseRuntime.initializeFromPersistedConfig()

    fun diagnostics(): PushDiagnostics = PushDiagnostics(
        firebaseInitialized = firebaseRuntime.isInitialized,
        importedConfigExists = firebaseRuntime.importedConfigExists,
        importedInitError = firebaseRuntime.lastInitError,
        permissionGranted = notificationPermissionGranted(),
    )

    fun notificationPermissionGranted(): Boolean =
        Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED

    /** 取当前 FCM token（Firebase 未初始化或设备无 Play 服务时失败）。 */
    suspend fun fetchToken(): Result<String> = runCatching {
        if (FirebaseApp.getApps(context).isEmpty()) {
            throw IllegalStateException("Firebase 尚未初始化")
        }
        FirebaseMessaging.getInstance().token.await()
    }

    /** 导入配置后的一键验证：取 token 并上报服务端注册。 */
    suspend fun registerAfterImport(): Result<String> = runCatching {
        val token = fetchToken().getOrThrow()
        registerFcmToken(token).getOrThrow()
        token
    }

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
