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

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.FileUpload
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.PlaylistAdd
import androidx.compose.material.icons.filled.QueueMusic
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Slider
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.lovejournal.app.data.remote.dto.ListenHistoryItem
import com.lovejournal.app.data.remote.dto.LyricLine
import com.lovejournal.app.data.remote.dto.PlaylistItem
import com.lovejournal.app.data.remote.dto.RoomCurrent
import com.lovejournal.app.data.remote.dto.SongMeta
import com.lovejournal.app.data.remote.dto.ToplistItem
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.theme.LoveMint

private fun formatMs(ms: Long): String {
    if (ms <= 0) return "0:00"
    val totalSec = ms / 1000
    val m = totalSec / 60
    val s = totalSec % 60
    return "%d:%02d".format(m, s)
}

@Composable
fun ListenScreen(viewModel: ListenViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(Unit) { viewModel.start() }
    LaunchedEffect(state.message) {
        val message = state.message
        if (!message.isNullOrBlank()) {
            snackbar.showSnackbar(message)
            viewModel.clearMessage()
        }
    }

    ListenScreenContent(
        state = state,
        snackbar = snackbar,
        onPlayPause = viewModel::playPause,
        onPrev = viewModel::prev,
        onNext = viewModel::next,
        onSeek = viewModel::seek,
        onSearchKeyword = viewModel::updateSearchKeyword,
        onSearch = viewModel::search,
        onPlaySong = viewModel::playNow,
        onQueueSong = viewModel::appendQueue,
        onLoadPlaylists = viewModel::loadPlaylists,
        onLoadPlaylistTracks = viewModel::loadPlaylistTracks,
        onLoadDiscover = viewModel::loadDiscover,
        onLoadDiscoverTracks = viewModel::loadDiscoverPlaylistTracks,
        onLoadToplistTracks = viewModel::loadToplistTracks,
        onLoadHistory = viewModel::loadHistory,
        onLoadLocal = viewModel::loadLocalTracks,
        onUploadLocal = viewModel::uploadLocalTrack,
        onDeleteLocal = viewModel::deleteLocalTrack,
        onRemoveQueue = viewModel::removeQueue,
        onClearQueue = viewModel::clearQueue,
    )
}

@Composable
private fun ListenScreenContent(
    state: ListenUiState,
    snackbar: SnackbarHostState,
    onPlayPause: () -> Unit,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onSeek: (Long) -> Unit,
    onSearchKeyword: (String) -> Unit,
    onSearch: (String) -> Unit,
    onPlaySong: (SongMeta) -> Unit,
    onQueueSong: (SongMeta) -> Unit,
    onLoadPlaylists: () -> Unit,
    onLoadPlaylistTracks: (PlaylistItem) -> Unit,
    onLoadDiscover: () -> Unit,
    onLoadDiscoverTracks: (PlaylistItem) -> Unit,
    onLoadToplistTracks: (ToplistItem) -> Unit,
    onLoadHistory: () -> Unit,
    onLoadLocal: () -> Unit,
    onUploadLocal: (Uri) -> Unit,
    onDeleteLocal: (SongMeta) -> Unit,
    onRemoveQueue: (Int) -> Unit,
    onClearQueue: () -> Unit,
) {
    Scaffold(snackbarHost = { SnackbarHost(snackbar) }) { padding ->
        LovePage(modifier = Modifier.padding(padding)) {
        when {
            state.loading && state.roomState == null -> LoadingState()
            state.error != null && state.roomState == null -> ErrorState(message = state.error)
            else -> ListenBody(
                state = state,
                modifier = Modifier,
                onPlayPause = onPlayPause,
                onPrev = onPrev,
                onNext = onNext,
                onSeek = onSeek,
                onSearchKeyword = onSearchKeyword,
                onSearch = onSearch,
                onPlaySong = onPlaySong,
                onQueueSong = onQueueSong,
                onLoadPlaylists = onLoadPlaylists,
                onLoadPlaylistTracks = onLoadPlaylistTracks,
                onLoadDiscover = onLoadDiscover,
                onLoadDiscoverTracks = onLoadDiscoverTracks,
                onLoadToplistTracks = onLoadToplistTracks,
                onLoadHistory = onLoadHistory,
                onLoadLocal = onLoadLocal,
                onUploadLocal = onUploadLocal,
                onDeleteLocal = onDeleteLocal,
                onRemoveQueue = onRemoveQueue,
                onClearQueue = onClearQueue,
            )
        }
        }
    }
}

