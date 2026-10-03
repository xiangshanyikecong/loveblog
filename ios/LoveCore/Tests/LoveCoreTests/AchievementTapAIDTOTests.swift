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

import XCTest

@testable import LoveCore

/// Achievement / tap / AI contracts — fixtures mirror
/// `server/app/schemas/{achievements,cottage_tap,ai}.py`, including the
/// optional next-level fields (nil at max level) and the fractional-second
/// ISO datetimes the server emits.
final class AchievementTapAIDTOTests: XCTestCase {

    // MARK: - Achievements

    func testAchievementsDecodeFullContract() throws {
        let data = Data(
            """
            {"generated_at":"2026-10-03T08:00:00.123456+00:00",
             "stats":{"love_days":866,"articles":12,"albums":3,"moments":40,"capsules":2,
                      "checkins":88,"checkin_streak_days":5,"moods":60,"mood_streak_days":3,
                      "chat_messages":900,"games_played":7,"wishes_total":9,"wishes_completed":4,
                      "songs_played":120,"album_media":210},
             "level":{"level":1,"title":"初识","points":0,"next_level_points":100,
                      "next_level_title":"心动","progress_percent":0},
             "badges":[
               {"code":"writer","name":"笔耕不辍","description":"累计写下 1 篇日记","icon":"✍️",
                "category":"record","tier":"none","achieved":false,"current":0,"next_target":1},
               {"code":"diary10","name":"日记达人","description":"累计写下 10 篇日记","icon":"📚",
                "category":"record","tier":"gold","achieved":true,"current":12,"next_target":null}]}
            """.utf8
        )
        let achievements = try LoveAPIClient.decode(AchievementDTOs.Achievements.self, from: data)
        XCTAssertEqual(achievements.stats["love_days"], 866)
        XCTAssertEqual(achievements.stats["checkin_streak_days"], 5)
        XCTAssertEqual(achievements.level.title, "初识")
        XCTAssertEqual(achievements.level.nextLevelPoints, 100)
        XCTAssertEqual(achievements.level.progressPercent, 0)
        XCTAssertEqual(achievements.badges.count, 2)
        XCTAssertEqual(achievements.badges[0].id, "writer")
        XCTAssertFalse(achievements.badges[0].achieved)
        XCTAssertEqual(achievements.badges[0].nextTarget, 1)
        XCTAssertTrue(achievements.badges[1].achieved)
        XCTAssertEqual(achievements.badges[1].tier, "gold")
        XCTAssertNil(achievements.badges[1].nextTarget)
    }

    func testMaxLevelDecodesWithoutNextLevelFields() throws {
        let data = Data(
            """
            {"generated_at":"2026-10-03T08:00:00+00:00","stats":{"love_days":2000},
             "level":{"level":6,"title":"白首","points":5000,"next_level_points":null,
                      "next_level_title":null,"progress_percent":100},
             "badges":[]}
            """.utf8
        )
        let achievements = try LoveAPIClient.decode(AchievementDTOs.Achievements.self, from: data)
        XCTAssertNil(achievements.level.nextLevelPoints)
        XCTAssertNil(achievements.level.nextLevelTitle)
        XCTAssertEqual(achievements.level.progressPercent, 100)
        XCTAssertTrue(achievements.badges.isEmpty)
    }

    // MARK: - Taps

    func testTapCreateEncodesSnakeCaseKind() throws {
        let json = try JSONSerialization.jsonObject(
            with: LoveAPIClient.encoder.encode(TapDTOs.TapCreate(kind: "heartbeat"))
        ) as? [String: Any]
        XCTAssertEqual(json?["kind"] as? String, "heartbeat")
        XCTAssertEqual(json?.count, 1)
    }

    func testTapAndListDecode() throws {
        let data = Data(
            """
            {"items":[
               {"tid":"t1","kind":"tap","from_uid":"u1","from_nickname":"alice",
                "to_uid":"u2","to_nickname":"bob","created_at":"2026-10-03T07:00:00+00:00"},
               {"tid":"t2","kind":"heartbeat","from_uid":"u2","from_nickname":"bob",
                "to_uid":"u1","to_nickname":"alice","created_at":"2026-10-03T07:05:00.500000+00:00"}],
             "total_kept":42}
            """.utf8
        )
        let list = try LoveAPIClient.decode(TapDTOs.TapList.self, from: data)
        XCTAssertEqual(list.totalKept, 42)
        XCTAssertEqual(list.items.count, 2)
        XCTAssertFalse(list.items[0].isHeartbeat)
        XCTAssertTrue(list.items[1].isHeartbeat)
        XCTAssertEqual(list.items[0].id, "t1")
        XCTAssertEqual(list.items[0].fromNickname, "alice")
    }

