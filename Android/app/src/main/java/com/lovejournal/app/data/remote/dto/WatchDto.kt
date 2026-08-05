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

import kotlinx.serialization.Serializable

// ---------------------------------------------------------------------------
// 小屋·一起看 (cottage watch-together) — REST: /v1/cottage/watch/*,
// WS: /v1/cottage/watch/ws (LOAD/PLAY/PAUSE/SEEK/RATE + PRESENCE).
// ---------------------------------------------------------------------------

@Serializable
data class WatchSourceCreateRequest(
    val title: String,
    val url: String,
    val poster_url: String? = null,
)

@Serializable
data class WatchSourceResponse(
    val wsid: String = "",
    val title: String = "",
    val kind: String = "url", // "upload" | "url"
    val url: String = "",
    val poster_url: String? = null,
    val size_bytes: Long? = null,
    val author_uid: String = "",
    val author_nickname: String = "",
    val created_at: String = "",
    // Resume / bookmarks — populated by the server since 2026-07.
    val last_position_ms: Long = 0L,
    val last_viewed_at: String? = null,
    val bookmarks: List<WatchBookmark> = emptyList(),
)

@Serializable
data class WatchBookmark(
    val bid: String = "",
    val position_ms: Long = 0L,
    val label: String = "",
    val created_at: String = "",
    val created_by_uid: String = "",
)

@Serializable
data class WatchSourcePatchRequest(
    val last_position_ms: Long? = null,
    val bookmarks: List<WatchBookmark>? = null,
)

@Serializable
data class WatchSourceListResponse(
    val items: List<WatchSourceResponse> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class WatchPartnerState(
    val user_uid: String = "",
    val nickname: String = "",
    val online: Boolean = false,
)

@Serializable
data class WatchCurrent(
    val source_wsid: String? = null,
    val source_url: String? = null,
    val source_title: String? = null,
    val source_kind: String? = null,
    val paused: Boolean = true,
    val position_ms: Long = 0,
    val rate: Float = 1.0f,
    val started_by: String? = null,
    val event_seq: Long = 0,
    val server_ts_ms: Long = 0,
)

@Serializable
data class WatchStateResponse(
    val current: WatchCurrent = WatchCurrent(),
    val partners: List<WatchPartnerState> = emptyList(),
)
