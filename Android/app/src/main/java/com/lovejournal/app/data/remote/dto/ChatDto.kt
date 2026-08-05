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
// 小屋·聊天 (cottage chat) — REST: /v1/cottage/chat/*, WS push: /v1/cottage/chat/ws
//
// ChatMessageResponse intentionally defaults every non-essential field so the
// SAME class parses both the REST response (has is_self/can_recall/…) and the
// leaner WS CHAT_MESSAGE payload (which omits them — see chat_features.event_payload).
// ---------------------------------------------------------------------------

@Serializable
data class ChatSendRequest(
    val type: String = "text",
    val content: String? = null,
    val media_url: String? = null,
    val audio_duration_sec: Int? = null,
    val reply_to_mid: String? = null,
    // Optional ISO 8601 timestamp (UTC) for "寄给未来" — when set, the
    // server stores the message as a future one and releases it at the
    // given time. Null means "send immediately".
    val visible_at: String? = null,
)

@Serializable
data class ChatReplyPreview(
    val mid: String = "",
    val sender_nickname: String = "",
    val type: String = "text",
    val content: String? = null,
    val is_recalled: Boolean = false,
)

@Serializable
data class ChatMessageResponse(
    val id: Long = 0,
    val mid: String = "",
    val sender_uid: String = "",
    val sender_nickname: String = "",
    val is_self: Boolean = false,
    val type: String = "text",
    val content: String? = null,
    val media_url: String? = null,
    val audio_duration_sec: Int? = null,
    val is_favorite: Boolean = false,
    val is_future: Boolean = false,
    val is_recalled: Boolean = false,
    val can_recall: Boolean = false,
    val recalled_at: String? = null,
    val reply_to: ChatReplyPreview? = null,
    val read_at: String? = null,
    val visible_at: String? = null,
    val created_at: String = "",
)

@Serializable
data class ChatHistoryResponse(
    val items: List<ChatMessageResponse> = emptyList(),
    val has_more: Boolean = false,
    val first_unread_mid: String? = null,
    val next_before_id: Int? = null,
)

@Serializable
data class ChatStateResponse(
    val partner_uid: String? = null,
    val partner_nickname: String? = null,
    val partner_online: Boolean = false,
    val self_online: Boolean = false,
    val unread: Int = 0,
)

@Serializable
data class PokeRequest(
    val kind: String = "poke",
)

@Serializable data class ChatFavoriteListResponse(val items: List<ChatMessageResponse> = emptyList())
@Serializable data class ChatFutureMessagesResponse(val items: List<ChatMessageResponse> = emptyList())
@Serializable data class ChatPinnedQuoteRequest(val mid: String)
@Serializable data class ChatPinnedQuoteResponse(val message: ChatMessageResponse? = null)
@Serializable data class ChatKeywordItem(val keyword: String, val count: Int)
@Serializable data class ChatKeywordsResponse(val on: String, val items: List<ChatKeywordItem> = emptyList())
@Serializable data class ChatMediaPanelResponse(
    val images: List<ChatMessageResponse> = emptyList(),
    val stickers: List<ChatMessageResponse> = emptyList(),
    val voices: List<ChatMessageResponse> = emptyList(),
    val favorites: List<ChatMessageResponse> = emptyList(),
)
@Serializable data class ChatMemoryCardResponse(
    val on: String,
    val total_messages: Int = 0,
    val self_messages: Int = 0,
    val partner_messages: Int = 0,
    val favorite_count: Int = 0,
    val first_message: ChatMessageResponse? = null,
    val last_message: ChatMessageResponse? = null,
    val pinned_quote: ChatMessageResponse? = null,
    val keywords: List<ChatKeywordItem> = emptyList(),
)
