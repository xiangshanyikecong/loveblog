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

/// M3 cottage contracts: E2EE chat, mood, check-ins, wishes, daily questions.
public enum CottageDTOs {
    // MARK: - Chat keys (`/v1/cottage/chat/keys`)

    public struct ChatKeyMeta: Decodable {
        public var initialized: Bool
        public var salt: String?
        public var kdf: String?
        public var kdfHash: String?
        public var iterations: Int?
        public var algo: String?
        public var verifierIv: String?
        public var verifierCipher: String?
        public var needsReEncrypt: Bool?

        enum CodingKeys: String, CodingKey {
            case initialized, salt, kdf, iterations, algo
            case kdfHash = "kdf_hash"
            case verifierIv = "verifier_iv"
            case verifierCipher = "verifier_cipher"
            case needsReEncrypt = "needs_re_encrypt"
        }
    }

    public struct ChatKeySetup: Encodable {
        public var salt: String
        public var kdf: String
        public var kdfHash: String
        public var iterations: Int
        public var algo: String
        public var verifierIv: String
        public var verifierCipher: String
        public var verifierHash: String

        enum CodingKeys: String, CodingKey {
            case salt, kdf, iterations, algo
            case kdfHash = "kdf_hash"
            case verifierIv = "verifier_iv"
            case verifierCipher = "verifier_cipher"
            case verifierHash = "verifier_hash"
        }
    }

    // MARK: - Chat messages (`/v1/cottage/chat/messages`)

    /// REST response superset; WS payloads omit isSelf/isFavorite/isFuture/
    /// canRecall — everything decodes with defaults.
    public struct ChatMessage: Decodable, Identifiable {
        public var id: Int
        public var mid: String
        public var senderUid: String
        public var senderNickname: String
        public var isSelf: Bool
        /// "text" | "image" | "sticker" | "voice"
        public var type: String
        public var content: String?
        public var mediaUrl: String?
        public var audioDurationSec: Int?
        public var isFavorite: Bool
        public var isFuture: Bool
        public var isRecalled: Bool
        public var canRecall: Bool
        public var recalledAt: Date?
        public var replyTo: ReplyPreview?
        public var readAt: Date?
        public var visibleAt: Date?
        public var createdAt: Date
        public var isEncrypted: Bool
        public var iv: String?
        public var ciphertext: String?
        public var algo: String?

        public var idKey: String { mid }

        public init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            id = try c.decode(Int.self, forKey: .id)
            mid = try c.decode(String.self, forKey: .mid)
            senderUid = try c.decodeIfPresent(String.self, forKey: .senderUid) ?? ""
            senderNickname = try c.decodeIfPresent(String.self, forKey: .senderNickname) ?? ""
            isSelf = try c.decodeIfPresent(Bool.self, forKey: .isSelf) ?? false
            type = try c.decodeIfPresent(String.self, forKey: .type) ?? "text"
            content = try c.decodeIfPresent(String.self, forKey: .content)
            mediaUrl = try c.decodeIfPresent(String.self, forKey: .mediaUrl)
            audioDurationSec = try c.decodeIfPresent(Int.self, forKey: .audioDurationSec)
            isFavorite = try c.decodeIfPresent(Bool.self, forKey: .isFavorite) ?? false
            isFuture = try c.decodeIfPresent(Bool.self, forKey: .isFuture) ?? false
            isRecalled = try c.decodeIfPresent(Bool.self, forKey: .isRecalled) ?? false
            canRecall = try c.decodeIfPresent(Bool.self, forKey: .canRecall) ?? false
            recalledAt = try c.decodeIfPresent(Date.self, forKey: .recalledAt)
            replyTo = try c.decodeIfPresent(ReplyPreview.self, forKey: .replyTo)
            readAt = try c.decodeIfPresent(Date.self, forKey: .readAt)
            visibleAt = try c.decodeIfPresent(Date.self, forKey: .visibleAt)
            createdAt = try c.decode(Date.self, forKey: .createdAt)
            isEncrypted = try c.decodeIfPresent(Bool.self, forKey: .isEncrypted) ?? false
            iv = try c.decodeIfPresent(String.self, forKey: .iv)
            ciphertext = try c.decodeIfPresent(String.self, forKey: .ciphertext)
            algo = try c.decodeIfPresent(String.self, forKey: .algo)
        }

        public struct ReplyPreview: Decodable {
            public var mid: String
            public var senderNickname: String
            public var type: String
            public var content: String?
            public var isRecalled: Bool
        }

