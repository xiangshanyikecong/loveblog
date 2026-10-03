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

package com.lovejournal.app.ui.mood

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.R
import com.lovejournal.app.data.local.entity.MoodEntity
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.repository.MoodRepository
import com.lovejournal.app.data.repository.UploadRepository
import com.lovejournal.app.sync.SyncScheduler
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class MoodViewModel @Inject constructor(
    application: Application,
    private val moodRepository: MoodRepository,
    private val uploadRepository: UploadRepository,
    private val serverConfig: ServerConfig,
) : AndroidViewModel(application) {

    val moods: StateFlow<List<MoodEntity>> = moodRepository.observeAll()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    /** Resolves a server-relative media path (e.g. /uploads/x.jpg) to a full URL. */
    fun mediaUrl(path: String?): String? = serverConfig.mediaUrl(path)

    private val _status = MutableStateFlow<UiText?>(null)
    val status: StateFlow<UiText?> = _status.asStateFlow()

    private val _attachmentUrl = MutableStateFlow<String?>(null)
    val attachmentUrl: StateFlow<String?> = _attachmentUrl.asStateFlow()

    init {
        viewModelScope.launch { moodRepository.refreshToday() }
    }

    fun checkIn(mood: String, emoji: String?, note: String?) {
        viewModelScope.launch {
            val online = moodRepository.checkIn(mood, emoji, note)
            _status.value = if (online) uiText(R.string.mood_msg_recorded) else uiText(R.string.messages_msg_offline_saved)
            SyncScheduler.requestSyncNow(getApplication())
        }
    }

    fun uploadPhoto(uri: Uri) {
        viewModelScope.launch {
            _status.value = uiText(R.string.status_uploading)
            uploadRepository.uploadImage(uri)
                .onSuccess {
                    _attachmentUrl.value = it.url
                    _status.value = uiText(R.string.mood_msg_photo_uploaded)
                }
                .onFailure { _status.value = uiText(R.string.timeline_msg_photo_upload_failed, it.message.orEmpty()) }
        }
    }

    fun clearStatus() {
        _status.value = null
    }
}