@Composable
private fun ListenBody(
    state: ListenUiState,
    modifier: Modifier = Modifier,
    onPlayPause: () -> Unit,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onSeek: (Long) -> Unit,
    onSearchKeyword: (String) -> Unit,
    onSearch: (String) -> Unit,
    onPlaySong: (SongMeta) -> Unit,
    onQueueSong: (SongMeta) -> Unit,
    onLoadPlaylists: () -> Unit,
    onLoadPlaylistTracks: (PlaylistItem) -> Unit,
    onLoadDiscover: () -> Unit,
    onLoadDiscoverTracks: (PlaylistItem) -> Unit,
    onLoadToplistTracks: (ToplistItem) -> Unit,
    onLoadHistory: () -> Unit,
    onLoadLocal: () -> Unit,
    onUploadLocal: (Uri) -> Unit,
    onDeleteLocal: (SongMeta) -> Unit,
    onRemoveQueue: (Int) -> Unit,
    onClearQueue: () -> Unit,
) {
    var selectedTab by remember { mutableStateOf(ListenLibraryTab.Search) }
    Column(
        modifier = modifier
            .fillMaxSize()
    ) {
        NowPlayingCard(
            state = state,
            onPlayPause = onPlayPause,
            onPrev = onPrev,
            onNext = onNext,
            onSeek = onSeek,
        )
        Spacer(Modifier.height(10.dp))
        LyricPanel(
            lines = state.lyricLines,
            kind = state.lyricKind,
            loading = state.lyricLoading,
            positionMs = state.positionMs,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 120.dp, max = 190.dp)
        )
        Spacer(Modifier.height(8.dp))
        LibraryTabs(selected = selectedTab, onSelected = { selectedTab = it })
        LibraryContent(
            tab = selectedTab,
            state = state,
            onSearchKeyword = onSearchKeyword,
            onSearch = onSearch,
            onPlaySong = onPlaySong,
            onQueueSong = onQueueSong,
            onLoadPlaylists = onLoadPlaylists,
            onLoadPlaylistTracks = onLoadPlaylistTracks,
            onLoadDiscover = onLoadDiscover,
            onLoadDiscoverTracks = onLoadDiscoverTracks,
            onLoadToplistTracks = onLoadToplistTracks,
            onLoadHistory = onLoadHistory,
            onLoadLocal = onLoadLocal,
            onUploadLocal = onUploadLocal,
            onDeleteLocal = onDeleteLocal,
            onRemoveQueue = onRemoveQueue,
            onClearQueue = onClearQueue,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun NowPlayingCard(
    state: ListenUiState,
    onPlayPause: () -> Unit,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onSeek: (Long) -> Unit,
) {
    val current = state.current
    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.elevatedCardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                ConnectionBadge(connected = state.connected, partners = state.partners.size)
                if (state.resolvingUrl) {
                    CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                }
            }
            Spacer(Modifier.height(12.dp))
            if (current?.songId.isNullOrBlank()) {
                EmptyNowPlaying()
            } else {
                CurrentSongInfo(current = current)
                Spacer(Modifier.height(12.dp))
                SeekBar(
                    positionMs = state.positionMs,
                    durationMs = state.durationMs,
                    songKey = current?.songId,
                    onSeek = onSeek,
                )
                Spacer(Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    FilledTonalIconButton(onClick = onPrev) {
                        Icon(Icons.Filled.SkipPrevious, contentDescription = "上一首")
                    }
                    Spacer(Modifier.width(20.dp))
                    FilledIconButton(onClick = onPlayPause, modifier = Modifier.size(56.dp)) {
                        Icon(
                            imageVector = if (current?.paused == false) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                            contentDescription = if (current?.paused == false) "暂停" else "播放",
                        )
                    }
                    Spacer(Modifier.width(20.dp))
                    FilledTonalIconButton(onClick = onNext) {
                        Icon(Icons.Filled.SkipNext, contentDescription = "下一首")
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptyNowPlaying() {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(64.dp)
                .clip(RoundedCornerShape(8.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Filled.MusicNote, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.width(12.dp))
        Column {
            Text("还没有正在播放", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text("从下方选择歌曲", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun CurrentSongInfo(current: RoomCurrent?) {
    val meta = current?.songMeta
    Row(verticalAlignment = Alignment.CenterVertically) {
        AsyncImage(
            model = meta?.coverUrl,
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .size(72.dp)
                .clip(RoundedCornerShape(8.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
        )
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                meta?.name?.takeIf { it.isNotBlank() } ?: "未知歌曲",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                meta?.artists?.joinToString(" / ").orEmpty(),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            meta?.album?.takeIf { it.isNotBlank() }?.let { album ->
                Text(
                    album,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun SeekBar(
    positionMs: Long,
    durationMs: Long,
    songKey: String?,
    onSeek: (Long) -> Unit,
) {
    var dragFraction by remember(songKey) { mutableStateOf<Float?>(null) }
    val fraction = dragFraction
        ?: if (durationMs > 0) (positionMs.toFloat() / durationMs).coerceIn(0f, 1f) else 0f
    Slider(
        value = fraction,
        onValueChange = { if (durationMs > 0) dragFraction = it },
        onValueChangeFinished = {
            val f = dragFraction
            if (f != null && durationMs > 0) onSeek((f * durationMs).toLong())
            dragFraction = null
        },
        enabled = durationMs > 0,
        modifier = Modifier.fillMaxWidth(),
    )
    val shownPos = dragFraction?.let { (it * durationMs).toLong() } ?: positionMs
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(formatMs(shownPos), style = MaterialTheme.typography.labelSmall)
        Text(formatMs(durationMs), style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun ConnectionBadge(connected: Boolean, partners: Int) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(if (connected) LoveMint else MaterialTheme.colorScheme.outline)
        )
        Spacer(Modifier.width(6.dp))
        Text(
            if (connected) "实时同步 · $partners 人" else "连接中",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun LyricPanel(
    lines: List<LyricLine>,
    kind: String,
    loading: Boolean,
    positionMs: Long,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
    ) {
        when {
            loading -> LyricHint {
                CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 2.dp)
                Spacer(Modifier.height(8.dp))
                Text("歌词加载中", style = MaterialTheme.typography.bodySmall)
            }
            kind == "instrumental" -> LyricHint {
                Text("纯音乐", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            lines.isEmpty() -> LyricHint {
                Text("暂无歌词", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            else -> LyricScroller(lines = lines, positionMs = positionMs, modifier = Modifier.fillMaxSize())
        }
    }
}

@Composable
private fun LyricHint(content: @Composable ColumnScope.() -> Unit) {
    Box(modifier = Modifier.fillMaxSize().padding(12.dp), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, content = content)
    }
}

@Composable
private fun LyricScroller(lines: List<LyricLine>, positionMs: Long, modifier: Modifier) {
    val listState = rememberLazyListState()
    val currentIndex = remember(positionMs, lines) {
        lines.indexOfLast { it.timeMs <= positionMs }.let { if (it < 0) 0 else it }
    }
    LaunchedEffect(currentIndex) {
        if (lines.isNotEmpty()) {
            listState.animateScrollToItem(index = (currentIndex - 2).coerceAtLeast(0))
        }
    }
    LazyColumn(
        state = listState,
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(vertical = 12.dp, horizontal = 10.dp),
    ) {
        itemsIndexed(lines) { index, line ->
            val active = index == currentIndex
            Column(modifier = Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = line.text,
                    style = if (active) MaterialTheme.typography.titleMedium else MaterialTheme.typography.bodyMedium,
                    fontWeight = if (active) FontWeight.Bold else FontWeight.Normal,
                    color = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
                line.trans?.takeIf { it.isNotBlank() }?.let { trans ->
                    Text(
                        text = trans,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                }
            }
        }
    }
}

@Composable
private fun LibraryTabs(selected: ListenLibraryTab, onSelected: (ListenLibraryTab) -> Unit) {
    ScrollableTabRow(selectedTabIndex = selected.ordinal, edgePadding = 0.dp) {
        ListenLibraryTab.entries.forEach { tab ->
            Tab(
                selected = selected == tab,
                onClick = { onSelected(tab) },
                text = { Text(tab.title, maxLines = 1) },
                icon = { Icon(tab.icon, contentDescription = null, modifier = Modifier.size(18.dp)) },
            )
        }
    }
}

@Composable
private fun LibraryContent(
    tab: ListenLibraryTab,
    state: ListenUiState,
    onSearchKeyword: (String) -> Unit,
    onSearch: (String) -> Unit,
    onPlaySong: (SongMeta) -> Unit,
    onQueueSong: (SongMeta) -> Unit,
    onLoadPlaylists: () -> Unit,
    onLoadPlaylistTracks: (PlaylistItem) -> Unit,
    onLoadDiscover: () -> Unit,
    onLoadDiscoverTracks: (PlaylistItem) -> Unit,
    onLoadToplistTracks: (ToplistItem) -> Unit,
    onLoadHistory: () -> Unit,
    onLoadLocal: () -> Unit,
    onUploadLocal: (Uri) -> Unit,
    onDeleteLocal: (SongMeta) -> Unit,
    onRemoveQueue: (Int) -> Unit,
    onClearQueue: () -> Unit,
    modifier: Modifier = Modifier,
) {
    when (tab) {
        ListenLibraryTab.Search -> SearchTab(state, onSearchKeyword, onSearch, onPlaySong, onQueueSong, modifier)
        ListenLibraryTab.Discover -> DiscoverTab(state, onLoadDiscover, onLoadDiscoverTracks, onPlaySong, onQueueSong, modifier)
        ListenLibraryTab.Playlists -> PlaylistsTab(state, onLoadPlaylists, onLoadPlaylistTracks, onPlaySong, onQueueSong, modifier)
        ListenLibraryTab.Charts -> ChartsTab(state, onLoadDiscover, onLoadToplistTracks, onPlaySong, onQueueSong, modifier)
        ListenLibraryTab.History -> HistoryTab(state, onLoadHistory, onPlaySong, onQueueSong, modifier)
        ListenLibraryTab.Local -> LocalTab(state, onLoadLocal, onUploadLocal, onDeleteLocal, onPlaySong, onQueueSong, modifier)
        ListenLibraryTab.Queue -> QueueTab(state, onRemoveQueue, onClearQueue, onPlaySong, modifier)
    }
}

@Composable
private fun SearchTab(
    state: ListenUiState,
    onSearchKeyword: (String) -> Unit,
    onSearch: (String) -> Unit,
    onPlaySong: (SongMeta) -> Unit,
    onQueueSong: (SongMeta) -> Unit,
    modifier: Modifier,
) {
    Column(modifier = modifier.padding(top = 12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = state.searchKeyword,
                onValueChange = onSearchKeyword,
                modifier = Modifier.weight(1f),
                singleLine = true,
                leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                placeholder = { Text("搜索歌曲") },
            )
            Spacer(Modifier.width(8.dp))
            FilledIconButton(onClick = { onSearch(state.searchKeyword) }) {
                Icon(Icons.Filled.Search, contentDescription = "搜索")
            }
        }
        LoadingLine(state.searchLoading)
        SongList(
            songs = state.searchResults,
            emptyMessage = if (state.searchKeyword.isBlank()) "输入关键词搜索" else "没有搜索结果",
            onPlaySong = onPlaySong,
            onQueueSong = onQueueSong,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun DiscoverTab(
    state: ListenUiState,
    onRefresh: () -> Unit,
    onLoadTracks: (PlaylistItem) -> Unit,
    onPlaySong: (SongMeta) -> Unit,
    onQueueSong: (SongMeta) -> Unit,
    modifier: Modifier,
) {
    LazyColumn(
        modifier = modifier.padding(top = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            SectionHeader(title = "每日推荐", loading = state.discoverLoading, onRefresh = onRefresh)
        }
        if (state.recommendSongs.isEmpty()) {
            item { EmptyText("暂无推荐歌曲") }
        } else {
            items(state.recommendSongs.take(12)) { song ->
                SongRow(song = song, onPlay = { onPlaySong(song) }, onQueue = { onQueueSong(song) })
            }
        }
        item {
            SectionHeader(title = "推荐歌单", loading = state.discoverLoading, onRefresh = onRefresh)
        }
        if (state.discoverPlaylists.isEmpty()) {
            item { EmptyText("暂无推荐歌单") }
        } else {
            items(state.discoverPlaylists) { playlist ->
                PlaylistRow(
                    playlist = playlist,
                    selected = playlist.playlistId == state.selectedDiscoverPlaylist?.playlistId,
                    onClick = { onLoadTracks(playlist) },
                )
            }
        }
        if (state.selectedDiscoverPlaylist != null) {
            item { SubTitle(state.selectedDiscoverPlaylist.name) }
            items(state.discoverPlaylistTracks) { song ->
                SongRow(song = song, onPlay = { onPlaySong(song) }, onQueue = { onQueueSong(song) })
            }
        }
    }
}

@Composable
private fun PlaylistsTab(
    state: ListenUiState,
    onRefresh: () -> Unit,
    onLoadTracks: (PlaylistItem) -> Unit,
    onPlaySong: (SongMeta) -> Unit,
    onQueueSong: (SongMeta) -> Unit,
    modifier: Modifier,
) {
    LazyColumn(
        modifier = modifier.padding(top = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item { SectionHeader(title = "我的歌单", loading = state.playlistsLoading, onRefresh = onRefresh) }
        if (state.playlists.isEmpty()) {
            item { EmptyText("暂无歌单") }
        } else {
            items(state.playlists) { playlist ->
                PlaylistRow(
                    playlist = playlist,
                    selected = playlist.playlistId == state.selectedPlaylist?.playlistId,
                    onClick = { onLoadTracks(playlist) },
                )
            }
        }
        if (state.selectedPlaylist != null) {
            item { SubTitle(state.selectedPlaylist.name) }
            items(state.playlistTracks) { song ->
                SongRow(song = song, onPlay = { onPlaySong(song) }, onQueue = { onQueueSong(song) })
            }
        }
    }
}

@Composable
private fun ChartsTab(
    state: ListenUiState,
    onRefresh: () -> Unit,
    onLoadTracks: (ToplistItem) -> Unit,
    onPlaySong: (SongMeta) -> Unit,
    onQueueSong: (SongMeta) -> Unit,
    modifier: Modifier,
) {
    LazyColumn(
        modifier = modifier.padding(top = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item { SectionHeader(title = "榜单", loading = state.chartsLoading, onRefresh = onRefresh) }
        if (state.toplists.isEmpty()) {
            item { EmptyText("暂无榜单") }
        } else {
            items(state.toplists) { toplist ->
                ToplistRow(
                    toplist = toplist,
                    selected = toplist.toplistId == state.selectedToplist?.toplistId,
                    onClick = { onLoadTracks(toplist) },
                )
            }
        }
        if (state.selectedToplist != null) {
            item { SubTitle(state.selectedToplist.name) }
            items(state.toplistTracks) { song ->
                SongRow(song = song, onPlay = { onPlaySong(song) }, onQueue = { onQueueSong(song) })
            }
        }
    }
}

@Composable
private fun HistoryTab(
    state: ListenUiState,
    onRefresh: () -> Unit,
    onPlaySong: (SongMeta) -> Unit,
    onQueueSong: (SongMeta) -> Unit,
    modifier: Modifier,
) {
    Column(modifier = modifier.padding(top = 12.dp)) {
        SectionHeader(title = "听歌历史", loading = state.historyLoading, onRefresh = onRefresh)
        SongList(
            songs = state.history.map { it.toSongMeta() },
            emptyMessage = "还没有听歌记录",
            onPlaySong = onPlaySong,
            onQueueSong = onQueueSong,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun LocalTab(
    state: ListenUiState,
    onRefresh: () -> Unit,
    onUpload: (Uri) -> Unit,
    onDelete: (SongMeta) -> Unit,
    onPlaySong: (SongMeta) -> Unit,
    onQueueSong: (SongMeta) -> Unit,
    modifier: Modifier,
) {
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) onUpload(uri)
    }
    Column(modifier = modifier.padding(top = 12.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            SectionTitle("本地上传", modifier = Modifier.weight(1f))
            IconButton(onClick = onRefresh) {
                Icon(Icons.Filled.Refresh, contentDescription = "刷新")
            }
            FilledTonalIconButton(onClick = { launcher.launch(arrayOf("audio/*")) }) {
                if (state.localUploading) {
                    CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                } else {
                    Icon(Icons.Filled.FileUpload, contentDescription = "上传")
                }
            }
        }
        LoadingLine(state.localLoading || state.localUploading)
        if (state.localTracks.isEmpty()) {
            EmptyState(message = "还没有本地歌曲")
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.weight(1f)) {
                items(state.localTracks) { song ->
                    SongRow(
                        song = song,
                        onPlay = { onPlaySong(song) },
                        onQueue = { onQueueSong(song) },
                        trailing = {
                            IconButton(onClick = { onDelete(song) }) {
                                Icon(Icons.Filled.Delete, contentDescription = "删除")
                            }
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun QueueTab(
    state: ListenUiState,
    onRemoveQueue: (Int) -> Unit,
    onClearQueue: () -> Unit,
    onPlaySong: (SongMeta) -> Unit,
    modifier: Modifier,
) {
    Column(modifier = modifier.padding(top = 12.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            SectionTitle("播放队列", modifier = Modifier.weight(1f))
            TextButton(onClick = onClearQueue, enabled = state.queue.isNotEmpty()) {
                Text("清空")
            }
        }
        if (state.queue.isEmpty()) {
            EmptyState(message = "队列为空")
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.weight(1f)) {
                itemsIndexed(state.queue) { index, song ->
                    SongRow(
                        song = song,
                        onPlay = { onPlaySong(song) },
                        onQueue = null,
                        leadingText = "${index + 1}",
                        trailing = {
                            IconButton(onClick = { onRemoveQueue(index) }) {
                                Icon(Icons.Filled.Delete, contentDescription = "移除")
                            }
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun SongList(
    songs: List<SongMeta>,
    emptyMessage: String,
    onPlaySong: (SongMeta) -> Unit,
    onQueueSong: (SongMeta) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (songs.isEmpty()) {
        Box(modifier = modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
            EmptyState(message = emptyMessage)
        }
        return
    }
    LazyColumn(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(vertical = 8.dp),
    ) {
        items(songs) { song ->
            SongRow(song = song, onPlay = { onPlaySong(song) }, onQueue = { onQueueSong(song) })
        }
    }
}

@Composable
private fun SongRow(
    song: SongMeta,
    onPlay: () -> Unit,
    onQueue: (() -> Unit)?,
    leadingText: String? = null,
    trailing: (@Composable () -> Unit)? = null,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onPlay)
                .padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (leadingText != null) {
                Box(modifier = Modifier.width(34.dp), contentAlignment = Alignment.Center) {
                    Text(leadingText, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                }
            } else {
                AsyncImage(
                    model = song.coverUrl,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .size(46.dp)
                        .clip(RoundedCornerShape(6.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant),
                )
            }
            Spacer(Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    song.name.ifBlank { "未知歌曲" },
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    song.artists.joinToString(" / "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            IconButton(onClick = onPlay) {
                Icon(Icons.Filled.PlayArrow, contentDescription = "播放")
            }
            if (onQueue != null) {
                IconButton(onClick = onQueue) {
                    Icon(Icons.Filled.PlaylistAdd, contentDescription = "加入队列")
                }
            }
            trailing?.invoke()
        }
    }
}

@Composable
private fun PlaylistRow(playlist: PlaylistItem, selected: Boolean, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
        ),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AsyncImage(
                model = playlist.coverUrl,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(48.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant),
            )
            Spacer(Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    playlist.name,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    "${playlist.trackCount} 首",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun ToplistRow(toplist: ToplistItem, selected: Boolean, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
        ),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AsyncImage(
                model = toplist.coverUrl,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(48.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant),
            )
            Spacer(Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    toplist.name,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    listOfNotNull(toplist.updateFrequency, "${toplist.trackCount} 首").joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String, loading: Boolean, onRefresh: () -> Unit) {
    Column {
        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            SectionTitle(title, modifier = Modifier.weight(1f))
            IconButton(onClick = onRefresh) {
                Icon(Icons.Filled.Refresh, contentDescription = "刷新")
            }
        }
        LoadingLine(loading)
    }
}

@Composable
private fun SectionTitle(title: String, modifier: Modifier = Modifier) {
    Text(title, modifier = modifier, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
}

@Composable
private fun SubTitle(title: String) {
    AssistChip(onClick = {}, label = { Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis) })
}

@Composable
private fun EmptyText(message: String) {
    Text(
        message,
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 16.dp),
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )
}

@Composable
private fun LoadingLine(loading: Boolean) {
    if (loading) {
        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
    } else {
        Spacer(Modifier.height(4.dp))
    }
}

private val ListenLibraryTab.icon: ImageVector
    get() = when (this) {
        ListenLibraryTab.Search -> Icons.Filled.Search
        ListenLibraryTab.Discover -> Icons.Filled.MusicNote
        ListenLibraryTab.Playlists -> Icons.Filled.LibraryMusic
        ListenLibraryTab.Charts -> Icons.Filled.TrendingUp
        ListenLibraryTab.History -> Icons.Filled.History
        ListenLibraryTab.Local -> Icons.Filled.FileUpload
        ListenLibraryTab.Queue -> Icons.Filled.QueueMusic
    }

private fun ListenHistoryItem.toSongMeta(): SongMeta =
    SongMeta(
        songId = songId,
        name = name,
        artists = artists,
        album = album,
        durationMs = durationMs,
        coverUrl = coverUrl,
    )

@Composable
private fun LoadingState() {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator()
    }
}

@Composable
private fun ErrorState(message: String?) {
    Box(modifier = Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        Text(
            message ?: "加载失败",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.error,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun EmptyState(message: String, modifier: Modifier = Modifier) {
    Box(modifier = modifier.fillMaxWidth().padding(vertical = 18.dp), contentAlignment = Alignment.Center) {
        Text(
            message,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}