    // MARK: - AI

    func testAIStatusDecodesAndChecksFeatures() throws {
        let data = Data(
            """
            {"enabled":true,"chat_model":"qwen-plus","embedding_model":"text-embedding-v3",
             "features":["article_polish","monthly_report","question_generate","semantic_search"]}
            """.utf8
        )
        let status = try LoveAPIClient.decode(AIDTOs.Status.self, from: data)
        XCTAssertTrue(status.enabled)
        XCTAssertEqual(status.chatModel, "qwen-plus")
        XCTAssertTrue(status.supports(AIDTOs.Feature.articlePolish))
        XCTAssertTrue(status.supports(AIDTOs.Feature.semanticSearch))
    }

    func testAIStatusDisabledSupportsNothing() throws {
        let data = Data(
            #"{"enabled":false,"chat_model":null,"embedding_model":null,"features":[]}"#.utf8
        )
        let status = try LoveAPIClient.decode(AIDTOs.Status.self, from: data)
        XCTAssertFalse(status.enabled)
        XCTAssertNil(status.embeddingModel)
        XCTAssertFalse(status.supports(AIDTOs.Feature.articlePolish))
    }

    func testAIPolishRequestEncodesAndResponseDecodes() throws {
        let json = try JSONSerialization.jsonObject(
            with: LoveAPIClient.encoder.encode(
                AIDTOs.PolishRequest(content: "今天我们去了海边", mode: "proofread")
            )
        ) as? [String: Any]
        XCTAssertEqual(json?["content"] as? String, "今天我们去了海边")
        XCTAssertEqual(json?["mode"] as? String, "proofread")

        let data = Data(#"{"text":"今天我们去了海边，风很轻。"}"#.utf8)
        let response = try LoveAPIClient.decode(AIDTOs.PolishResponse.self, from: data)
        XCTAssertEqual(response.text, "今天我们去了海边，风很轻。")
    }

    func testSemanticSearchRoundTrip() throws {
        let json = try JSONSerialization.jsonObject(
            with: LoveAPIClient.encoder.encode(AIDTOs.SemanticSearchRequest(query: "海边的约定", topK: 5))
        ) as? [String: Any]
        XCTAssertEqual(json?["query"] as? String, "海边的约定")
        XCTAssertEqual(json?["top_k"] as? Int, 5)

        let data = Data(
            """
            {"query":"海边的约定",
             "results":[{"aid":"a1","title":"海边日记","snippet":"那天我们说好…","score":0.87,
                         "updated_at":"2026-09-30T18:00:00+00:00"}],
             "indexed_count":12}
            """.utf8
        )
        let response = try LoveAPIClient.decode(AIDTOs.SemanticSearchResponse.self, from: data)
        XCTAssertEqual(response.indexedCount, 12)
        XCTAssertEqual(response.results.first?.id, "a1")
        XCTAssertEqual(response.results.first?.score ?? 0, 0.87, accuracy: 0.0001)
    }

    func testMonthlyReportAndQuestionsRoundTrip() throws {
        let reportJson = try JSONSerialization.jsonObject(
            with: LoveAPIClient.encoder.encode(AIDTOs.MonthlyReportRequest(year: 2026, month: 9))
        ) as? [String: Any]
        XCTAssertEqual(reportJson?["year"] as? Int, 2026)
        XCTAssertEqual(reportJson?["month"] as? Int, 9)

        let reportData = Data(#"{"year":2026,"month":9,"text":"这个月你们…" }"#.utf8)
        let report = try LoveAPIClient.decode(AIDTOs.MonthlyReportResponse.self, from: reportData)
        XCTAssertEqual(report.month, 9)
        XCTAssertFalse(report.text.isEmpty)

        let questionsJson = try JSONSerialization.jsonObject(
            with: LoveAPIClient.encoder.encode(AIDTOs.QuestionsRequest(count: 3))
        ) as? [String: Any]
        XCTAssertEqual(questionsJson?["count"] as? Int, 3)

        let questionsData = Data(
            #"{"questions":["如果重来一次初见，你想在哪？","对方最治愈你的瞬间？","一起最想去的海岛？"]}"#.utf8
        )
        let questions = try LoveAPIClient.decode(AIDTOs.QuestionsResponse.self, from: questionsData)
        XCTAssertEqual(questions.questions.count, 3)
    }
}
