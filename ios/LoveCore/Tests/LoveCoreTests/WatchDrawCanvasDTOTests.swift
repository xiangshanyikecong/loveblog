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

/// Contract guards for the remaining realtime cottage modules: watch-together
/// (`schemas/watch.py`), draw-and-guess (`services/cottage_games/draw.py`
/// `to_snapshot`) and canvas artworks (`schemas/canvas_artwork.py`).
/// Fixtures mirror the server shapes byte-for-byte in field names — same
/// pattern as MediaSyncGameDTOTests, extended after the 一起听/一起玩 decode
/// regressions so future schema drift fails here instead of in a release.
final class WatchDrawCanvasDTOTests: XCTestCase {
    // MARK: - 一起看 (watch)

    func testWatchStateDecodesPlayingRoom() throws {
        let data = Data(
            """
            {"current":{"source_wsid":"ws-1","source_url":"/uploads/watch/v.mp4",
               "source_title":"旅行视频","source_kind":"upload",
               "paused":false,"position_ms":91500,"rate":1.0,
               "started_by":"u1","event_seq":4,"server_ts_ms":1790950000000},
             "partners":[{"user_uid":"u1","nickname":"我","online":true},
                         {"user_uid":"u2","nickname":"Ta","online":false}]}
            """.utf8
        )
        let state = try LoveAPIClient.decode(MediaSyncDTOs.WatchState.self, from: data)
        let current = try XCTUnwrap(state.current)
        XCTAssertEqual(current.sourceWsid, "ws-1")
        XCTAssertEqual(current.sourceKind, "upload")
        XCTAssertFalse(current.paused)
        XCTAssertEqual(current.positionMs, 91500)
        XCTAssertEqual(current.eventSeq, 4)
        XCTAssertEqual(state.partners.count, 2)
        XCTAssertTrue(state.partners[0].online)
    }

    func testWatchStateDecodesIdleRoom() throws {
        let data = Data(
            """
            {"current":{"source_wsid":null,"source_url":null,"source_title":null,
               "source_kind":null,"paused":true,"position_ms":0,"rate":1.0,
               "started_by":null,"event_seq":0,"server_ts_ms":1790950000000},
             "partners":[]}
            """.utf8
        )
        let state = try LoveAPIClient.decode(MediaSyncDTOs.WatchState.self, from: data)
        XCTAssertNil(state.current?.sourceWsid)
        XCTAssertTrue(state.current!.paused)
        XCTAssertTrue(state.partners.isEmpty)
    }

    func testWatchSourceListDecodesResumeAndBookmarks() throws {
        let data = Data(
            """
            {"items":[
               {"wsid":"ws-1","title":"旅行视频","kind":"upload","url":"/uploads/watch/v.mp4",
                "poster_url":"/uploads/watch/poster.jpg","size_bytes":10485760,
                "author_uid":"u1","author_nickname":"我",
                "created_at":"2026-09-30T10:00:00+00:00",
                "last_position_ms":91500,"last_viewed_at":"2026-10-01T22:30:00+00:00",
                "bookmarks":[
                  {"bid":"bk-1","position_ms":45000,"label":"名场面",
                   "created_at":"2026-10-01T22:31:00+00:00","created_by_uid":"u2"}]},
               {"wsid":"ws-2","title":"直链","kind":"url","url":"https://cdn.example.com/a.m3u8",
                "poster_url":null,"size_bytes":null,
                "author_uid":"u2","author_nickname":"Ta",
                "created_at":"2026-10-02T08:00:00.123456+00:00",
                "last_position_ms":0,"last_viewed_at":null,"bookmarks":[]}],
             "total":2}
            """.utf8
        )
        let list = try LoveAPIClient.decode(MediaSyncDTOs.WatchSourceList.self, from: data)
        XCTAssertEqual(list.total, 2)
        XCTAssertEqual(list.items.count, 2)

        let first = list.items[0]
        XCTAssertEqual(first.wsid, "ws-1")
        XCTAssertEqual(first.kind, "upload")
        XCTAssertEqual(first.sizeBytes, 10_485_760)
        XCTAssertEqual(first.lastPositionMs, 91_500)
        XCTAssertEqual(first.bookmarks.count, 1)
        XCTAssertEqual(first.bookmarks.first?.label, "名场面")
        XCTAssertEqual(first.bookmarks.first?.createdByUid, "u2")

        let second = list.items[1]
        XCTAssertNil(second.posterUrl)
        XCTAssertNil(second.sizeBytes)
        XCTAssertNil(second.lastViewedAt)
        XCTAssertTrue(second.bookmarks.isEmpty)
    }

