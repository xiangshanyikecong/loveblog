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

import Foundation

/// M5 game contracts: five board/card games share one REST+WS protocol;
/// draw (guess-the-word) has its own; canvas is a pure relay.
public enum GameDTOs {
    public static let boardGames = ["gomoku", "tictactoe", "reversi", "memory", "linklink"]

    // MARK: - Shared board-game snapshot (`STATE` / `GET /{game}/state`)

    /// Every field except `gameKey` is optional because engines emit only the
    /// fields relevant to their game (and `waiting` rooms carry even less).
    public struct GameState: Decodable {
        public var gameKey: String
        /// waiting | playing | finished
        public var phase: String?
        public var size: Int?
        /// Flat board, row-major `idx = y * cols + x`; 0 empty / 1 black / 2
        /// white for the three boards; per-game meanings otherwise.
        public var cells: [Int]?
        public var cols: Int?
        public var rows: Int?
        /// memory: sanitized answer faces (only UP/MATCHED are real).
        public var tiles: [Int]?
        /// memory: 0 face-down / 1 up / 2 matched.
        public var states: [Int]?
        /// memory: 8 emoji icons.
        public var icons: [String]?
        /// linklink: block ids 1-24 in `cells`; `pending` = first pick.
        public var pending: [Int]?
        public var blackScore: Int?
        public var whiteScore: Int?
        /// black | white | null
        public var turn: String?
        public var turnUid: String?
        /// black | white | draw | null
        public var winner: String?
        public var winLine: [[Int]]?
        public var legalMoves: [[Int]]?
        public struct LastMove: Decodable {
            public var x: Int
            public var y: Int
            public var color: Int?
        }
        public var lastMove: LastMove?
        public var moveCount: Int?
        public var blackUid: String?
        public var whiteUid: String?
        public var startedBy: String?
        /// five | draw | count | surrender | score (draw) — omitted on some paths.
        public var endReason: String?
        public var undoRequestBy: String?
        public var seq: Int?
        public var serverTsMs: Int?
        /// Present on the REST `/state` response only — the WS `STATE` frame
        /// payload carries the same flat snapshot *without* players (presence
        /// arrives via PRESENCE / PRESENCE_SNAPSHOT frames instead).
        public var players: [GamePlayer]?

        public var isPlaying: Bool { phase == "playing" }
        public var isFinished: Bool { phase == "finished" }

        enum CodingKeys: String, CodingKey {
            case phase, size, cells, cols, rows, tiles, states, icons, pending, turn, seq, players
            case gameKey = "game_key"
            case blackScore = "black_score"
            case whiteScore = "white_score"
            case turnUid = "turn_uid"
            case winner, winLine = "win_line"
            case legalMoves = "legal_moves"
            case lastMove = "last_move"
            case moveCount = "move_count"
            case blackUid = "black_uid"
            case whiteUid = "white_uid"
            case startedBy = "started_by"
            case endReason = "end_reason"
            case undoRequestBy = "undo_request_by"
            case serverTsMs = "server_ts_ms"
        }
    }

    public struct GamePlayer: Decodable, Identifiable {
        public var uid: String
        public var nickname: String
        /// black | white | null
        public var color: String?
        public var online: Bool

        public var id: String { uid }
    }

    /// The wire shape is FLAT, not nested: the REST `GET /{game}/state`
    /// response and the WS `STATE` frame payload are both a single-level
    /// snapshot (`game_key`, `phase`, `cells`, …). Only the REST flavor
    /// carries a `players` array; WS delivers presence separately.
    public struct GameRoomState: Decodable {
        public var state: GameState
        public var players: [GamePlayer]

        public init(from decoder: Decoder) throws {
            let flat = try GameState(from: decoder)
            state = flat
            players = flat.players ?? []
        }
    }

    public struct GameMatch: Decodable, Identifiable {
        public var gmid: String
        public var gameKey: String
        public var blackUid: String?
        public var blackNickname: String?
        public var whiteUid: String?
        public var whiteNickname: String?
        public var winnerUid: String?
        public var isDraw: Bool
        /// five | draw | count | surrender | score
        public var endReason: String?
        public var moveCount: Int?
        public var createdAt: Date

        public var id: String { gmid }

        enum CodingKeys: String, CodingKey {
            case gmid, isDraw
            case gameKey = "game_key"
            case blackUid = "black_uid"
            case blackNickname = "black_nickname"
            case whiteUid = "white_uid"
            case whiteNickname = "white_nickname"
            case winnerUid = "winner_uid"
            case endReason = "end_reason"
            case moveCount = "move_count"
            case createdAt = "created_at"
        }
    }

