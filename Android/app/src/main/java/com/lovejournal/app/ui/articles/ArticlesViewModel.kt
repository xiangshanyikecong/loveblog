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

package com.lovejournal.app.ui.articles

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.dto.ArticleDetail
import com.lovejournal.app.data.remote.dto.ArticleBlockRequest
import com.lovejournal.app.data.remote.dto.ArticleCreateRequest
import com.lovejournal.app.data.remote.dto.ArticleSummary
import com.lovejournal.app.data.remote.dto.ContentVersion
import com.lovejournal.app.data.repository.ArticlesRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ArticlesUiState(
    val loading: Boolean = false,
    val articles: List<ArticleSummary> = emptyList(),
    val error: String? = null,
    val detail: ArticleDetail? = null,
    val detailLoading: Boolean = false,
    val detailError: String? = null,
    val saving: Boolean = false,
    val versions: List<ContentVersion> = emptyList(),
    val message: String? = null,
)

@HiltViewModel
class ArticlesViewModel @Inject constructor(
    private val repository: ArticlesRepository,
    private val serverConfig: ServerConfig,
) : ViewModel() {

    private val _state = MutableStateFlow(ArticlesUiState())
    val state: StateFlow<ArticlesUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            repository.list().fold(
                onSuccess = { _state.value = _state.value.copy(loading = false, articles = it, error = null) },
                onFailure = { _state.value = _state.value.copy(loading = false, error = it.message ?: "加载失败") },
            )
        }
    }

    fun open(aid: String) {
        _state.value = _state.value.copy(detailLoading = true, detailError = null, detail = null)
        viewModelScope.launch {
            repository.detail(aid).fold(
                onSuccess = { _state.value = _state.value.copy(detailLoading = false, detail = it) },
                onFailure = { _state.value = _state.value.copy(detailLoading = false, detailError = it.message ?: "加载失败") },
            )
        }
    }

    fun closeDetail() {
        _state.value = _state.value.copy(detail = null, detailError = null, detailLoading = false, versions = emptyList())
    }

    fun save(title: String, excerpt: String, content: String, published: Boolean, tags: String) {
        if (title.isBlank() || content.isBlank()) {
            _state.value = _state.value.copy(message = "标题和正文不能为空")
            return
        }
        val current = _state.value.detail
        _state.value = _state.value.copy(saving = true, message = null)
        viewModelScope.launch {
            val result = if (current == null) {
                repository.create(
                    ArticleCreateRequest(
                        title = title.trim(),
                        excerpt = excerpt.trim().ifBlank { null },
                        status = if (published) "Published" else "Draft",
                        tags = parseTags(tags),
                        blocks = listOf(ArticleBlockRequest(content = content.trim())),
                    ),
                )
            } else {
                repository.update(
                    current.aid,
                    ArticleCreateRequest(
                        title = title.trim(),
                        excerpt = excerpt.trim().ifBlank { null },
                        status = if (published) "Published" else "Draft",
                        is_encrypted = current.is_encrypted,
                        visibility = current.visibility,
                        tags = parseTags(tags),
                        blocks = listOf(ArticleBlockRequest(content = content.trim())),
                    ),
                )
            }
            result.fold(
                onSuccess = {
                    _state.value = _state.value.copy(saving = false, detail = it, message = "保存成功")
                    refresh()
                },
                onFailure = { _state.value = _state.value.copy(saving = false, message = it.message ?: "保存失败") },
            )
        }
    }

    fun deleteCurrent() {
        val current = _state.value.detail ?: return
        _state.value = _state.value.copy(saving = true)
        viewModelScope.launch {
            repository.delete(current.aid).fold(
                onSuccess = {
                    _state.value = _state.value.copy(saving = false, detail = null, message = "已删除")
                    refresh()
                },
                onFailure = { _state.value = _state.value.copy(saving = false, message = it.message ?: "删除失败") },
            )
        }
    }

    fun comment(content: String) {
        val current = _state.value.detail ?: return
        if (content.isBlank()) return
        viewModelScope.launch {
            repository.comment(current.aid, content.trim()).fold(
                onSuccess = { open(current.aid) },
                onFailure = { _state.value = _state.value.copy(message = it.message ?: "评论失败") },
            )
        }
    }

    fun loadVersions() {
        val current = _state.value.detail ?: return
        viewModelScope.launch {
            repository.versions(current.aid).fold(
                onSuccess = { _state.value = _state.value.copy(versions = it) },
                onFailure = { _state.value = _state.value.copy(message = it.message ?: "版本加载失败") },
            )
        }
    }

    fun rollback(version: Int) {
        val current = _state.value.detail ?: return
        viewModelScope.launch {
            repository.rollback(current.aid, version).fold(
                onSuccess = { _state.value = _state.value.copy(detail = it, versions = emptyList(), message = "已回滚") ; refresh() },
                onFailure = { _state.value = _state.value.copy(message = it.message ?: "回滚失败") },
            )
        }
    }

    fun clearMessage() { _state.value = _state.value.copy(message = null) }

    fun mediaUrl(path: String?): String? = serverConfig.mediaUrl(path)

    private fun parseTags(value: String): List<String> = value.split(',', '，').map(String::trim).filter(String::isNotBlank)
}