        enum CodingKeys: String, CodingKey {
            case id, mid, type, content, replyTo, readAt
            case senderUid = "sender_uid"
            case senderNickname = "sender_nickname"
            case isSelf = "is_self"
            case mediaUrl = "media_url"
            case audioDurationSec = "audio_duration_sec"
            case isFavorite = "is_favorite"
            case isFuture = "is_future"
            case isRecalled = "is_recalled"
            case canRecall = "can_recall"
            case recalledAt = "recalled_at"
            case visibleAt = "visible_at"
            case createdAt = "created_at"
            case isEncrypted = "is_encrypted"
            case iv, ciphertext, algo
        }
    }

    public struct ChatHistory: Decodable {
        /// Ascending by id (server reverses its desc query).
        public var items: [ChatMessage]
        public var hasMore: Bool
        public var firstUnreadMid: String?
        public var nextBeforeId: Int?

        enum CodingKeys: String, CodingKey {
            case items
            case hasMore = "has_more"
            case firstUnreadMid = "first_unread_mid"
            case nextBeforeId = "next_before_id"
        }
    }

    public struct ChatSend: Encodable {
        public var type: String
        public var content: String?
        public var mediaUrl: String?
        public var audioDurationSec: Int?
        public var visibleAt: Date?
        public var replyToMid: String?
        public var isEncrypted: Bool
        public var iv: String?
        public var ciphertext: String?
        public var algo: String?

        public init(
            type: String = "text",
            content: String? = nil,
            mediaUrl: String? = nil,
            audioDurationSec: Int? = nil,
            visibleAt: Date? = nil,
            replyToMid: String? = nil,
            isEncrypted: Bool = false,
            iv: String? = nil,
            ciphertext: String? = nil,
            algo: String? = nil
        ) {
            self.type = type
            self.content = content
            self.mediaUrl = mediaUrl
            self.audioDurationSec = audioDurationSec
            self.visibleAt = visibleAt
            self.replyToMid = replyToMid
            self.isEncrypted = isEncrypted
            self.iv = iv
            self.ciphertext = ciphertext
            self.algo = algo
        }

        enum CodingKeys: String, CodingKey {
            case type, content, iv, ciphertext, algo
            case mediaUrl = "media_url"
            case audioDurationSec = "audio_duration_sec"
            case visibleAt = "visible_at"
            case replyToMid = "reply_to_mid"
            case isEncrypted = "is_encrypted"
        }
    }

    public struct ChatState: Decodable {
        public var partnerUid: String
        public var partnerNickname: String
        public var partnerOnline: Bool
        public var partnerOnlineSince: Date?
        public var partnerLastActiveAt: Date?
        public var selfOnline: Bool
        public var unread: Int

        enum CodingKeys: String, CodingKey {
            case unread
            case partnerUid = "partner_uid"
            case partnerNickname = "partner_nickname"
            case partnerOnline = "partner_online"
            case partnerOnlineSince = "partner_online_since"
            case partnerLastActiveAt = "partner_last_active_at"
            case selfOnline = "self_online"
        }
    }

    public struct PinnedQuote: Decodable {
        public var mid: String
        public var content: String
        public var senderNickname: String
        public var createdAt: Date

        enum CodingKeys: String, CodingKey {
            case mid, content
            case senderNickname = "sender_nickname"
            case createdAt = "created_at"
        }
    }

    // MARK: - Mood (`/v1/cottage/mood`)

    public struct Mood: Decodable, Identifiable, Equatable {
        public var mid: String
        public var authorUid: String
        public var authorNickname: String
        public var isSelf: Bool
        /// YYYY-MM-DD
        public var moodDate: String
        public var mood: String
        public var emoji: String?
        public var note: String?
        public var createdAt: Date
        public var updatedAt: Date

        public var id: String { mid }

        enum CodingKeys: String, CodingKey {
            case mid, mood, emoji, note
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case isSelf = "is_self"
            case moodDate = "mood_date"
            case createdAt = "created_at"
            case updatedAt = "updated_at"
        }
    }

    public struct MoodCreate: Encodable {
        public var mood: String
        public var emoji: String?
        public var note: String?
        public var moodDate: String?

        public init(mood: String, emoji: String?, note: String?, moodDate: String?) {
            self.mood = mood
            self.emoji = emoji
            self.note = note
            self.moodDate = moodDate
        }

        enum CodingKeys: String, CodingKey {
            case mood, emoji, note
            case moodDate = "mood_date"
        }
    }

    public struct TodayMoods: Decodable {
        public var mine: Mood?
        public var partner: Mood?
    }

    // MARK: - Check-ins (`/v1/checkins`)

    public struct CheckIn: Decodable, Identifiable {
        public var cid: String
        public var authorUid: String
        public var authorNickname: String
        public var content: String?
        public var mediaUrls: [String]
        public var locationText: String?
        /// resolved | permission_denied | lookup_failed | omitted
        public var locationStatus: String
        public var locationProvider: String?
        public var createdAt: Date

        public var id: String { cid }

        enum CodingKeys: String, CodingKey {
            case cid, content
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case mediaUrls = "media_urls"
            case locationText = "location_text"
            case locationStatus = "location_status"
            case locationProvider = "location_provider"
            case createdAt = "created_at"
        }
    }

    public struct CheckInCreate: Encodable {
        public var content: String?
        public var mediaUrls: [String]
        public var latitude: Double?
        public var longitude: Double?
        public var locationPermissionDenied: Bool?

        public init(
            content: String?,
            mediaUrls: [String] = [],
            latitude: Double? = nil,
            longitude: Double? = nil,
            locationPermissionDenied: Bool? = nil
        ) {
            self.content = content
            self.mediaUrls = mediaUrls
            self.latitude = latitude
            self.longitude = longitude
            self.locationPermissionDenied = locationPermissionDenied
        }

        enum CodingKeys: String, CodingKey {
            case content, latitude, longitude
            case mediaUrls = "media_urls"
            case locationPermissionDenied = "location_permission_denied"
        }
    }

    public struct CheckInList: Decodable {
        public var items: [CheckIn]
        public var page: Int
        public var pageSize: Int
        public var total: Int
        public var hasNext: Bool

        enum CodingKeys: String, CodingKey {
            case items, page, total
            case pageSize = "page_size"
            case hasNext = "has_next"
        }
    }

    public struct LatestCheckIn: Decodable {
        public var item: CheckIn?
    }

    // MARK: - Wishes (`/v1/cottage/wishes`)

    public struct Wish: Decodable, Identifiable {
        public var wid: String
        public var title: String
        public var description: String?
        public var category: String?
        /// pending | completed
        public var status: String
        public var priority: Int
        public var targetDate: String?
        public var authorUid: String
        public var authorNickname: String
        public var completedAt: Date?
        public var completedByUid: String?
        public var completedByNickname: String?
        public var createdAt: Date

        public var id: String { wid }
        public var isCompleted: Bool { status == "completed" }

        enum CodingKeys: String, CodingKey {
            case wid, title, description, category, status, priority
            case targetDate = "target_date"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case completedAt = "completed_at"
            case completedByUid = "completed_by_uid"
            case completedByNickname = "completed_by_nickname"
            case createdAt = "created_at"
        }
    }

    public struct WishCreate: Encodable {
        public var title: String
        public var description: String?
        public var category: String?
        public var targetDate: String?
        public var priority: Int

        public init(title: String, description: String? = nil, category: String? = nil, targetDate: String? = nil, priority: Int = 0) {
            self.title = title
            self.description = description
            self.category = category
            self.targetDate = targetDate
            self.priority = priority
        }

        enum CodingKeys: String, CodingKey {
            case title, description, category, priority
            case targetDate = "target_date"
        }
    }

    public struct WishList: Decodable {
        public var items: [Wish]
        public var total: Int
        public var pending: Int
        public var completed: Int
    }

    // MARK: - Daily questions (`/v1/cottage/questions`)

    public struct QuestionAnswer: Decodable {
        public var aid: String?
        public var authorUid: String
        public var authorNickname: String
        public var isSelf: Bool
        public var answered: Bool
        public var contentVisible: Bool
        public var content: String?
        public var createdAt: Date?
        public var updatedAt: Date?

        enum CodingKeys: String, CodingKey {
            case aid, answered, content
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case isSelf = "is_self"
            case contentVisible = "content_visible"
            case createdAt = "created_at"
            case updatedAt = "updated_at"
        }
    }

    public struct DailyQuestion: Decodable, Identifiable {
        public var qid: String
        public var questionDate: String
        public var prompt: String
        public var authorUid: String
        public var authorNickname: String
        public var revealed: Bool
        public var answeredCount: Int
        public var partnerCount: Int
        public var answers: [QuestionAnswer]
        public var createdAt: Date
        public var updatedAt: Date

        public var id: String { qid }
        public var myAnswer: QuestionAnswer? { answers.first { $0.isSelf } }

        enum CodingKeys: String, CodingKey {
            case qid, prompt, revealed, answers
            case questionDate = "question_date"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case answeredCount = "answered_count"
            case partnerCount = "partner_count"
            case createdAt = "created_at"
            case updatedAt = "updated_at"
        }
    }

    public struct TodayQuestion: Decodable {
        public var item: DailyQuestion?
    }
}