    public struct PlayerStat: Decodable, Identifiable {
        public var uid: String
        public var nickname: String
        public var wins: Int

        public var id: String { uid }
    }

    public struct MatchList: Decodable {
        public var items: [GameMatch]
        public var total: Int
        public var draws: Int
        public var stats: [PlayerStat]
    }

    // MARK: - Draw (guess the word)

    public struct StrokeSeg: Codable, Equatable {
        public var sid: String
        /// Normalized 0...1 canvas coordinates.
        public var x0: Double
        public var y0: Double
        public var x1: Double
        public var y1: Double
        public var color: String
        public var size: Double
        public var eraser: Bool?

        public init(sid: String, x0: Double, y0: Double, x1: Double, y1: Double, color: String, size: Double, eraser: Bool? = nil) {
            self.sid = sid
            self.x0 = x0
            self.y0 = y0
            self.x1 = x1
            self.y1 = y1
            self.color = color
            self.size = size
            self.eraser = eraser
        }
    }

    public struct Stroke: Codable, Equatable, Identifiable {
        public var sid: String
        public var segs: [StrokeSeg]

        public var id: String { sid }

        public init(sid: String, segs: [StrokeSeg]) {
            self.sid = sid
            self.segs = segs
        }
    }

    public struct DrawGuess: Decodable, Identifiable {
        public var uid: String
        public var text: String
        public var correct: Bool
        public var tsMs: Int

        public var id: String { "\(uid)-\(tsMs)-\(text)" }

        enum CodingKeys: String, CodingKey {
            case uid, text, correct
            case tsMs = "ts_ms"
        }
    }

    public struct DrawState: Decodable {
        public var gameKey: String?
        /// waiting | drawing | round_end | finished
        public var phase: String
        public var aUid: String?
        public var bUid: String?
        public var drawerUid: String?
        public var round: Int?
        public var totalRounds: Int?
        public var scores: [String: Int]?
        public var wordLen: Int?
        public var wordMask: String?
        public var revealedWord: String?
        public var roundStartedMs: Int?
        public var roundDeadlineMs: Int?
        public var roundDurationSec: Int?
        public var guesses: [DrawGuess]?
        public var roundWinnerUid: String?
        public var winnerUid: String?
        public var seq: Int?
        public var serverTsMs: Int?

        enum CodingKeys: String, CodingKey {
            case phase, round, scores, guesses, seq
            case gameKey = "game_key"
            case aUid = "a_uid"
            case bUid = "b_uid"
            case drawerUid = "drawer_uid"
            case totalRounds = "total_rounds"
            case wordLen = "word_len"
            case wordMask = "word_mask"
            case revealedWord = "revealed_word"
            case roundStartedMs = "round_started_ms"
            case roundDeadlineMs = "round_deadline_ms"
            case roundDurationSec = "round_duration_sec"
            case roundWinnerUid = "round_winner_uid"
            case winnerUid = "winner_uid"
            case serverTsMs = "server_ts_ms"
        }
    }

    // MARK: - Canvas artworks

    public struct CanvasCollaborator: Decodable, Identifiable {
        public var userUid: String
        public var nickname: String
        public var strokeCount: Int

        public var id: String { userUid }

        enum CodingKeys: String, CodingKey {
            case nickname
            case userUid = "user_uid"
            case strokeCount = "stroke_count"
        }
    }

    public struct CanvasArtwork: Decodable, Identifiable {
        public var caid: String
        public var title: String?
        public var width: Int
        public var height: Int
        public var strokeCount: Int
        public var authorUid: String
        public var authorNickname: String
        public var thumbDataUrl: String?
        /// Only present in detail responses (list omits it).
        public var strokesJson: String?
        public var createdAt: Date
        public var updatedAt: Date
        public var collaborators: [CanvasCollaborator]

        public var id: String { caid }

        enum CodingKeys: String, CodingKey {
            case caid, title, width, height
            case strokeCount = "stroke_count"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case thumbDataUrl = "thumb_data_url"
            case strokesJson = "strokes_json"
            case createdAt = "created_at"
            case updatedAt = "updated_at"
            case collaborators
        }
    }

    public struct CanvasPage: Decodable {
        public var items: [CanvasArtwork]
        public var total: Int
        public var hasNext: Bool

        enum CodingKeys: String, CodingKey {
            case items, total
            case hasNext = "has_next"
        }
    }

    /// Parsed `strokes_json` document (also the SYNC frame payload shape).
    public struct StrokeDocument: Codable {
        public var width: Int
        public var height: Int
        public var strokes: [Stroke]

        public init(width: Int, height: Int, strokes: [Stroke]) {
            self.width = width
            self.height = height
            self.strokes = strokes
        }
    }

