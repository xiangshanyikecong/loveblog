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
import com.lovejournal.app.data.local.entity.MoodEntity
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.repository.MoodRepository
import com.lovejournal.app.data.repository.UploadRepository
import com.lovejournal.app.sync.SyncScheduler
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
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

    private val _status = MutableStateFlow<String?>(null)
    val status: StateFlow<String?> = _status.asStateFlow()

    private val _attachmentUrl = MutableStateFlow<String?>(null)
    val attachmentUrl: StateFlow<String?> = _attachmentUrl.asStateFlow()

    /** 打卡成功信号：界面收到后清空本屏的文字/心情选择，防止重复提交。 */
    private val _checkInSuccess = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val checkInSuccess: SharedFlow<Unit> = _checkInSuccess.asSharedFlow()

    private var submitting = false

    init {
        viewModelScope.launch { moodRepository.refreshToday() }
    }

    fun checkIn(mood: String, emoji: String?, note: String?) {
        if (submitting) return
        submitting = true
        viewModelScope.launch {
            try {
                val online = moodRepository.checkIn(mood, emoji, note)
                _status.value = if (online) "已记录今日心情" else "离线已保存，联网后自动同步"
                _attachmentUrl.value = null
                _checkInSuccess.tryEmit(Unit)
                SyncScheduler.requestSyncNow(getApplication())
            } finally {
                submitting = false
            }
        }
    }

    fun uploadPhoto(uri: Uri) {
        viewModelScope.launch {
            _status.value = "正在上传图片…"
            uploadRepository.uploadImage(uri)
                .onSuccess {
                    _attachmentUrl.value = it.url
                    _status.value = "图片已上传"
                }
                .onFailure { _status.value = "图片上传失败：${it.message}" }
        }
    }

    fun clearStatus() {
        _status.value = null
    }
}
