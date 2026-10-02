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

/// M4/M5 listen-together and game room contracts — fixtures mirror
/// `server/app/schemas/cottage_listen.py` (`RoomStateResponse`) and
/// `server/app/schemas/game.py` (`GameStateResponse`). Regression guards for
/// the two bugs that made 一起听 / 一起玩 die with "服务器响应格式异常":
/// the snake_case `event_seq` room field and the FLAT (not nested) game
/// snapshot shape shared by the REST `/state` response and the WS STATE frame.
final class MediaSyncGameDTOTests: XCTestCase {
    // MARK: - 一起听 room state

    func testListenStateDecodesSnakeCaseEventSeq() throws {
        let data = Data(
            """
            {"event_seq":7,
             "current":{"song_id":"186016","song_meta":{"song_id":"186016","name":"歌",
               "artists":["歌手"],"album":"专辑","duration_ms":243000,
               "cover_url":"http://cdn/cover.jpg"},
               "paused":false,"position_ms":42100,"started_by":"u1",
               "event_seq":6,"server_ts_ms":1790950000000},
             "queue":[{"song_id":"25906124","name":"下一首","artists":["A","B"]}],
             "partners":[{"user_uid":"u1","nickname":"我","netease_logged_in":true},
                         {"user_uid":"u2","nickname":"Ta","netease_logged_in":false}]}
            """.utf8
        )
        let state = try LoveAPIClient.decode(MediaSyncDTOs.ListenState.self, from: data)
        XCTAssertEqual(state.eventSeq, 7)
        XCTAssertEqual(state.current?.songId, "186016")
        XCTAssertEqual(state.current?.positionMs, 42100)
        XCTAssertFalse(state.current!.paused)
        XCTAssertEqual(state.current?.songMeta?.durationMs, 243000)
        XCTAssertEqual(state.queue.count, 1)
        XCTAssertEqual(state.queue.first?.artists, ["A", "B"])
        XCTAssertEqual(state.partners.count, 2)
        XCTAssertTrue(state.partners[0].neteaseLoggedIn)
        XCTAssertFalse(state.partners[1].neteaseLoggedIn)
    }

    func testListenStateDecodesEmptyRoom() throws {
        let data = Data(
            """
            {"event_seq":0,"current":{"song_id":null,"song_meta":null,"paused":true,
             "position_ms":0,"started_by":null,"event_seq":0,"server_ts_ms":1790950000000},
             "queue":[],"partners":[]}
            """.utf8
        )
        let state = try LoveAPIClient.decode(MediaSyncDTOs.ListenState.self, from: data)
        XCTAssertEqual(state.eventSeq, 0)
        XCTAssertNil(state.current?.songId)
        XCTAssertTrue(state.queue.isEmpty)
        XCTAssertTrue(state.partners.isEmpty)
    }

    // MARK: - 一起玩 room state (flat REST /state shape)

    func testGameRoomStateDecodesFlatRestResponseWithPlayers() throws {
        let data = Data(
            """
            {"game_key":"gomoku","phase":"playing","size":15,
             "cells":[0,0,1,0,0],"turn":"black","turn_uid":"u1",
             "winner":null,"win_line":[],"legal_moves":[],
             "last_move":{"x":2,"y":0,"color":1},"move_count":1,
             "black_uid":"u1","white_uid":"u2","started_by":"u1",
             "end_reason":null,"undo_request_by":null,"seq":3,
             "server_ts_ms":1790950000000,
             "players":[{"uid":"u1","nickname":"我","color":"black","online":true},
                        {"uid":"u2","nickname":"Ta","color":"white","online":false}]}
            """.utf8
        )
        let room = try LoveAPIClient.decode(GameDTOs.GameRoomState.self, from: data)
        XCTAssertEqual(room.state.gameKey, "gomoku")
        XCTAssertEqual(room.state.phase, "playing")
        XCTAssertEqual(room.state.size, 15)
        XCTAssertEqual(room.state.cells, [0, 0, 1, 0, 0])
        XCTAssertEqual(room.state.lastMove?.x, 2)
        XCTAssertEqual(room.state.turnUid, "u1")
        XCTAssertEqual(room.players.count, 2)
        XCTAssertEqual(room.players.first?.color, "black")
        XCTAssertTrue(room.players[0].online)
        XCTAssertFalse(room.players[1].online)
    }

    func testGameRoomStateDecodesFlatWsStatePayloadWithoutPlayers() throws {
        // The WS STATE frame payload is the same flat snapshot minus players.
        let data = Data(
            """
            {"game_key":"reversi","phase":"waiting","size":8,
             "cells":[],"turn":null,"turn_uid":null,"winner":null,
             "win_line":[],"legal_moves":[],"last_move":null,"move_count":0,
             "black_uid":null,"white_uid":null,"started_by":null,
             "end_reason":null,"undo_request_by":null,"seq":0,
             "server_ts_ms":1790950000000}
            """.utf8
        )
        let room = try LoveAPIClient.decode(GameDTOs.GameRoomState.self, from: data)
        XCTAssertEqual(room.state.gameKey, "reversi")
        XCTAssertEqual(room.state.phase, "waiting")
        XCTAssertNil(room.state.turn)
        XCTAssertTrue(room.players.isEmpty)
    }
}