    public struct CanvasSave: Encodable {
        public var title: String?
        public var strokesJson: String
        public var thumbDataUrl: String
        public var width: Int
        public var height: Int
        public var idempotencyKey: String?

        public init(title: String?, strokesJson: String, thumbDataUrl: String, width: Int, height: Int, idempotencyKey: String? = nil) {
            self.title = title
            self.strokesJson = strokesJson
            self.thumbDataUrl = thumbDataUrl
            self.width = width
            self.height = height
            self.idempotencyKey = idempotencyKey
        }

        enum CodingKeys: String, CodingKey {
            case title, width, height
            case strokesJson = "strokes_json"
            case thumbDataUrl = "thumb_data_url"
            case idempotencyKey = "idempotency_key"
        }
    }
}

/// M5 daily-life modules: coupons, ledger, reminders, plans.
public enum LifeDTOs {
    // MARK: Coupons

    public struct Coupon: Decodable, Identifiable {
        public var cpid: String
        public var title: String
        public var description: String?
        public var icon: String?
        /// active | redeemed
        public var status: String
        public var authorUid: String
        public var authorNickname: String
        public var isMine: Bool
        public var redeemedAt: Date?
        public var redeemedByUid: String?
        public var redeemedByNickname: String?
        public var createdAt: Date

        public var id: String { cpid }
        public var isRedeemed: Bool { status == "redeemed" }

        enum CodingKeys: String, CodingKey {
            case cpid, title, description, icon, status
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case isMine = "is_mine"
            case redeemedAt = "redeemed_at"
            case redeemedByUid = "redeemed_by_uid"
            case redeemedByNickname = "redeemed_by_nickname"
            case createdAt = "created_at"
        }
    }

    public struct CouponCreate: Encodable {
        public var title: String
        public var description: String?
        public var icon: String?

        public init(title: String, description: String? = nil, icon: String? = nil) {
            self.title = title
            self.description = description
            self.icon = icon
        }
    }

    public struct CouponList: Decodable {
        public var items: [Coupon]
        public var total: Int
        public var active: Int
        public var redeemed: Int
    }

    // MARK: Ledger

    public struct LedgerEntry: Decodable, Identifiable {
        public var leid: String
        public var title: String
        public var note: String?
        public var amountCents: Int
        public var category: String?
        /// aa | treat | owed_full
        public var splitType: String
        /// YYYY-MM-DD
        public var spentOn: String
        public var payerUid: String
        public var payerNickname: String
        public var authorUid: String
        public var authorNickname: String
        public var createdAt: Date

        public var id: String { leid }

        enum CodingKeys: String, CodingKey {
            case leid, title, note, category
            case amountCents = "amount_cents"
            case splitType = "split_type"
            case spentOn = "spent_on"
            case payerUid = "payer_uid"
            case payerNickname = "payer_nickname"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case createdAt = "created_at"
        }
    }

    public struct LedgerUpsert: Encodable {
        public var title: String
        public var amountCents: Int
        public var note: String?
        public var category: String?
        /// me | partner
        public var payer: String
        /// aa | treat | owed_full
        public var splitType: String
        public var spentOn: String

        public init(title: String, amountCents: Int, note: String? = nil, category: String? = nil, payer: String, splitType: String = "aa", spentOn: String) {
            self.title = title
            self.amountCents = amountCents
            self.note = note
            self.category = category
            self.payer = payer
            self.splitType = splitType
            self.spentOn = spentOn
        }

        enum CodingKeys: String, CodingKey {
            case title, note, category, payer
            case amountCents = "amount_cents"
            case splitType = "split_type"
            case spentOn = "spent_on"
        }
    }

    public struct LedgerPatch: Encodable {
        public var title: String?
        public var amountCents: Int?
        public var note: String?
        public var category: String?
        public var payer: String?
        public var splitType: String?
        public var spentOn: String?

        enum CodingKeys: String, CodingKey {
            case title, note, category, payer
            case amountCents = "amount_cents"
            case splitType = "split_type"
            case spentOn = "spent_on"
        }
    }

    public struct PayerBreakdown: Decodable {
        public var uid: String
        public var nickname: String
        public var paidCents: Int

        enum CodingKeys: String, CodingKey {
            case uid, nickname
            case paidCents = "paid_cents"
        }
    }

    public struct CategoryBreakdown: Decodable {
        public var category: String
        public var amountCents: Int

        enum CodingKeys: String, CodingKey {
            case category
            case amountCents = "amount_cents"
        }
    }

    public struct LedgerBalance: Decodable {
        public var settled: Bool
        public var debtorUid: String?
        public var debtorNickname: String?
        public var creditorUid: String?
        public var creditorNickname: String?
        public var amountCents: Int

