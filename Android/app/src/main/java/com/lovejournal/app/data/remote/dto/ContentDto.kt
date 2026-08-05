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

// ---- Events ----

@Serializable
data class EventListResponse(
    val items: List<EventResponse> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class EventCreateRequest(
    val title: String,
    val date: String,
    val type: String = "Countdown",
    val is_important: Boolean = false,
    val is_yearly_repeat: Boolean = false,
    val visibility: String = "Public",
    val tags: List<String> = emptyList(),
)

// ---- Articles ----

@Serializable
data class ArticleListResponse(
    val items: List<ArticleSummary> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class ArticleSummary(
    val aid: String,
    val title: String,
    val excerpt: String? = null,
    val status: String = "Draft",
    val is_encrypted: Boolean = false,
    val visibility: String = "public",
    val requires_password: Boolean = false,
    val tags: List<String> = emptyList(),
    val author_uid: String? = null,
    val author_nickname: String? = null,
    val published_at: String? = null,
    val created_at: String? = null,
)

@Serializable
data class ArticleBlock(
    val bid: String,
    val block_type: String = "Paragraph",
    val content: String = "",
    val sort_order: Int = 0,
    val author_uid: String? = null,
    val author_nickname: String? = null,
)

@Serializable
data class ArticleBlockRequest(
    val block_type: String = "Paragraph",
    val content: String,
    val sort_order: Int = 0,
)

@Serializable
data class ArticleCreateRequest(
    val title: String,
    val excerpt: String? = null,
    val status: String = "Draft",
    val is_encrypted: Boolean = false,
    val partner_can_edit: Boolean = false,
    val visibility: String = "public",
    val password: String? = null,
    val cover_url: String? = null,
    val tags: List<String> = emptyList(),
    val blocks: List<ArticleBlockRequest> = emptyList(),
)

@Serializable
data class ArticlePatchRequest(
    val title: String? = null,
    val excerpt: String? = null,
    val status: String? = null,
    val is_encrypted: Boolean? = null,
    val partner_can_edit: Boolean? = null,
    val visibility: String? = null,
    val password: String? = null,
    val cover_url: String? = null,
    val tags: List<String>? = null,
)

@Serializable
data class ArticleDetail(
    val aid: String,
    val title: String,
    val excerpt: String? = null,
    val status: String = "Draft",
    val is_encrypted: Boolean = false,
    val visibility: String = "public",
    val tags: List<String> = emptyList(),
    val author_uid: String? = null,
    val author_nickname: String? = null,
    val published_at: String? = null,
    val created_at: String? = null,
    val blocks: List<ArticleBlock> = emptyList(),
    val comments: List<CommentNode> = emptyList(),
)

// ---- Albums ----

@Serializable
data class AlbumListResponse(
    val items: List<AlbumSummary> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class AlbumSummary(
    val alb_id: String,
    val title: String,
    val description: String? = null,
    val cover_url: String? = null,
    val is_encrypted: Boolean = false,
    val is_public: Boolean = true,
    val visibility: String = "public",
    val requires_password: Boolean = false,
    val tags: List<String> = emptyList(),
    val author_uid: String? = null,
    val author_nickname: String? = null,
    val media_count: Int = 0,
    val created_at: String? = null,
)

@Serializable
data class AlbumMedia(
    val media_id: String,
    val media_type: String = "Image",
    val file_url: String = "",
    val thumbnail_url: String? = null,
    val file_size: Long? = null,
    val mime_type: String? = null,
    val is_encrypted: Boolean = false,
)

@Serializable
data class AlbumMediaRequest(
    val media_type: String = "Image",
    val file_url: String,
    val thumbnail_url: String? = null,
    val file_size: Long? = null,
    val mime_type: String? = null,
    val is_encrypted: Boolean = false,
)

@Serializable
data class AlbumCreateRequest(
    val title: String,
    val description: String? = null,
    val cover_url: String? = null,
    val is_encrypted: Boolean = false,
    val is_public: Boolean = true,
    val visibility: String = "public",
    val password: String? = null,
    val tags: List<String> = emptyList(),
    val media_items: List<AlbumMediaRequest> = emptyList(),
)

@Serializable
data class AlbumPatchRequest(
    val title: String? = null,
    val description: String? = null,
    val cover_url: String? = null,
    val is_encrypted: Boolean? = null,
    val is_public: Boolean? = null,
    val visibility: String? = null,
    val password: String? = null,
    val tags: List<String>? = null,
)

@Serializable
data class AlbumDetail(
    val alb_id: String,
    val title: String,
    val description: String? = null,
    val cover_url: String? = null,
    val is_encrypted: Boolean = false,
    val is_public: Boolean = true,
    val visibility: String = "public",
    val tags: List<String> = emptyList(),
    val author_uid: String? = null,
    val author_nickname: String? = null,
    val media_count: Int = 0,
    val created_at: String? = null,
    val media_items: List<AlbumMedia> = emptyList(),
    val comments: List<CommentNode> = emptyList(),
)

@Serializable
data class CommentCreateRequest(
    val content: String,
    val parent_cid: String? = null,
    val mention_uids: List<String> = emptyList(),
)

@Serializable
data class CommentNode(
    val cid: String,
    val content: String,
    val author_uid: String? = null,
    val author_nickname: String? = null,
    val parent_cid: String? = null,
    val mention_uids: List<String> = emptyList(),
    val created_at: String? = null,
    val replies: List<CommentNode> = emptyList(),
)

@Serializable
data class ContentVersion(
    val vid: String,
    val content_type: String,
    val content_id: String,
    val version: Int,
    val title: String? = null,
    val note: String? = null,
    val actor_uid: String? = null,
    val actor_nickname: String? = null,
    val created_at: String? = null,
)

@Serializable
data class ContentVersionListResponse(
    val items: List<ContentVersion> = emptyList(),
    val total: Int = 0,
)
