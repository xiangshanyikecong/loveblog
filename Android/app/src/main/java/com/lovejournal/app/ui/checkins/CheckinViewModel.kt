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

package com.lovejournal.app.ui.checkins

import android.Manifest
import android.annotation.SuppressLint
import android.app.Application
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.CancellationSignal
import android.os.Looper
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.dto.CheckInResponse
import com.lovejournal.app.data.repository.CheckinRepository
import com.lovejournal.app.data.repository.UploadRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlin.coroutines.resume
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import javax.inject.Inject

data class CheckinUiState(
    val loading: Boolean = false,
    val items: List<CheckInResponse> = emptyList(),
    val total: Int = 0,
    val error: String? = null,
)

/** 正在编辑的报备草稿：已上传的照片路径、上传中 / 提交中标记。 */
data class CheckinDraft(
    val mediaUrls: List<String> = emptyList(),
    val uploading: Boolean = false,
    val submitting: Boolean = false,
    val locating: Boolean = false,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val locationPermissionDenied: Boolean = false,
    val locationMessage: String? = null,
)

@HiltViewModel
class CheckinViewModel @Inject constructor(
    application: Application,
    private val repository: CheckinRepository,
    private val uploadRepository: UploadRepository,
    private val serverConfig: ServerConfig,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(CheckinUiState())
    val state: StateFlow<CheckinUiState> = _state.asStateFlow()

    private val _draft = MutableStateFlow(CheckinDraft())
    val draft: StateFlow<CheckinDraft> = _draft.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        refresh()
    }

    /** server-relative "/uploads/..." -> 完整 URL，供 Coil 加载。 */
    fun mediaUrl(path: String?): String? = serverConfig.mediaUrl(path)

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.list().fold(
                onSuccess = { _state.value = CheckinUiState(items = it.items, total = it.total) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败") },
            )
        }
    }

    fun uploadPhoto(uri: Uri) {
        _draft.value = _draft.value.copy(uploading = true)
        viewModelScope.launch {
            uploadRepository.uploadImage(uri).fold(
                onSuccess = {
                    _draft.value = _draft.value.copy(
                        mediaUrls = _draft.value.mediaUrls + it.url,
                        uploading = false,
                    )
                },
                onFailure = {
                    _draft.value = _draft.value.copy(uploading = false)
                    _message.value = it.message ?: "图片上传失败"
                },
            )
        }
    }

    fun removePhoto(url: String) {
        _draft.value = _draft.value.copy(mediaUrls = _draft.value.mediaUrls - url)
    }

    fun captureLocation() {
        if (!hasLocationPermission()) {
            markLocationPermissionDenied()
            return
        }
        _draft.value = _draft.value.copy(
            locating = true,
            latitude = null,
            longitude = null,
            locationPermissionDenied = false,
            locationMessage = "正在获取位置…",
        )
        viewModelScope.launch {
            val location = runCatching { currentLocation() }.getOrNull()
            if (location != null) {
                _draft.value = _draft.value.copy(
                    locating = false,
                    latitude = location.latitude,
                    longitude = location.longitude,
                    locationPermissionDenied = false,
                    locationMessage = "已获取位置",
                )
            } else {
                _draft.value = _draft.value.copy(
                    locating = false,
                    latitude = null,
                    longitude = null,
                    locationPermissionDenied = false,
                    locationMessage = "暂时没有拿到位置",
                )
                _message.value = "暂时没有拿到位置，本次可先提交文字或照片"
            }
        }
    }

    fun markLocationPermissionDenied() {
        _draft.value = _draft.value.copy(
            locating = false,
            latitude = null,
            longitude = null,
            locationPermissionDenied = true,
            locationMessage = "已记录未授权位置",
        )
    }

    fun clearLocation() {
        _draft.value = _draft.value.copy(
            locating = false,
            latitude = null,
            longitude = null,
            locationPermissionDenied = false,
            locationMessage = null,
        )
    }

    fun submit(content: String, onDone: () -> Unit) {
        val text = content.trim().ifBlank { null }
        val draft = _draft.value
        val media = draft.mediaUrls
        val hasLocationIntent = (draft.latitude != null && draft.longitude != null) ||
            draft.locationPermissionDenied
        if (text == null && media.isEmpty() && !hasLocationIntent) {
            _message.value = "写点什么，或加一张照片吧"
            return
        }
        _draft.value = draft.copy(submitting = true)
        viewModelScope.launch {
            repository.create(
                content = text,
                mediaUrls = media,
                latitude = draft.latitude,
                longitude = draft.longitude,
                locationPermissionDenied = draft.locationPermissionDenied,
            ).fold(
                onSuccess = {
                    _draft.value = CheckinDraft()
                    _message.value = "已报备"
                    onDone()
                    refresh()
                },
                onFailure = {
                    _draft.value = _draft.value.copy(submitting = false)
                    _message.value = it.message ?: "报备失败"
                },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }

    private fun hasLocationPermission(): Boolean {
        val context = getApplication<Application>()
        return ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED
    }

    @Suppress("DEPRECATION", "OVERRIDE_DEPRECATION")
    @SuppressLint("MissingPermission")
    private suspend fun currentLocation(): Location? {
        val context = getApplication<Application>()
        val manager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val providers = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
            .filter { provider -> runCatching { manager.isProviderEnabled(provider) }.getOrDefault(false) }
        val lastKnown = providers
            .mapNotNull { provider -> runCatching { manager.getLastKnownLocation(provider) }.getOrNull() }
            .maxByOrNull { it.time }
        if (lastKnown != null && System.currentTimeMillis() - lastKnown.time < RECENT_LOCATION_MS) {
            return lastKnown
        }
        val provider = providers.firstOrNull() ?: return lastKnown
        return withTimeoutOrNull(LOCATION_TIMEOUT_MS) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                suspendCancellableCoroutine { continuation ->
                    val signal = CancellationSignal()
                    manager.getCurrentLocation(provider, signal, context.mainExecutor) { location ->
                        if (continuation.isActive) continuation.resume(location)
                    }
                    continuation.invokeOnCancellation { signal.cancel() }
                }
            } else {
                suspendCancellableCoroutine { continuation ->
                    val listener = object : LocationListener {
                        override fun onLocationChanged(location: Location) {
                            manager.removeUpdates(this)
                            if (continuation.isActive) continuation.resume(location)
                        }

                        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit
                        override fun onProviderEnabled(provider: String) = Unit
                        override fun onProviderDisabled(provider: String) = Unit
                    }
                    manager.requestSingleUpdate(provider, listener, Looper.getMainLooper())
                    continuation.invokeOnCancellation { manager.removeUpdates(listener) }
                }
            }
        } ?: lastKnown
    }

    private companion object {
        const val LOCATION_TIMEOUT_MS = 8_000L
        const val RECENT_LOCATION_MS = 5 * 60 * 1000L
    }
}