        enum CodingKeys: String, CodingKey {
            case settled
            case debtorUid = "debtor_uid"
            case debtorNickname = "debtor_nickname"
            case creditorUid = "creditor_uid"
            case creditorNickname = "creditor_nickname"
            case amountCents = "amount_cents"
        }
    }

    public struct LedgerSummary: Decodable {
        public var month: String
        public var totalSpentCents: Int
        public var entryCount: Int
        public var byPayer: [PayerBreakdown]
        public var byCategory: [CategoryBreakdown]
        public var balance: LedgerBalance

        enum CodingKeys: String, CodingKey {
            case month, balance
            case totalSpentCents = "total_spent_cents"
            case entryCount = "entry_count"
            case byPayer = "by_payer"
            case byCategory = "by_category"
        }
    }

    public struct LedgerPage: Decodable {
        public var items: [LedgerEntry]
        public var total: Int
        public var page: Int
        public var pageSize: Int
        public var hasNext: Bool

        enum CodingKeys: String, CodingKey {
            case items, total, page
            case pageSize = "page_size"
            case hasNext = "has_next"
        }
    }

    // MARK: Reminders

    public struct Reminder: Decodable, Identifiable {
        public var rid: String
        public var title: String
        public var note: String?
        public var remindAt: Date
        /// both | me | partner
        public var audience: String
        public var isDue: Bool
        public var isDone: Bool
        public var authorUid: String
        public var authorNickname: String
        public var doneAt: Date?
        public var doneByUid: String?
        public var doneByNickname: String?
        public var createdAt: Date
        public var updatedAt: Date

        public var id: String { rid }

        enum CodingKeys: String, CodingKey {
            case rid, title, note, audience
            case remindAt = "remind_at"
            case isDue = "is_due"
            case isDone = "is_done"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case doneAt = "done_at"
            case doneByUid = "done_by_uid"
            case doneByNickname = "done_by_nickname"
            case createdAt = "created_at"
            case updatedAt = "updated_at"
        }
    }

    public struct ReminderUpsert: Encodable {
        public var title: String
        public var note: String?
        public var remindAt: Date
        public var audience: String

        public init(title: String, note: String? = nil, remindAt: Date, audience: String = "both") {
            self.title = title
            self.note = note
            self.remindAt = remindAt
            self.audience = audience
        }

        enum CodingKeys: String, CodingKey {
            case title, note, audience
            case remindAt = "remind_at"
        }
    }

    public struct ReminderList: Decodable {
        public var items: [Reminder]
        public var total: Int
        public var active: Int
        public var done: Int
        public var due: Int
    }

    // MARK: Plans

    public struct PlanChecklistItem: Codable, Identifiable {
        public var key: String?
        public var text: String
        public var done: Bool

        public var id: String { key ?? text }

        enum CodingKeys: String, CodingKey {
            case key, text, done
        }
    }

    public struct Plan: Decodable, Identifiable {
        public var pid: String
        public var title: String
        public var description: String?
        public var location: String?
        /// YYYY-MM-DD
        public var planDate: String?
        /// planned | in_progress | done | cancelled
        public var status: String
        public var priority: Int
        public var checklist: [PlanChecklistItem]
        public var authorUid: String
        public var authorNickname: String
        public var completedAt: Date?
        public var completedByUid: String?
        public var completedByNickname: String?
        public var createdAt: Date
        public var updatedAt: Date

        public var id: String { pid }
        public var isDone: Bool { status == "done" }

        enum CodingKeys: String, CodingKey {
            case pid, title, description, location, status, priority, checklist
            case planDate = "plan_date"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case completedAt = "completed_at"
            case completedByUid = "completed_by_uid"
            case completedByNickname = "completed_by_nickname"
            case createdAt = "created_at"
            case updatedAt = "updated_at"
        }
    }

    public struct PlanUpsert: Encodable {
        public var title: String
        public var description: String?
        public var location: String?
        public var planDate: String?
        public var priority: Int?
        public var checklist: [PlanChecklistItem]?
        public var status: String?

        public init(title: String, description: String? = nil, location: String? = nil, planDate: String? = nil, priority: Int? = nil, checklist: [PlanChecklistItem]? = nil, status: String? = nil) {
            self.title = title
            self.description = description
            self.location = location
            self.planDate = planDate
            self.priority = priority
            self.checklist = checklist
            self.status = status
        }

        enum CodingKeys: String, CodingKey {
            case title, description, location, priority, checklist, status
            case planDate = "plan_date"
        }
    }

    public struct PlanList: Decodable {
        public var items: [Plan]
        public var total: Int
        public var active: Int
        public var completed: Int
        public var cancelled: Int
    }
}
