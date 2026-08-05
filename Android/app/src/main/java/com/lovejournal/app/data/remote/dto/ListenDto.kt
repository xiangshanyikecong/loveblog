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

package com.lovejournal.app.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// ---------------------------------------------------------------------------
// 小屋·一起听 (cottage listen-together)
// REST: /v1/cottage/listen/*, WS: /v1/cottage/listen/ws.
// Field names are kept idiomatic in Kotlin and mapped to the backend's
// snake_case contract with @SerialName.
// ---------------------------------------------------------------------------

@Serializable
data class SongMeta(
    @SerialName("song_id") val songId: String = "",
    val name: String = "",
    val artists: List<String> = emptyList(),
    val album: String? = null,
    @SerialName("duration_ms") val durationMs: Long? = null,
    @SerialName("cover_url") val coverUrl: String? = null,
)

@Serializable
data class SongSearchResponse(
    val items: List<SongMeta> = emptyList(),
    val page: Int = 1,
    @SerialName("page_size") val pageSize: Int = 20,
    @SerialName("has_next") val hasNext: Boolean = false,
)

@Serializable
data class PlaylistItem(
    @SerialName("playlist_id") val playlistId: String = "",
    val name: String = "",
    @SerialName("cover_url") val coverUrl: String? = null,
    @SerialName("track_count") val trackCount: Int = 0,
)

@Serializable
data class PlaylistsResponse(
    val items: List<PlaylistItem> = emptyList(),
)

@Serializable
data class PlaylistTracksResponse(
    val items: List<SongMeta> = emptyList(),
    val page: Int = 1,
    @SerialName("page_size") val pageSize: Int = 50,
    @SerialName("has_next") val hasNext: Boolean = false,
)

@Serializable
data class ToplistItem(
    @SerialName("toplist_id") val toplistId: String = "",
    val name: String = "",
    @SerialName("cover_url") val coverUrl: String? = null,
    @SerialName("update_frequency") val updateFrequency: String? = null,
    @SerialName("track_count") val trackCount: Int = 0,
)

@Serializable
data class ToplistResponse(
    val items: List<ToplistItem> = emptyList(),
)

@Serializable
data class ListenHistoryItem(
    @SerialName("song_id") val songId: String = "",
    val name: String = "",
    val artists: List<String> = emptyList(),
    val album: String? = null,
    @SerialName("duration_ms") val durationMs: Long? = null,
    @SerialName("cover_url") val coverUrl: String? = null,
    @SerialName("played_at_ms") val playedAtMs: Long = 0L,
    @SerialName("started_by_uid") val startedByUid: String = "",
)

@Serializable
data class ListenHistoryResponse(
    val items: List<ListenHistoryItem> = emptyList(),
)

@Serializable
data class LocalTracksResponse(
    val items: List<SongMeta> = emptyList(),
)

@Serializable
data class SongUrlResponse(
    @SerialName("song_id") val songId: String = "",
    val url: String? = null,
    @SerialName("expires_at_ms") val expiresAtMs: Long? = null,
    val provider: String = "netease",
    @SerialName("error_kind") val errorKind: String? = null,
)

@Serializable
data class LyricLine(
    @SerialName("time_ms") val timeMs: Long = 0L,
    val text: String = "",
    val trans: String? = null,
)

@Serializable
data class SongLyricResponse(
    @SerialName("song_id") val songId: String = "",
    val lines: List<LyricLine> = emptyList(),
    val kind: String = "none",
)

@Serializable
data class PartnerLoginState(
    @SerialName("user_uid") val userUid: String = "",
    val nickname: String = "",
    @SerialName("netease_logged_in") val neteaseLoggedIn: Boolean = false,
)

@Serializable
data class RoomCurrent(
    @SerialName("song_id") val songId: String? = null,
    @SerialName("song_meta") val songMeta: SongMeta? = null,
    val paused: Boolean = true,
    @SerialName("position_ms") val positionMs: Long = 0L,
    @SerialName("started_by") val startedBy: String? = null,
    @SerialName("event_seq") val eventSeq: Long = 0L,
    @SerialName("server_ts_ms") val serverTsMs: Long = 0L,
)

@Serializable
data class RoomStateResponse(
    val current: RoomCurrent = RoomCurrent(),
    val queue: List<SongMeta> = emptyList(),
    val partners: List<PartnerLoginState> = emptyList(),
)

@Serializable
data class QrKeyResponse(
    val unikey: String = "",
    @SerialName("qr_image_data_url") val qrImageDataUrl: String = "",
)

@Serializable
data class QrStatusResponse(
    val status: String = "",
    val message: String? = null,
)

@Serializable
data class ImportCookieRequest(
    val cookie: String,
)

typealias ListenStateDto = RoomStateResponse
typealias ListenCurrentDto = RoomCurrent
typealias ListenSongMeta = SongMeta
typealias ListenQueueItem = SongMeta
typealias ListenPartnerDto = PartnerLoginState
typealias ListenLyricLine = LyricLine
typealias ListenLyricResponse = SongLyricResponse