    // MARK: - 你画我猜 (draw) — WS snapshot shape

    func testDrawStateDecodesWaitingRoom() throws {
        // draw.py `_empty_room` + `to_snapshot`: waiting rooms carry nulls and
        // defaults everywhere (`total_rounds` 6, `round_duration_sec` 90).
        let data = Data(
            """
            {"game_key":"draw","phase":"waiting","a_uid":null,"b_uid":null,
             "drawer_uid":null,"round":0,"total_rounds":6,"scores":{},
             "word_len":0,"word_mask":"","revealed_word":null,
             "round_started_ms":null,"round_deadline_ms":null,
             "round_duration_sec":90,"guesses":[],
             "round_winner_uid":null,"winner_uid":null,"seq":0,
             "server_ts_ms":1790950000000}
            """.utf8
        )
        let state = try LoveAPIClient.decode(GameDTOs.DrawState.self, from: data)
        XCTAssertEqual(state.gameKey, "draw")
        XCTAssertEqual(state.phase, "waiting")
        XCTAssertEqual(state.totalRounds, 6)
        XCTAssertEqual(state.roundDurationSec, 90)
        XCTAssertEqual(state.wordMask, "")
        XCTAssertTrue(state.guesses?.isEmpty ?? false)
        XCTAssertNil(state.drawerUid)
    }

    func testDrawStateDecodesActiveRoundWithMaskedWordAndGuesses() throws {
        // During a round the secret ships only as length + `_ _ _ _` mask;
        // guesses carry the `ts_ms` snake_case key.
        let data = Data(
            """
            {"game_key":"draw","phase":"drawing","a_uid":"u1","b_uid":"u2",
             "drawer_uid":"u2","round":2,"total_rounds":6,
             "scores":{"u1":7,"u2":3},
             "word_len":4,"word_mask":"_ _ _ _","revealed_word":null,
             "round_started_ms":1790949960000,"round_deadline_ms":1790950050000,
             "round_duration_sec":90,
             "guesses":[{"uid":"u1","text":"月亮","correct":false,"ts_ms":1790949971000},
                        {"uid":"u1","text":"太阳","correct":true,"ts_ms":1790949985000}],
             "round_winner_uid":null,"winner_uid":null,"seq":11,
             "server_ts_ms":1790950000000}
            """.utf8
        )
        let state = try LoveAPIClient.decode(GameDTOs.DrawState.self, from: data)
        XCTAssertEqual(state.phase, "drawing")
        XCTAssertEqual(state.drawerUid, "u2")
        XCTAssertEqual(state.scores?["u1"], 7)
        XCTAssertEqual(state.wordLen, 4)
        XCTAssertEqual(state.wordMask, "_ _ _ _")
        XCTAssertNil(state.revealedWord)
        XCTAssertEqual(state.guesses?.count, 2)
        XCTAssertEqual(state.guesses?.last?.text, "太阳")
        XCTAssertTrue(state.guesses!.last!.correct)
        XCTAssertEqual(state.guesses?.last?.tsMs, 1_790_949_985_000)
    }

    func testDrawStateDecodesRoundEndWithRevealedWord() throws {
        let data = Data(
            """
            {"game_key":"draw","phase":"round_end","a_uid":"u1","b_uid":"u2",
             "drawer_uid":"u2","round":2,"total_rounds":6,
             "scores":{"u1":10,"u2":3},
             "word_len":4,"word_mask":"","revealed_word":"太阳",
             "round_started_ms":1790949960000,"round_deadline_ms":1790950050000,
             "round_duration_sec":90,"guesses":[],
             "round_winner_uid":"u1","winner_uid":null,"seq":12,
             "server_ts_ms":1790950060000}
            """.utf8
        )
        let state = try LoveAPIClient.decode(GameDTOs.DrawState.self, from: data)
        XCTAssertEqual(state.phase, "round_end")
        XCTAssertEqual(state.revealedWord, "太阳")
        XCTAssertEqual(state.roundWinnerUid, "u1")
    }

