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

package com.lovejournal.app.ui.cottage.listen

import android.app.Application
import android.content.ContentResolver
import android.database.Cursor
import android.net.Uri
import android.provider.OpenableColumns
import androidx.annotation.OptIn
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import com.lovejournal.app.data.remote.ServerConfig
import com.lovejournal.app.data.remote.dto.ListenHistoryItem
import com.lovejournal.app.data.remote.dto.LyricLine
import com.lovejournal.app.data.remote.dto.PartnerLoginState
import com.lovejournal.app.data.remote.dto.PlaylistItem
import com.lovejournal.app.data.remote.dto.RoomCurrent
import com.lovejournal.app.data.remote.dto.RoomStateResponse
import com.lovejournal.app.data.remote.dto.SongMeta
import com.lovejournal.app.data.remote.dto.ToplistItem
import com.lovejournal.app.data.repository.ListenRepository
import com.lovejournal.app.data.repository.ListenWsEvent
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.FileNotFoundException
import javax.inject.Inject
import javax.inject.Named
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okio.BufferedSink
import okio.source

enum class ListenLibraryTab(val title: String) {
    Search("搜索"),
    Discover("推荐"),
    Playlists("歌单"),
    Charts("榜单"),
    History("历史"),
    Local("本地"),
    Queue("队列"),
}

data class ListenUiState(
    val loading: Boolean = false,
    val roomState: RoomStateResponse? = null,
    val connected: Boolean = false,
    val positionMs: Long = 0L,
    val durationMs: Long = 0L,
    val isPlaying: Boolean = false,
    val resolvingUrl: Boolean = false,
    val lyricLines: List<LyricLine> = emptyList(),
    val lyricKind: String = "none",
    val lyricLoading: Boolean = false,
    val searchKeyword: String = "",
    val searchResults: List<SongMeta> = emptyList(),
    val searchLoading: Boolean = false,
    val playlists: List<PlaylistItem> = emptyList(),
    val playlistTracks: List<SongMeta> = emptyList(),
    val selectedPlaylist: PlaylistItem? = null,
    val playlistsLoading: Boolean = false,
    val recommendSongs: List<SongMeta> = emptyList(),
    val discoverPlaylists: List<PlaylistItem> = emptyList(),
    val discoverPlaylistTracks: List<SongMeta> = emptyList(),
    val selectedDiscoverPlaylist: PlaylistItem? = null,
    val discoverLoading: Boolean = false,
    val toplists: List<ToplistItem> = emptyList(),
    val toplistTracks: List<SongMeta> = emptyList(),
    val selectedToplist: ToplistItem? = null,
    val chartsLoading: Boolean = false,
    val history: List<ListenHistoryItem> = emptyList(),
    val historyLoading: Boolean = false,
    val localTracks: List<SongMeta> = emptyList(),
    val localLoading: Boolean = false,
    val localUploading: Boolean = false,
    val message: String? = null,
    val error: String? = null,
) {
    val current: RoomCurrent?
        get() = roomState?.current

    val queue: List<SongMeta>
        get() = roomState?.queue.orEmpty()

    val partners: List<PartnerLoginState>
        get() = roomState?.partners.orEmpty()
}

