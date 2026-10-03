/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, version 3 of the License.
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

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 小屋新模块（成就 / 轻触 / AI）DTO 解析测试。
 * JSON 载荷严格按后端 app.schemas.achievements / cottage_tap / ai 的响应构造，
 * Json 配置与 NetworkModule.provideJson 一致（ignoreUnknownKeys + explicitNulls=false）。
 */
class CottageNewDtoTest {

    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        explicitNulls = false
    }

    @Test
    fun `achievements response parses level stats and badges`() {
        val payload = """
            {
              "generated_at": "2026-10-03T10:00:00+00:00",
              "stats": {"love_days": 100, "articles": 3, "chat_messages": 42, "unknown_future_key": 7},
              "level": {"level": 1, "title": "初识", "points": 0, "next_level_points": 100,
                        "next_level_title": "心动", "progress_percent": 0},
              "badges": [
                {"code": "writer", "name": "笔耕不辍", "description": "累计写下 1 篇日记",
                 "icon": "✍️", "category": "record", "tier": "none", "achieved": false,
                 "current": 0, "next_target": 1}
              ]
            }
        """.trimIndent()

        val parsed = json.decodeFromString<AchievementsResponse>(payload)

        assertEquals(100, parsed.stats["love_days"])
        assertEquals(42, parsed.stats["chat_messages"])
        assertEquals(1, parsed.level.level)
        assertEquals("初识", parsed.level.title)
        assertEquals(100, parsed.level.next_level_points)
        assertEquals("心动", parsed.level.next_level_title)
        assertEquals(1, parsed.badges.size)
        val badge = parsed.badges.first()
        assertEquals("writer", badge.code)
        assertFalse(badge.achieved)
        assertEquals(0, badge.current)
        assertEquals(1, badge.next_target)
        // stats 是开放字典：未知键原样进入 map，由 UI 的 STAT_LABELS 决定展示与否。
        assertEquals(7, parsed.stats["unknown_future_key"])
    }

    @Test
    fun `achievements max level tolerates null next level fields`() {
        val payload = """
            {
              "generated_at": "2026-10-03T10:00:00+00:00",
              "stats": {},
              "level": {"level": 9, "title": "永恒", "points": 900,
                        "next_level_points": null, "next_level_title": null, "progress_percent": 100},
              "badges": [
                {"code": "soulmate", "name": "灵魂伴侣", "description": "", "icon": "💞",
                 "category": "time", "tier": "gold", "achieved": true, "current": 999, "next_target": null}
              ]
            }
        """.trimIndent()

        val parsed = json.decodeFromString<AchievementsResponse>(payload)

        assertEquals(9, parsed.level.level)
        assertNull(parsed.level.next_level_points)
        assertNull(parsed.level.next_level_title)
        assertEquals(100, parsed.level.progress_percent)
        assertTrue(parsed.badges.first().achieved)
        assertEquals("gold", parsed.badges.first().tier)
        assertNull(parsed.badges.first().next_target)
    }

    @Test
    fun `tap list response parses items and total kept`() {
        val payload = """
            {
              "items": [
                {"tid": "t1", "kind": "tap", "from_uid": "u1", "from_nickname": "小明",
                 "to_uid": "u2", "to_nickname": "小红", "created_at": "2026-10-03T09:00:00+00:00"},
                {"tid": "t2", "kind": "heartbeat", "from_uid": "u2", "from_nickname": "小红",
                 "to_uid": "u1", "to_nickname": "小明", "created_at": "2026-10-03T09:05:00+00:00"}
              ],
              "total_kept": 12
            }
        """.trimIndent()

        val parsed = json.decodeFromString<TapListResponse>(payload)

        assertEquals(2, parsed.items.size)
        assertEquals(12, parsed.total_kept)
        assertEquals("tap", parsed.items[0].kind)
        assertEquals("小明", parsed.items[0].from_nickname)
        assertEquals("heartbeat", parsed.items[1].kind)
        assertEquals("t2", parsed.items[1].tid)
    }

    @Test
    fun `ai status parses disabled state with null models`() {
        val payload = """{"enabled": false, "chat_model": null, "embedding_model": null, "features": []}"""

        val parsed = json.decodeFromString<AiStatusResponse>(payload)

        assertFalse(parsed.enabled)
        assertNull(parsed.chat_model)
        assertNull(parsed.embedding_model)
        assertTrue(parsed.features.isEmpty())
    }

    @Test
    fun `ai status parses enabled state with features`() {
        val payload = """
            {"enabled": true, "chat_model": "gpt-4o-mini", "embedding_model": "text-embedding-3-small",
             "features": ["article_polish", "monthly_report", "question_generate", "semantic_search"]}
        """.trimIndent()

        val parsed = json.decodeFromString<AiStatusResponse>(payload)

        assertTrue(parsed.enabled)
        assertEquals("gpt-4o-mini", parsed.chat_model)
        assertEquals(4, parsed.features.size)
        assertTrue(parsed.features.contains("semantic_search"))
    }

    @Test
    fun `ai semantic search response parses results and indexed count`() {
        val payload = """
            {
              "query": "海边的那个夏天",
              "results": [
                {"aid": "a1", "title": "夏日旅行", "snippet": "我们一起去了海边…", "score": 0.87,
                 "updated_at": "2026-08-01T12:00:00+00:00"},
                {"aid": "a2", "title": "周年纪念", "snippet": "", "score": 0.42, "updated_at": null}
              ],
              "indexed_count": 18
            }
        """.trimIndent()

        val parsed = json.decodeFromString<AiSemanticSearchResponse>(payload)

        assertEquals("海边的那个夏天", parsed.query)
        assertEquals(18, parsed.indexed_count)
        assertEquals(2, parsed.results.size)
        assertEquals("a1", parsed.results[0].aid)
        assertEquals(0.87, parsed.results[0].score, 1e-9)
        assertNull(parsed.results[1].updated_at)
    }

    @Test
    fun `ai polish monthly and questions responses parse`() {
        val polish = json.decodeFromString<AiPolishResponse>("""{"text": "润色后的正文"}""")
        assertEquals("润色后的正文", polish.text)

        val monthly = json.decodeFromString<AiMonthlyReportResponse>("""{"year": 2026, "month": 9, "text": "九月你们…"}""")
        assertEquals(2026, monthly.year)
        assertEquals(9, monthly.month)
        assertEquals("九月你们…", monthly.text)

        val questions = json.decodeFromString<AiQuestionsResponse>("""{"questions": ["Q1", "Q2", "Q3"]}""")
        assertEquals(listOf("Q1", "Q2", "Q3"), questions.questions)
    }
}
