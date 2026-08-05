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

package com.lovejournal.app.ui.cottage.watch

import android.app.Application
import android.content.ContentResolver
import android.database.Cursor
import android.net.Uri
import android.provider.OpenableColumns
import androidx.annotation.OptIn
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackParameters
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.dto.WatchBookmark
import com.lovejournal.app.data.remote.dto.WatchCurrent
import com.lovejournal.app.data.remote.dto.WatchSourceResponse
import com.lovejournal.app.data.repository.WatchRepository
import com.lovejournal.app.data.repository.WatchWsEvent
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.FileNotFoundException
import okhttp3.OkHttpClient
import javax.inject.Named
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okio.BufferedSink
import okio.source
import javax.inject.Inject

data class WatchUiState(
    val connected: Boolean = false,
    val partnerOnline: Boolean = false,
    val sources: List<WatchSourceResponse> = emptyList(),
    val currentTitle: String? = null,
    val isPlaying: Boolean = false,
    val selfUid: String? = null,
    val uploading: Boolean = false,
    val deletingWsid: String? = null,
    // The currently-loaded source's wsid (null = nothing on stage).
    val currentWsid: String? = null,
    // Bookmarks attached to the current source, sorted by position.
    val currentBookmarks: List<WatchBookmark> = emptyList(),
)

