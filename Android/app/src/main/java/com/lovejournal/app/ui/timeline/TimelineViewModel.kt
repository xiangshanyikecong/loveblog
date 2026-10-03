/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

package com.lovejournal.app.ui.timeline

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.paging.Pager
import androidx.paging.PagingConfig
import androidx.paging.PagingData
import androidx.paging.PagingSource
import androidx.paging.cachedIn
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.dto.MomentResponse
import com.lovejournal.app.data.repository.TimelineRepository
import com.lovejournal.app.data.repository.UploadRepository
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/** 时间线顶部分栏。动态 = 常规动态流（可发帖 / 评论 / 删除）；回忆 = 往年今日（只读）。 */
enum class TimelineTab { MOMENTS, MEMORIES }

/**
 * 时间线页面的 UI 状态。动态流本身走 Paging（[TimelineViewModel.moments]），
 * 这里只保留回忆分栏与发布流程的字段。
 */
data class TimelineUiState(
    val selectedTab: TimelineTab = TimelineTab.MOMENTS,
    val memories: List<MomentResponse> = emptyList(),
    val memoriesLoading: Boolean = false,
    val memoriesError: UiText? = null,
    /** 回忆是否已成功加载过（首次切到回忆分栏时懒加载）。 */
    val memoriesLoaded: Boolean = false,
    /** 发动态中（图片上传 + 提交期间为 true，用于禁用发布按钮）。 */
    val posting: Boolean = false,
)

@HiltViewModel
class TimelineViewModel @Inject constructor(
    private val repository: TimelineRepository,
    private val uploadRepository: UploadRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(TimelineUiState())
    val state: StateFlow<TimelineUiState> = _state.asStateFlow()

    private val _message = MutableStateFlow<UiText?>(null)
    val message: StateFlow<UiText?> = _message.asStateFlow()

    /** 最近一次由 Pager 工厂创建的分页源；invalidate 即触发整列表刷新。 */
    private var currentSource: PagingSource<Int, MomentResponse>? = null

    /** 动态流：按页惰性加载（服务端 page/page_size），随 cachedIn 存活于 VM 生命周期。 */
    val moments: Flow<PagingData<MomentResponse>> = Pager(
        config = PagingConfig(
            pageSize = TimelineRepository.PAGE_SIZE,
            initialLoadSize = TimelineRepository.PAGE_SIZE,
            prefetchDistance = 3,
            enablePlaceholders = false,
        ),
        pagingSourceFactory = {
            repository.pagingSource().also { currentSource = it }
        },
    ).flow.cachedIn(viewModelScope)

    /** 刷新当前分栏的数据。 */
    fun refresh() {
        when (_state.value.selectedTab) {
            TimelineTab.MOMENTS -> refreshMoments()
            TimelineTab.MEMORIES -> loadMemories(force = true)
        }
    }

    /** 切换「动态 / 回忆」分栏；回忆首次进入时懒加载，动态流常驻无需处理。 */
    fun selectTab(tab: TimelineTab) {
        if (_state.value.selectedTab == tab) return
        _state.value = _state.value.copy(selectedTab = tab)
        if (tab == TimelineTab.MEMORIES) {
            loadMemories(force = false)
        }
    }

    private fun refreshMoments() {
        currentSource?.invalidate()
    }

    private fun loadMemories(force: Boolean) {
        if (!force && (_state.value.memoriesLoaded || _state.value.memoriesLoading)) return
        _state.value = _state.value.copy(memoriesLoading = true, memoriesError = null)
        viewModelScope.launch {
            repository.memories().fold(
                onSuccess = {
                    _state.value = _state.value.copy(
                        memoriesLoading = false,
                        memories = it,
                        memoriesError = null,
                        memoriesLoaded = true,
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(
                        memoriesLoading = false,
                        memoriesError = it.toUiText(),
                    )
                },
            )
        }
    }

    /**
     * 发布动态：先把本地选中的图片逐张经上传链路换取 URL，再随
     * [com.lovejournal.app.data.remote.dto.MomentCreateRequest.media_urls] 提交。
     * 任一图片上传失败则中止并提示，不再提交动态。
     */
    fun post(content: String, visibility: String, mediaUris: List<Uri> = emptyList(), onDone: () -> Unit = {}) {
        if (content.isBlank() && mediaUris.isEmpty()) {
            _message.value = uiText(R.string.timeline_msg_say_something)
            return
        }
        if (_state.value.posting) return
        _state.value = _state.value.copy(posting = true)
        viewModelScope.launch {
            val mediaUrls = mutableListOf<String>()
            for (uri in mediaUris) {
                uploadRepository.uploadTimelineImage(uri).fold(
                    onSuccess = { mediaUrls += it.url },
                    onFailure = {
                        _state.value = _state.value.copy(posting = false)
                        _message.value = uiText(R.string.timeline_msg_photo_upload_failed, it.message ?: "unknown")
                        return@launch
                    },
                )
            }
            repository.post(content.trim(), visibility, mediaUrls).fold(
                onSuccess = {
                    _state.value = _state.value.copy(posting = false)
                    _message.value = uiText(R.string.msg_published)
                    onDone()
                    refreshMoments()
                },
                onFailure = {
                    _state.value = _state.value.copy(posting = false)
                    _message.value = uiText(R.string.msg_publish_failed)
                },
            )
        }
    }

    /** 发表评论；[parentCid] 非空表示回复某条评论。成功后刷新动态流以拉取最新评论树。 */
    fun comment(mid: String, content: String, parentCid: String? = null) {
        if (content.isBlank()) {
            _message.value = uiText(R.string.timeline_msg_say_something)
            return
        }
        viewModelScope.launch {
            repository.comment(mid, content.trim(), parentCid).fold(
                onSuccess = {
                    _message.value = uiText(R.string.timeline_msg_commented)
                    refreshMoments()
                },
                onFailure = { _message.value = uiText(R.string.timeline_comment_failed) },
            )
        }
    }

    fun delete(moment: MomentResponse) {
        viewModelScope.launch {
            repository.delete(moment.mid).fold(
                onSuccess = {
                    _message.value = uiText(R.string.msg_deleted)
                    refreshMoments()
                },
                onFailure = { _message.value = uiText(R.string.msg_delete_failed) },
            )
        }
    }

    fun clearMessage() {
        _message.value = null
    }
}