    // MARK: - 画板 (canvas)

    func testCanvasListDecodesWithoutStrokesJson() throws {
        // The gallery list intentionally omits `strokes_json` (wire size);
        // only the detail response carries it.
        let data = Data(
            """
            {"items":[
               {"caid":"ca-1","title":"周年纪念","width":960,"height":600,
                "stroke_count":128,"author_uid":"u1","author_nickname":"我",
                "thumb_data_url":"data:image/png;base64,iVBORw0KGgo=",
                "created_at":"2026-09-30T10:00:00+00:00",
                "updated_at":"2026-09-30T10:05:00+00:00",
                "collaborators":[
                  {"user_uid":"u1","nickname":"我","stroke_count":80},
                  {"user_uid":"u2","nickname":"Ta","stroke_count":48}]},
               {"caid":"ca-2","title":null,"width":960,"height":600,
                "stroke_count":12,"author_uid":"u2","author_nickname":"Ta",
                "thumb_data_url":"data:image/png;base64,iVBORw0KGgo=",
                "created_at":"2026-10-01T18:00:00+00:00",
                "updated_at":"2026-10-01T18:01:00+00:00",
                "collaborators":[]}],
             "total":2,"has_next":false}
            """.utf8
        )
        let page = try LoveAPIClient.decode(GameDTOs.CanvasPage.self, from: data)
        XCTAssertEqual(page.total, 2)
        XCTAssertFalse(page.hasNext)
        XCTAssertEqual(page.items.count, 2)

        let first = page.items[0]
        XCTAssertEqual(first.caid, "ca-1")
        XCTAssertEqual(first.strokeCount, 128)
        XCTAssertNil(first.strokesJson)
        XCTAssertEqual(first.collaborators.count, 2)
        XCTAssertEqual(first.collaborators.last?.strokeCount, 48)
        XCTAssertNil(page.items[1].title)
    }

    func testCanvasDetailStrokesJsonParsesIntoStrokeDocument() throws {
        // Detail responses return `strokes_json` as an escaped JSON string;
        // the client re-decodes it into a StrokeDocument to replay strokes.
        let document = """
            {"width":960,"height":600,"strokes":[
              {"sid":"s1","segs":[
                {"sid":"s1","x0":0.1,"y0":0.2,"x1":0.3,"y1":0.4,
                 "color":"#ff5a76","size":4,"eraser":false},
                {"sid":"s1","x0":0.3,"y0":0.4,"x1":0.5,"y1":0.6,
                 "color":"#ff5a76","size":4}]}]}
            """
        let escaped = document
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: "")
        let data = Data(
            """
            {"caid":"ca-1","title":"回放","width":960,"height":600,
             "stroke_count":1,"author_uid":"u1","author_nickname":"我",
             "thumb_data_url":"data:image/png;base64,iVBORw0KGgo=",
             "strokes_json":"\(escaped)",
             "created_at":"2026-09-30T10:00:00+00:00",
             "updated_at":"2026-09-30T10:05:00+00:00",
             "collaborators":[]}
            """.utf8
        )
        let artwork = try LoveAPIClient.decode(GameDTOs.CanvasArtwork.self, from: data)
        let strokesJson = try XCTUnwrap(artwork.strokesJson)
        let parsed = try LoveAPIClient.decode(
            GameDTOs.StrokeDocument.self, from: Data(strokesJson.utf8)
        )
        XCTAssertEqual(parsed.width, 960)
        XCTAssertEqual(parsed.strokes.count, 1)
        XCTAssertEqual(parsed.strokes.first?.segs.count, 2)
        XCTAssertEqual(parsed.strokes.first?.segs.first?.color, "#ff5a76")
        XCTAssertEqual(parsed.strokes.first?.segs.first?.x0 ?? 0, 0.1, accuracy: 0.0001)
        XCTAssertNil(parsed.strokes.first?.segs.last?.eraser)
    }
}
