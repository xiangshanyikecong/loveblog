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
// 小屋·协作画板作品集 (cottage canvas artwork gallery) —
// REST: /v1/cottage/canvas/artworks
//
// The drawing frames themselves stay in the WebSocket relay; the
// gallery only stores the *result* of a "保存到作品集" click (strokes
// snapshot + base64 PNG thumbnail).
// ---------------------------------------------------------------------------

@Serializable
data class CanvasArtworkCollaborator(
    val user_uid: String = "",
    val nickname: String = "",
    val stroke_count: Int = 0,
)

@Serializable
data class CanvasArtworkResponse(
    val caid: String = "",
    val title: String? = null,
    val width: Int = 960,
    val height: Int = 600,
    val stroke_count: Int = 0,
    val author_uid: String = "",
    val author_nickname: String = "",
    val thumb_data_url: String = "",
    val strokes_json: String? = null,
    val created_at: String = "",
    val updated_at: String = "",
    val collaborators: List<CanvasArtworkCollaborator> = emptyList(),
)

@Serializable
data class CanvasArtworkListResponse(
    val items: List<CanvasArtworkResponse> = emptyList(),
    val total: Int = 0,
    val has_next: Boolean = false,
)

@Serializable
data class CanvasArtworkCreateRequest(
    val title: String? = null,
    val strokes_json: String,
    val thumb_data_url: String,
    val width: Int = 960,
    val height: Int = 600,
    val idempotency_key: String? = null,
)
