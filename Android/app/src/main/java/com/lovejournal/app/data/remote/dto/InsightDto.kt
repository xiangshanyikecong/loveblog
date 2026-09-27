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
// 回忆 · 年报 · 存储用量（对齐网页端 memories / reports/annual / storage/usage）
// ---------------------------------------------------------------------------

@Serializable
data class MemoryArticleItem(
    val aid: String,
    val title: String,
    val excerpt: String? = null,
    val created_at: String = "",
)

@Serializable
data class MemoryAlbumItem(
    val alb_id: String,
    val title: String,
    val cover_url: String? = null,
    val created_at: String = "",
)

@Serializable
data class MemorySongItem(
    val song_id: String = "",
    val name: String = "",
    val artists: List<String> = emptyList(),
    val cover_url: String? = null,
    val played_at: String = "",
)

@Serializable
data class MemoryTotals(
    val articles: Int = 0,
    val albums: Int = 0,
    val songs: Int = 0,
)

@Serializable
data class MemoryYearGroup(
    val year: Int = 0,
    val articles: List<MemoryArticleItem> = emptyList(),
    val albums: List<MemoryAlbumItem> = emptyList(),
    val songs: List<MemorySongItem> = emptyList(),
    val totals: MemoryTotals = MemoryTotals(),
)

@Serializable
data class OnThisDayResponse(
    val date: String = "",
    val years: List<MemoryYearGroup> = emptyList(),
    val totals: MemoryTotals = MemoryTotals(),
)

@Serializable
data class AnnualStats(
    val articles: Int = 0,
    val albums: Int = 0,
    val photos: Int = 0,
    val checkins: Int = 0,
    val messages: Int = 0,
    val songs_played: Int = 0,
    val songs_minutes: Int = 0,
    val capsules_created: Int = 0,
    val wishes_completed: Int = 0,
)

@Serializable
data class MonthlyActivity(
    val month: Int = 0,
    val articles: Int = 0,
    val albums: Int = 0,
    val photos: Int = 0,
    val checkins: Int = 0,
    val messages: Int = 0,
    val songs_played: Int = 0,
)

@Serializable
data class TopSong(
    val song_id: String = "",
    val name: String = "",
    val artists: List<String> = emptyList(),
    val cover_url: String? = null,
    val played_count: Int = 0,
)

@Serializable
data class AnnualReportResponse(
    val year: Int = 0,
    val couple_since: String? = null,
    val days_together: Int = 0,
    val stats: AnnualStats = AnnualStats(),
    val monthly: List<MonthlyActivity> = emptyList(),
    val top_songs: List<TopSong> = emptyList(),
    val highlights: List<String> = emptyList(),
)

// ---- 存储用量（后台管理 · 存储页）----

@Serializable
data class DiskInfo(
    val total_bytes: Long = 0,
    val used_bytes: Long = 0,
    val free_bytes: Long = 0,
    val percent: Double = 0.0,
)

@Serializable
data class DirInfo(
    val total_bytes: Long = 0,
    val file_count: Int = 0,
)

@Serializable
data class DbInfo(val size_bytes: Long? = null)

@Serializable
data class CategoryUsage(
    val category: String = "",
    val bytes: Long = 0,
    val file_count: Int = 0,
)

@Serializable
data class StorageUsageResponse(
    val disk: DiskInfo = DiskInfo(),
    val uploads: DirInfo = DirInfo(),
    val database: DbInfo = DbInfo(),
    val breakdown: List<CategoryUsage> = emptyList(),
)