@OptIn(UnstableApi::class)
@HiltViewModel
class WatchViewModel @Inject constructor(
    application: Application,
    private val repository: WatchRepository,
    private val serverConfig: ServerConfig,
    private val session: SessionManager,
    @Named("ws") mediaClient: OkHttpClient,
) : AndroidViewModel(application) {

    // OkHttp data source so the player sends the auth cookie when streaming
    // partner-only /uploads videos (the media route is cookie-gated).
    val player: ExoPlayer = ExoPlayer.Builder(application)
        .setMediaSourceFactory(DefaultMediaSourceFactory(OkHttpDataSource.Factory(mediaClient)))
        .build()

    private val _state = MutableStateFlow(WatchUiState())
    val state: StateFlow<WatchUiState> = _state.asStateFlow()

    private val _toast = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val toast: SharedFlow<String> = _toast.asSharedFlow()

    private val resolver = application.contentResolver
    private var lastUrl: String? = null
    private var selfUid: String? = null

    init {
        player.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                _state.update { it.copy(isPlaying = isPlaying) }
            }
        })
        viewModelScope.launch {
            selfUid = session.sessionFlow.first().uid
            _state.update { it.copy(selfUid = selfUid) }
        }
        observeEvents()
        repository.connect()
        refreshState()
        loadSources()
        startProgressFlush()
    }

    // ---- Resume / bookmark state ----
    //
    // Source-level state is mirrored from the sources list (the server is
    // authoritative). The current-source mirror lives on WatchUiState so
    // the bookmarks panel can render synchronously with the player.
    private var progressJob: kotlinx.coroutines.Job? = null
    private var lastProgressSentAt = 0L

    private fun startProgressFlush() {
        if (progressJob?.isActive == true) return
        progressJob = viewModelScope.launch {
            while (isActive) {
                delay(5000)
                val wsid = _state.value.currentWsid ?: continue
                if (wsid.isBlank()) continue
                val pos = player.currentPosition
                if (pos <= 0) continue
                // Throttle on top of the 5s loop so a tight replay of pause /
                // play can't trigger a duplicate PATCH.
                val now = System.currentTimeMillis()
                if (now - lastProgressSentAt < 4000) continue
                lastProgressSentAt = now
                repository.patchSource(wsid, lastPositionMs = pos)
            }
        }
    }

    private fun flushProgressNow(force: Boolean = false) {
        val wsid = _state.value.currentWsid ?: return
        if (wsid.isBlank()) return
        val pos = player.currentPosition
        if (pos < 0) return
        if (!force) {
            val now = System.currentTimeMillis()
            if (now - lastProgressSentAt < 4000) return
            lastProgressSentAt = now
        } else {
            lastProgressSentAt = System.currentTimeMillis()
        }
        viewModelScope.launch { repository.patchSource(wsid, lastPositionMs = pos) }
    }

    private fun observeEvents() {
        viewModelScope.launch {
            repository.events.collect { ev ->
                when (ev) {
                    is WatchWsEvent.Connection -> _state.update { it.copy(connected = ev.connected) }
                    is WatchWsEvent.Presence ->
                        if (ev.uid != selfUid) _state.update { it.copy(partnerOnline = ev.online) }
                    is WatchWsEvent.Sync ->
                        // Ignore our own echoed events (already applied locally).
                        if (ev.originUid != selfUid) refreshState()
                }
            }
        }
    }

    private fun refreshState() {
        viewModelScope.launch {
            repository.state().onSuccess { st ->
                applyCurrent(st.current)
                val partnerOnline = st.partners.any { it.online && it.user_uid != selfUid }
                _state.update { it.copy(partnerOnline = partnerOnline) }
            }
        }
    }

    private fun loadSources() {
        viewModelScope.launch {
            repository.sources().onSuccess { res ->
                val sources = res.items
                val currentWsid = _state.value.currentWsid
                val currentBookmarks = sources.firstOrNull { it.wsid == currentWsid }?.bookmarks
                    ?: _state.value.currentBookmarks
                _state.update {
                    it.copy(
                        sources = sources,
                        currentBookmarks = currentBookmarks,
                    )
                }
            }
        }
    }

    /** Apply the authoritative room state to the local player (no rebroadcast). */
    private fun applyCurrent(c: WatchCurrent) {
        val url = serverConfig.mediaUrl(c.source_url)
        if (url == null) {
            if (lastUrl != null) {
                player.clearMediaItems()
                lastUrl = null
            }
        } else if (url != lastUrl) {
            player.setMediaItem(MediaItem.fromUri(url))
            player.prepare()
            lastUrl = url
        }
        if (url != null) {
            player.seekTo(c.position_ms)
            player.playbackParameters = PlaybackParameters(c.rate)
            player.playWhenReady = !c.paused
        }
        val bookmarks = _state.value.sources.firstOrNull { it.wsid == c.source_wsid }?.bookmarks
            ?: _state.value.currentBookmarks
        _state.update {
            it.copy(
                currentTitle = c.source_title,
                currentWsid = c.source_wsid,
                currentBookmarks = bookmarks.sortedBy { b -> b.position_ms },
            )
        }
    }

    // ---- local controls: drive the player AND broadcast to the partner ----

    fun togglePlay() {
        val pos = player.currentPosition
        if (player.isPlaying) {
            player.pause()
            repository.pause(pos)
            // Flush synchronously on pause so a tab close / app background
            // a moment later still preserves the position.
            flushProgressNow(force = true)
        } else {
            player.play()
            repository.play(pos)
        }
    }

    fun seekBy(deltaMs: Long) {
        val target = (player.currentPosition + deltaMs).coerceAtLeast(0)
        player.seekTo(target)
        repository.seek(target)
    }

    fun loadSource(src: WatchSourceResponse) {
        val url = serverConfig.mediaUrl(src.url) ?: return
        // Seed the player with the server-side resume position (>= 0) so the
        // user picks up where the couple left off.
        val startMs = if (src.last_position_ms > 0) src.last_position_ms else 0L
        player.setMediaItem(MediaItem.fromUri(url), startMs)
        player.prepare()
        player.playWhenReady = false
        lastUrl = url
        repository.load(src.wsid, src.url, src.title, src.kind)
        _state.update {
            it.copy(
                currentTitle = src.title,
                currentWsid = src.wsid,
                currentBookmarks = src.bookmarks.sortedBy { b -> b.position_ms },
            )
        }
        // Seed the room head with the resume point so the partner can
        // rejoin us at the same place.
        if (startMs > 0) repository.seek(startMs)
    }

    /** Jump to the bookmark's stored position (broadcast via SEEK). */
    fun jumpToBookmark(bookmark: WatchBookmark) {
        val pos = bookmark.position_ms
        player.seekTo(pos)
        repository.seek(pos)
        flushProgressNow(force = true)
    }

    /** Add a bookmark at the player's current position. */
    fun addBookmark(label: String? = null) {
        val wsid = _state.value.currentWsid ?: return
        if (wsid.isBlank()) return
        val pos = player.currentPosition
        if (pos <= 0) {
            _toast.tryEmit("播放几秒后再添加书签")
            return
        }
        val now = System.currentTimeMillis()
        val next = _state.value.currentBookmarks.toMutableList()
        if (next.size >= 200) {
            _toast.tryEmit("书签已达上限（200）")
            return
        }
        val bm = WatchBookmark(
            bid = now.toString(36) + "-" + java.util.UUID.randomUUID().toString().take(8),
            position_ms = pos,
            label = label?.takeIf { it.isNotBlank() } ?: "片段 ${formatTime(pos)}",
            created_at = java.time.Instant.ofEpochMilli(now).toString(),
            // created_by_uid is stamped by the server from the authenticated
            // session — we leave it empty here so the server is the source
            // of truth and the client cannot forge authorship.
        )
        next.add(bm)
        val sorted = next.sortedBy { it.position_ms }
        // Optimistic local update so the UI feels instant.
        _state.update { it.copy(currentBookmarks = sorted) }
        viewModelScope.launch {
            repository.patchSource(wsid, bookmarks = sorted)
                .onSuccess { res ->
                    _state.update { it.copy(currentBookmarks = res.bookmarks.sortedBy { b -> b.position_ms }) }
                    _toast.tryEmit("已添加书签")
                }
                .onFailure { err ->
                    // Roll back to the pre-add list to keep the UI in sync.
                    _state.update { it.copy(currentBookmarks = it.currentBookmarks.filterNot { b -> b.bid == bm.bid }) }
                    _toast.tryEmit(err.message ?: "添加书签失败")
                }
        }
    }

    fun deleteBookmark(bookmark: WatchBookmark) {
        val wsid = _state.value.currentWsid ?: return
        if (wsid.isBlank()) return
        val previous = _state.value.currentBookmarks
        val next = previous.filterNot { it.bid == bookmark.bid }
        if (next.size == previous.size) return
        _state.update { it.copy(currentBookmarks = next) }
        viewModelScope.launch {
            repository.patchSource(wsid, bookmarks = next)
                .onSuccess { res ->
                    _state.update { it.copy(currentBookmarks = res.bookmarks.sortedBy { b -> b.position_ms }) }
                }
                .onFailure { err ->
                    _state.update { it.copy(currentBookmarks = previous) }
                    _toast.tryEmit(err.message ?: "删除书签失败")
                }
        }
    }

    /** Format milliseconds as `m:ss` / `h:mm:ss` for bookmark labels. */
    fun formatTime(ms: Long): String {
        val total = (ms / 1000).coerceAtLeast(0)
        val h = total / 3600
        val m = (total % 3600) / 60
        val s = total % 60
        return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
    }

    fun invite() {
        viewModelScope.launch {
            repository.invite().onSuccess { _toast.tryEmit("已邀请对方一起看") }
        }
    }

    fun addSource(title: String, url: String) {
        if (title.isBlank() || url.isBlank()) {
            _toast.tryEmit("请填写标题和直链")
            return
        }
        viewModelScope.launch {
            repository.addSource(title.trim(), url.trim(), null)
                .onSuccess { _toast.tryEmit("已添加片源"); loadSources() }
                .onFailure { _toast.tryEmit(it.message ?: "添加失败") }
        }
    }

    fun uploadVideo(uri: Uri) {
        viewModelScope.launch {
            _state.update { it.copy(uploading = true) }
            val name = displayName(uri)
            val part = MultipartBody.Part.createFormData("file", name, UriRequestBody(resolver, uri))
            repository.uploadSource(part)
                .onSuccess {
                    _toast.tryEmit("视频已上传")
                    loadSources()
                }
                .onFailure { _toast.tryEmit(it.message ?: "上传失败") }
            _state.update { it.copy(uploading = false) }
        }
    }

    fun deleteSource(src: WatchSourceResponse) {
        viewModelScope.launch {
            _state.update { it.copy(deletingWsid = src.wsid) }
            repository.deleteSource(src.wsid)
                .onSuccess {
                    _toast.tryEmit("已删除片源")
                    _state.update { state ->
                        state.copy(sources = state.sources.filterNot { it.wsid == src.wsid })
                    }
                    refreshState()
                }
                .onFailure { _toast.tryEmit(it.message ?: "删除失败") }
            _state.update { it.copy(deletingWsid = null) }
        }
    }

    private fun displayName(uri: Uri): String {
        val cursor: Cursor? = resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
        cursor?.use {
            if (it.moveToFirst()) {
                val index = it.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0) return it.getString(index)
            }
        }
        return "watch-video.mp4"
    }

    override fun onCleared() {
        repository.disconnect()
        player.release()
        super.onCleared()
    }
}

private class UriRequestBody(
    private val resolver: ContentResolver,
    private val uri: Uri,
) : RequestBody() {
    override fun contentType(): MediaType? =
        resolver.getType(uri)?.toMediaTypeOrNull() ?: "application/octet-stream".toMediaTypeOrNull()

    override fun writeTo(sink: BufferedSink) {
        val input = resolver.openInputStream(uri) ?: throw FileNotFoundException(uri.toString())
        input.use { stream -> sink.writeAll(stream.source()) }
    }
}
