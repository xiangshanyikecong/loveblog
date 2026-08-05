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

package com.lovejournal.app.ui.albums

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.dto.AlbumDetail
import android.net.Uri
import com.lovejournal.app.data.remote.dto.AlbumCreateRequest
import com.lovejournal.app.data.remote.dto.AlbumMediaRequest
import com.lovejournal.app.data.remote.dto.AlbumSummary
import com.lovejournal.app.data.repository.AlbumsRepository
import com.lovejournal.app.data.repository.UploadRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AlbumsUiState(
    val loading: Boolean = false,
    val albums: List<AlbumSummary> = emptyList(),
    val error: String? = null,
    val detail: AlbumDetail? = null,
    val detailLoading: Boolean = false,
    val detailError: String? = null,
    val saving: Boolean = false,
    val uploading: Boolean = false,
    val pendingImageUrl: String? = null,
    val message: String? = null,
)

@HiltViewModel
class AlbumsViewModel @Inject constructor(
    private val repository: AlbumsRepository,
    private val uploadRepository: UploadRepository,
    private val serverConfig: ServerConfig,
) : ViewModel() {

    private val _state = MutableStateFlow(AlbumsUiState())
    val state: StateFlow<AlbumsUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.list().fold(
                onSuccess = { _state.value = _state.value.copy(loading = false, albums = it, error = null) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败") },
            )
        }
    }

    fun open(albId: String) {
        _state.value = _state.value.copy(detailLoading = true, detailError = null, detail = null)
        viewModelScope.launch {
            repository.detail(albId).fold(
                onSuccess = { _state.value = _state.value.copy(detailLoading = false, detail = it) },
                onFailure = { _state.value = _state.value.copy(detailLoading = false, detailError = it.message ?: "加载失败") },
            )
        }
    }

    fun closeDetail() {
        _state.value = _state.value.copy(detail = null, detailError = null, detailLoading = false, pendingImageUrl = null)
    }

    fun upload(uri: Uri) {
        _state.value = _state.value.copy(uploading = true, message = null)
        viewModelScope.launch {
            uploadRepository.uploadAlbumImage(uri).fold(
                onSuccess = { _state.value = _state.value.copy(uploading = false, pendingImageUrl = it.url) },
                onFailure = { _state.value = _state.value.copy(uploading = false, message = it.message ?: "上传失败") },
            )
        }
    }

    fun save(title: String, description: String, tags: String) {
        if (title.isBlank()) { _state.value = _state.value.copy(message = "标题不能为空"); return }
        val current = _state.value.detail
        val imageUrl = _state.value.pendingImageUrl
        _state.value = _state.value.copy(saving = true, message = null)
        viewModelScope.launch {
            val result = if (current == null) {
                repository.create(
                    AlbumCreateRequest(
                        title = title.trim(),
                        description = description.trim().ifBlank { null },
                        cover_url = imageUrl,
                        tags = parseTags(tags),
                        media_items = imageUrl?.let { listOf(AlbumMediaRequest(file_url = it)) }.orEmpty(),
                    ),
                )
            } else repository.update(
                current.alb_id,
                AlbumCreateRequest(
                    title = title.trim(),
                    description = description.trim().ifBlank { null },
                    cover_url = imageUrl ?: current.cover_url,
                    is_encrypted = current.is_encrypted,
                    is_public = current.is_public,
                    visibility = current.visibility,
                    tags = parseTags(tags),
                    media_items = current.media_items.map {
                        AlbumMediaRequest(
                            media_type = it.media_type,
                            file_url = it.file_url,
                            thumbnail_url = it.thumbnail_url,
                            file_size = it.file_size,
                            mime_type = it.mime_type,
                            is_encrypted = it.is_encrypted,
                        )
                    } + imageUrl?.let { listOf(AlbumMediaRequest(file_url = it)) }.orEmpty(),
                ),
            )
            result.fold(
                onSuccess = { _state.value = _state.value.copy(saving = false, detail = it, pendingImageUrl = null, message = "保存成功"); refresh() },
                onFailure = { _state.value = _state.value.copy(saving = false, message = it.message ?: "保存失败") },
            )
        }
    }

    fun deleteCurrent() {
        val current = _state.value.detail ?: return
        viewModelScope.launch {
            repository.delete(current.alb_id).fold(
                onSuccess = { _state.value = _state.value.copy(detail = null, message = "已删除"); refresh() },
                onFailure = { _state.value = _state.value.copy(message = it.message ?: "删除失败") },
            )
        }
    }

    fun comment(content: String) {
        val current = _state.value.detail ?: return
        if (content.isBlank()) return
        viewModelScope.launch {
            repository.comment(current.alb_id, content.trim()).fold(
                onSuccess = { open(current.alb_id) },
                onFailure = { _state.value = _state.value.copy(message = it.message ?: "评论失败") },
            )
        }
    }

    fun clearMessage() { _state.value = _state.value.copy(message = null) }

    fun mediaUrl(path: String?): String? = serverConfig.mediaUrl(path)

    private fun parseTags(value: String): List<String> = value.split(',', '，').map(String::trim).filter(String::isNotBlank)
}