@OptIn(UnstableApi::class)
@HiltViewModel
class ListenViewModel @Inject constructor(
    application: Application,
    private val repo: ListenRepository,
    private val serverConfig: ServerConfig,
    @Named("ws") mediaClient: OkHttpClient,
) : AndroidViewModel(application) {

    val player: ExoPlayer = ExoPlayer.Builder(application)
        .setMediaSourceFactory(DefaultMediaSourceFactory(OkHttpDataSource.Factory(mediaClient)))
        .build()

    private val resolver: ContentResolver = application.contentResolver
    private val _state = MutableStateFlow(ListenUiState())
    val state: StateFlow<ListenUiState> = _state.asStateFlow()

    private var started = false
    private var pollJob: Job? = null
    private var tickJob: Job? = null
    private var heartbeatJob: Job? = null
    private var lyricJob: Job? = null
    private var lastLyricSongId: String? = null
    private var lastResolvedSongId: String? = null
    private var lastMediaUrl: String? = null

    init {
        player.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                _state.update { it.copy(isPlaying = isPlaying) }
            }

            override fun onPlaybackStateChanged(playbackState: Int) {
                updatePlaybackSnapshot()
                if (playbackState == Player.STATE_ENDED) {
                    repo.next(expectedSongId = _state.value.current?.songId)
                    viewModelScope.launch {
                        delay(250)
                        loadState(silent = true)
                    }
                }
            }

            override fun onPlayerError(error: PlaybackException) {
                _state.update { it.copy(message = error.message ?: "播放失败") }
            }
        })
    }

    fun start() {
        if (started) return
        started = true
        observeSocket()
        repo.connect()
        loadState()
        loadHistory()
        loadLocalTracks()
        loadPlaylists()
        loadDiscover()
        startPolling()
        startTicking()
        startHeartbeat()
    }

    private fun observeSocket() {
        viewModelScope.launch {
            repo.events.collect { event ->
                when (event) {
                    is ListenWsEvent.Connection -> _state.update { it.copy(connected = event.connected) }
                    is ListenWsEvent.RoomChanged -> {
                        loadState(silent = true)
                        if (event.type == "PLAY" || event.type == "NEXT") loadHistory()
                    }
                    ListenWsEvent.LoginChanged -> {
                        lastResolvedSongId = null
                        loadState(silent = true)
                        loadPlaylists()
                        loadDiscover()
                    }
                }
            }
        }
    }

    private fun startPolling() {
        pollJob?.cancel()
        pollJob = viewModelScope.launch {
            while (true) {
                delay(5000)
                loadState(silent = true)
            }
        }
    }

    private fun startTicking() {
        tickJob?.cancel()
        tickJob = viewModelScope.launch {
            while (true) {
                delay(500)
                updatePlaybackSnapshot()
            }
        }
    }

    private fun startHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = viewModelScope.launch {
            while (true) {
                delay(20_000)
                repo.heartbeat()
            }
        }
    }

    fun loadState(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) _state.update { it.copy(loading = true, error = null) }
            repo.state()
                .onSuccess { room ->
                    val remoteDuration = room.current.songMeta?.durationMs ?: 0L
                    _state.update {
                        it.copy(
                            loading = false,
                            roomState = room,
                            positionMs = room.current.positionMs,
                            durationMs = remoteDuration,
                            error = null,
                        )
                    }
                    syncPlayer(room.current)
                    maybeLoadLyric(room.current.songId)
                }
                .onFailure { err ->
                    _state.update {
                        it.copy(
                            loading = false,
                            error = if (it.roomState == null) friendlyError(err) else it.error,
                            message = if (it.roomState == null) it.message else friendlyError(err),
                        )
                    }
                }
        }
    }

    fun loadHistory() {
        viewModelScope.launch {
            _state.update { it.copy(historyLoading = true) }
            repo.history()
                .onSuccess { resp ->
                    _state.update { it.copy(history = resp.items, historyLoading = false) }
                }
                .onFailure { err ->
                    _state.update { it.copy(historyLoading = false, message = friendlyError(err)) }
                }
        }
    }

    fun loadLocalTracks() {
        viewModelScope.launch {
            _state.update { it.copy(localLoading = true) }
            repo.localTracks()
                .onSuccess { resp ->
                    _state.update { it.copy(localTracks = resp.items, localLoading = false) }
                }
                .onFailure { err ->
                    _state.update { it.copy(localLoading = false, message = friendlyError(err)) }
                }
        }
    }

    fun uploadLocalTrack(uri: Uri) {
        viewModelScope.launch {
            _state.update { it.copy(localUploading = true, message = null) }
            val fileName = displayName(uri)
            val body = UriRequestBody(resolver, uri)
            val part = MultipartBody.Part.createFormData("file", fileName, body)
            repo.uploadLocalTrack(file = part, name = fileName.nameWithoutExtensionBody())
                .onSuccess { song ->
                    _state.update {
                        it.copy(
                            localUploading = false,
                            localTracks = listOf(song) + it.localTracks,
                            message = "本地歌曲已上传",
                        )
                    }
                }
                .onFailure { err ->
                    _state.update { it.copy(localUploading = false, message = friendlyError(err)) }
                }
        }
    }

    fun deleteLocalTrack(song: SongMeta) {
        viewModelScope.launch {
            repo.deleteLocalTrack(song.songId)
                .onSuccess {
                    _state.update {
                        it.copy(
                            localTracks = it.localTracks.filterNot { item -> item.songId == song.songId },
                            message = "已删除本地歌曲",
                        )
                    }
                }
                .onFailure { err -> _state.update { it.copy(message = friendlyError(err)) } }
        }
    }

    fun updateSearchKeyword(keyword: String) {
        _state.update { it.copy(searchKeyword = keyword) }
    }

    fun search(keyword: String = _state.value.searchKeyword) {
        val clean = keyword.trim()
        if (clean.isEmpty()) {
            _state.update { it.copy(searchKeyword = "", searchResults = emptyList()) }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(searchKeyword = clean, searchLoading = true, message = null) }
            repo.search(clean)
                .onSuccess { resp ->
                    _state.update { it.copy(searchResults = resp.items, searchLoading = false) }
                }
                .onFailure { err ->
                    _state.update { it.copy(searchLoading = false, message = friendlyError(err)) }
                }
        }
    }

    fun loadPlaylists() {
        viewModelScope.launch {
            _state.update { it.copy(playlistsLoading = true) }
            repo.playlists()
                .onSuccess { resp ->
                    _state.update { it.copy(playlists = resp.items, playlistsLoading = false) }
                }
                .onFailure { err ->
                    _state.update { it.copy(playlistsLoading = false, message = friendlyError(err)) }
                }
        }
    }

    fun loadPlaylistTracks(playlist: PlaylistItem) {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    selectedPlaylist = playlist,
                    playlistsLoading = true,
                    playlistTracks = emptyList(),
                )
            }
            repo.playlistTracks(playlist.playlistId)
                .onSuccess { resp ->
                    _state.update { it.copy(playlistTracks = resp.items, playlistsLoading = false) }
                }
                .onFailure { err ->
                    _state.update { it.copy(playlistsLoading = false, message = friendlyError(err)) }
                }
        }
    }

    fun loadDiscover() {
        viewModelScope.launch {
            _state.update { it.copy(discoverLoading = true, chartsLoading = true) }
            repo.recommendSongs()
                .onSuccess { resp -> _state.update { it.copy(recommendSongs = resp.items) } }
                .onFailure { err -> _state.update { it.copy(message = friendlyError(err)) } }
            repo.discoverPlaylists()
                .onSuccess { resp -> _state.update { it.copy(discoverPlaylists = resp.items) } }
                .onFailure { err -> _state.update { it.copy(message = friendlyError(err)) } }
            _state.update { it.copy(discoverLoading = false) }
            repo.toplist()
                .onSuccess { resp -> _state.update { it.copy(toplists = resp.items) } }
                .onFailure { err -> _state.update { it.copy(message = friendlyError(err)) } }
            _state.update { it.copy(chartsLoading = false) }
        }
    }

    fun loadDiscoverPlaylistTracks(playlist: PlaylistItem) {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    selectedDiscoverPlaylist = playlist,
                    discoverPlaylistTracks = emptyList(),
                    discoverLoading = true,
                )
            }
            repo.discoverPlaylistTracks(playlist.playlistId)
                .onSuccess { resp ->
                    _state.update { it.copy(discoverPlaylistTracks = resp.items, discoverLoading = false) }
                }
                .onFailure { err ->
                    _state.update { it.copy(discoverLoading = false, message = friendlyError(err)) }
                }
        }
    }

    fun loadToplistTracks(toplist: ToplistItem) {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    selectedToplist = toplist,
                    toplistTracks = emptyList(),
                    chartsLoading = true,
                )
            }
            repo.toplistTracks(toplist.toplistId)
                .onSuccess { resp ->
                    _state.update { it.copy(toplistTracks = resp.items, chartsLoading = false) }
                }
                .onFailure { err ->
                    _state.update { it.copy(chartsLoading = false, message = friendlyError(err)) }
                }
        }
    }

    fun playPause() {
        val current = _state.value.current ?: return
        val song = current.songMeta ?: SongMeta(songId = current.songId.orEmpty(), name = "未知歌曲")
        val pos = if (player.mediaItemCount > 0) player.currentPosition else _state.value.positionMs
        if (current.paused) {
            player.playWhenReady = true
            setPausedOptimistic(false)
            repo.play(song, pos)
        } else {
            player.pause()
            setPausedOptimistic(true)
            repo.pause(pos)
        }
    }

    fun playNow(song: SongMeta) {
        if (song.songId.isBlank()) return
        viewModelScope.launch {
            lastResolvedSongId = null
            val nextRoom = (_state.value.roomState ?: RoomStateResponse()).copy(
                current = RoomCurrent(
                    songId = song.songId,
                    songMeta = song,
                    paused = false,
                    positionMs = 0L,
                )
            )
            _state.update {
                it.copy(
                    roomState = nextRoom,
                    positionMs = 0L,
                    durationMs = song.durationMs ?: 0L,
                    message = null,
                )
            }
            maybeLoadLyric(song.songId)
            syncPlayer(nextRoom.current)
            repo.play(song, 0L)
        }
    }

    fun appendQueue(song: SongMeta) {
        if (song.songId.isBlank()) return
        repo.queueAppend(song)
        _state.update { it.copy(message = "已加入队列") }
    }

    fun removeQueue(index: Int) {
        repo.queueRemove(index)
        _state.update {
            val room = it.roomState
            if (room == null) it else it.copy(roomState = room.copy(queue = room.queue.filterIndexed { i, _ -> i != index }))
        }
    }

    fun clearQueue() {
        repo.queueClear()
        _state.update {
            val room = it.roomState
            if (room == null) it else it.copy(roomState = room.copy(queue = emptyList()))
        }
    }

    fun next() {
        repo.next()
        viewModelScope.launch {
            delay(250)
            loadState(silent = true)
        }
    }

    fun prev() {
        repo.prev()
        player.seekTo(0L)
        viewModelScope.launch {
            delay(250)
            loadState(silent = true)
        }
    }

    fun seek(ms: Long) {
        val clamped = ms.coerceAtLeast(0L)
        player.seekTo(clamped)
        _state.update { it.copy(positionMs = clamped) }
        repo.seek(clamped)
    }

    fun clearMessage() {
        _state.update { it.copy(message = null) }
    }

    private suspend fun syncPlayer(current: RoomCurrent) {
        val songId = current.songId
        if (songId.isNullOrBlank()) {
            player.clearMediaItems()
            lastResolvedSongId = null
            lastMediaUrl = null
            _state.update { it.copy(positionMs = 0L, durationMs = 0L, resolvingUrl = false) }
            return
        }

        val needsResolve = songId != lastResolvedSongId
        if (needsResolve) {
            _state.update { it.copy(resolvingUrl = true) }
            repo.songUrl(songId)
                .onSuccess { response ->
                    val mediaUrl = serverConfig.mediaUrl(response.url)
                    lastResolvedSongId = songId
                    lastMediaUrl = mediaUrl
                    if (mediaUrl.isNullOrBlank()) {
                        player.clearMediaItems()
                        _state.update {
                            it.copy(
                                resolvingUrl = false,
                                message = if (response.errorKind != null) "这首歌暂时不能播放" else "未获取到播放地址",
                            )
                        }
                    } else {
                        player.setMediaItem(MediaItem.fromUri(mediaUrl))
                        player.prepare()
                        _state.update { it.copy(resolvingUrl = false) }
                    }
                }
                .onFailure { err ->
                    lastResolvedSongId = songId
                    lastMediaUrl = null
                    player.clearMediaItems()
                    _state.update { it.copy(resolvingUrl = false, message = friendlyError(err)) }
                }
        }

        if (lastMediaUrl != null) {
            val drift = kotlin.math.abs(player.currentPosition - current.positionMs)
            if (needsResolve || drift > 1500L || current.paused) {
                player.seekTo(current.positionMs)
            }
            player.playWhenReady = !current.paused
        }
        updatePlaybackSnapshot(current)
    }

    private fun updatePlaybackSnapshot(current: RoomCurrent? = _state.value.current) {
        val playerDuration = player.duration
            .takeIf { it != C.TIME_UNSET && it > 0L }
            ?: 0L
        val remoteDuration = current?.songMeta?.durationMs ?: 0L
        val duration = maxOf(playerDuration, remoteDuration)
        val position = if (player.mediaItemCount > 0) player.currentPosition.coerceAtLeast(0L) else current?.positionMs ?: 0L
        _state.update {
            it.copy(
                positionMs = position,
                durationMs = duration,
                isPlaying = player.isPlaying,
            )
        }
    }

    private fun maybeLoadLyric(songId: String?) {
        lyricJob?.cancel()
        if (songId.isNullOrBlank()) {
            lastLyricSongId = null
            _state.update { it.copy(lyricLines = emptyList(), lyricKind = "none", lyricLoading = false) }
            return
        }
        if (songId == lastLyricSongId) return
        lastLyricSongId = songId
        lyricJob = viewModelScope.launch {
            _state.update { it.copy(lyricLoading = true) }
            repo.lyric(songId)
                .onSuccess { resp ->
                    _state.update {
                        it.copy(
                            lyricLines = resp.lines,
                            lyricKind = resp.kind,
                            lyricLoading = false,
                        )
                    }
                }
                .onFailure {
                    _state.update {
                        it.copy(
                            lyricLines = emptyList(),
                            lyricKind = "none",
                            lyricLoading = false,
                        )
                    }
                }
        }
    }

    private fun setPausedOptimistic(paused: Boolean) {
        _state.update { currentState ->
            val room = currentState.roomState ?: return@update currentState
            currentState.copy(roomState = room.copy(current = room.current.copy(paused = paused)))
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
        return "本地歌曲"
    }

    private fun String.nameWithoutExtensionBody(): RequestBody {
        val clean = substringBeforeLast('.', this).ifBlank { this }
        return clean.toRequestBody("text/plain".toMediaTypeOrNull())
    }

    private fun friendlyError(error: Throwable): String {
        val raw = error.message.orEmpty()
        return when {
            raw.contains("409", ignoreCase = true) -> "请先登录网易云，或播放本地上传歌曲"
            raw.contains("403", ignoreCase = true) -> "当前账号没有权限访问这个内容"
            raw.contains("404", ignoreCase = true) -> "内容不存在或已被删除"
            raw.isBlank() -> "操作失败，请稍后再试"
            else -> raw
        }
    }

    override fun onCleared() {
        pollJob?.cancel()
        tickJob?.cancel()
        heartbeatJob?.cancel()
        lyricJob?.cancel()
        repo.disconnect()
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
