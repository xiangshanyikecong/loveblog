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

/// M6 contracts: vault, period, footprints, reports, recycle bin, privacy,
/// security, TOTP, devices and site settings.
public enum CareDTOs {
    // MARK: - Vault (client-side E2EE, server is blind storage)

    public struct VaultMeta: Decodable {
        public var initialized: Bool
        public var salt: String?
        public var kdf: String?
        public var kdfHash: String?
        public var iterations: Int?
        public var algo: String?
        public var verifierIv: String?
        public var verifierCipher: String?

        enum CodingKeys: String, CodingKey {
            case initialized, salt, kdf, iterations, algo
            case kdfHash = "kdf_hash"
            case verifierIv = "verifier_iv"
            case verifierCipher = "verifier_cipher"
        }
    }

    public struct VaultSetup: Encodable {
        public var salt: String
        public var kdf: String
        public var kdfHash: String
        public var iterations: Int
        public var algo: String
        public var verifierIv: String
        public var verifierCipher: String

        enum CodingKeys: String, CodingKey {
            case salt, kdf, iterations, algo
            case kdfHash = "kdf_hash"
            case verifierIv = "verifier_iv"
            case verifierCipher = "verifier_cipher"
        }
    }

    public struct VaultEntry: Decodable, Identifiable {
        public var vid: String
        public var iv: String
        public var ciphertext: String
        public var authorUid: String
        public var createdAt: Date
        public var updatedAt: Date

        public var id: String { vid }

        enum CodingKeys: String, CodingKey {
            case vid, iv, ciphertext
            case authorUid = "author_uid"
            case createdAt = "created_at"
            case updatedAt = "updated_at"
        }
    }

    public struct VaultEnvelope: Codable {
        /// Client-side plaintext shape: {"title": "...", "body": "..."}.
        public var title: String
        public var body: String

        public init(title: String, body: String) {
            self.title = title
            self.body = body
        }
    }

    public struct VaultCipherBody: Encodable {
        public var iv: String
        public var ciphertext: String

        public init(iv: String, ciphertext: String) {
            self.iv = iv
            self.ciphertext = ciphertext
        }
    }

    public struct VaultRekey: Encodable {
        public var salt: String
        public var kdf: String
        public var kdfHash: String
        public var iterations: Int
        public var algo: String
        public var verifierIv: String
        public var verifierCipher: String
        public var entries: [EntryBody]

        public struct EntryBody: Encodable {
            public var vid: String
            public var iv: String
            public var ciphertext: String

            public init(vid: String, iv: String, ciphertext: String) {
                self.vid = vid
                self.iv = iv
                self.ciphertext = ciphertext
            }
        }

        enum CodingKeys: String, CodingKey {
            case salt, kdf, iterations, algo, entries
            case kdfHash = "kdf_hash"
            case verifierIv = "verifier_iv"
            case verifierCipher = "verifier_cipher"
        }
    }

    // MARK: - Period

    public struct Period: Decodable, Identifiable {
        public var pcid: String
        /// YYYY-MM-DD
        public var startDate: String
        public var endDate: String?
        public var note: String?
        public var lengthDays: Int?
        public var authorUid: String
        public var authorNickname: String
        public var createdAt: Date

        public var id: String { pcid }

        enum CodingKeys: String, CodingKey {
            case pcid, note
            case startDate = "start_date"
            case endDate = "end_date"
            case lengthDays = "length_days"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case createdAt = "created_at"
        }
    }

    public struct PeriodUpsert: Encodable {
        public var startDate: String
        public var endDate: String?
        public var note: String?

        public init(startDate: String, endDate: String? = nil, note: String? = nil) {
            self.startDate = startDate
            self.endDate = endDate
            self.note = note
        }

        enum CodingKeys: String, CodingKey {
            case note
            case startDate = "start_date"
            case endDate = "end_date"
        }
    }

    public struct PeriodList: Decodable {
        public var items: [Period]
        public var total: Int
    }

    public struct PeriodSummary: Decodable {
        public var cycleCount: Int
        public var avgCycleDays: Int?
        public var avgPeriodDays: Int?
        public var lastStart: String?
        public var lastEnd: String?
        public var predictedNextStart: String?
        public var predictedDaysUntil: Int?
        /// in_period | due_soon | overdue | normal | unknown
        public var phase: String

        enum CodingKeys: String, CodingKey {
            case phase
            case cycleCount = "cycle_count"
            case avgCycleDays = "avg_cycle_days"
            case avgPeriodDays = "avg_period_days"
            case lastStart = "last_start"
            case lastEnd = "last_end"
            case predictedNextStart = "predicted_next_start"
            case predictedDaysUntil = "predicted_days_until"
        }
    }

    // MARK: - Footprints

    public struct FootprintCity: Decodable, Identifiable {
        public var city: String
        public var count: Int
        public var firstAt: Date?
        public var lastAt: Date?

        public var id: String { city }

        enum CodingKeys: String, CodingKey {
            case city, count
            case firstAt = "first_at"
            case lastAt = "last_at"
        }
    }

    public struct FootprintRecent: Decodable, Identifiable {
        public var city: String
        public var authorNickname: String
        public var createdAt: Date

        public var id: String { city + String(createdAt.timeIntervalSince1970) }

        enum CodingKeys: String, CodingKey {
            case city
            case authorNickname = "author_nickname"
            case createdAt = "created_at"
        }
    }

    public struct Footprints: Decodable {
        public var cities: [FootprintCity]
        public var totalCities: Int
        public var totalCheckins: Int
        public var recent: [FootprintRecent]

        enum CodingKeys: String, CodingKey {
            case cities, recent
            case totalCities = "total_cities"
            case totalCheckins = "total_checkins"
        }
    }

    // MARK: - Monthly report (`/cottage/reports/monthly`)

    public struct MonthlyStats: Decodable {
        public var checkins: Int
        public var moods: Int
        public var questions: Int
        public var answers: Int
        public var chatMessages: Int
        public var wishesCreated: Int
        public var wishesCompleted: Int
        public var plansCreated: Int
        public var plansCompleted: Int
        public var remindersCreated: Int

        enum CodingKeys: String, CodingKey {
            case checkins, moods, questions, answers
            case chatMessages = "chat_messages"
            case wishesCreated = "wishes_created"
            case wishesCompleted = "wishes_completed"
            case plansCreated = "plans_created"
            case plansCompleted = "plans_completed"
            case remindersCreated = "reminders_created"
        }
    }

    public struct MoodCount: Decodable, Identifiable {
        public var mood: String
        public var emoji: String?
        public var count: Int

        public var id: String { mood }
    }

    public struct ReportHighlight: Decodable, Identifiable {
        /// wish | plan | question
        public var kind: String
        public var title: String
        public var subtitle: String?
        public var occurredAt: Date?

        public var id: String { kind + title }

        enum CodingKeys: String, CodingKey {
            case kind, title, subtitle
            case occurredAt = "occurred_at"
        }
    }

    public struct MonthlyReport: Decodable {
        public var year: Int
        public var month: Int
        public var startDate: String
        public var endDate: String
        public var generatedAt: Date
        public var stats: MonthlyStats
        public var topMoods: [MoodCount]
        public var highlights: [ReportHighlight]

        enum CodingKeys: String, CodingKey {
            case year, month, stats, highlights
            case startDate = "start_date"
            case endDate = "end_date"
            case generatedAt = "generated_at"
            case topMoods = "top_moods"
        }
    }

    // MARK: - Annual report (`/reports/annual` — no cottage prefix!)

    public struct AnnualStats: Decodable {
        public var articles: Int
        public var albums: Int
        public var photos: Int
        public var checkins: Int
        public var messages: Int
        public var songsPlayed: Int
        public var songsMinutes: Int
        public var capsulesCreated: Int
        public var wishesCompleted: Int

        enum CodingKeys: String, CodingKey {
            case articles, albums, photos, checkins, messages
            case songsPlayed = "songs_played"
            case songsMinutes = "songs_minutes"
            case capsulesCreated = "capsules_created"
            case wishesCompleted = "wishes_completed"
        }
    }

    public struct AnnualMonth: Decodable, Identifiable {
        public var month: Int
        public var articles: Int
        public var songs: Int
        public var checkins: Int

        public var id: Int { month }
    }

    public struct TopSong: Decodable, Identifiable {
        public var songId: String
        public var name: String
        public var artists: [String]?
        public var coverUrl: String?
        public var playCount: Int

        public var id: String { songId }

        enum CodingKeys: String, CodingKey {
            case name, artists
            case songId = "song_id"
            case coverUrl = "cover_url"
            case playCount = "play_count"
        }
    }

    public struct AnnualReport: Decodable {
        public var year: Int
        public var coupleSince: String?
        public var daysTogether: Int
        public var stats: AnnualStats
        public var monthly: [AnnualMonth]
        public var topSongs: [TopSong]
        public var highlights: [String]

        enum CodingKeys: String, CodingKey {
            case year, stats, monthly, highlights
            case coupleSince = "couple_since"
            case daysTogether = "days_together"
            case topSongs = "top_songs"
        }
    }

    // MARK: - Recycle bin

    public struct RecycleItem: Decodable, Identifiable {
        /// aid / alb_id / eid / mid / msg_id depending on type.
        public var id: String
        /// article | album | event | moment | message
        public var type: String
        public var title: String
        public var deletedAt: Date

        enum CodingKeys: String, CodingKey {
            case id, type, title
            case deletedAt = "deleted_at"
        }
    }

    public struct RecycleList: Decodable {
        public var items: [RecycleItem]
        public var total: Int
    }

    // MARK: - Privacy center

    public struct PrivacyCounts: Decodable {
        public var `public`: Int?
        public var signedIn: Int?
        public var partners: Int?
        public var authorOnly: Int?
        public var password: Int?
        public var endToEndEncrypted: Int?
        public var serverReadable: Int?
        public var serverMasked: Int?

        enum CodingKeys: String, CodingKey {
            case `public`
            case signedIn = "signed_in"
            case partners
            case authorOnly = "author_only"
            case password
            case endToEndEncrypted = "end_to_end_encrypted"
            case serverReadable = "server_readable"
            case serverMasked = "server_masked"
        }
    }

    public struct PrivacyModule: Decodable, Identifiable {
        public var key: String
        public var label: String
        public var total: Int
        public var access: PrivacyCounts?
        public var protection: PrivacyCounts?
        public var managePath: String?
        public var note: String?

        public var id: String { key }

        enum CodingKeys: String, CodingKey {
            case key, label, total
            case access, protection
            case managePath = "manage_path"
            case note
        }
    }

    public struct PrivacyEncryption: Decodable, Identifiable {
        /// chat | vault
        public var scope: String
        public var label: String
        public var initialized: Bool
        public var algorithm: String?
        public var kdf: String?
        public var iterations: Int?
        public var itemCount: Int
        public var encryptedCount: Int
        public var managePath: String?

        public var id: String { scope }

        enum CodingKeys: String, CodingKey {
            case scope, label, initialized, iterations
            case algorithm = "algorithm"
            case kdf
            case itemCount = "item_count"
            case encryptedCount = "encrypted_count"
            case managePath = "manage_path"
        }
    }

    public struct PrivacyAccount: Decodable {
        public var uid: String
        public var nickname: String
        public var lastLoginAt: Date?
        public var lastLoginIp: String?
        public var passwordChangedAt: Date?
        public var sessionVersion: Int

        enum CodingKeys: String, CodingKey {
            case uid, nickname
            case lastLoginAt = "last_login_at"
            case lastLoginIp = "last_login_ip"
            case passwordChangedAt = "password_changed_at"
            case sessionVersion = "session_version"
        }
    }

    public struct PrivacySummary: Decodable {
        public var generatedAt: Date
        public var totals: PrivacyCounts?
        public var protection: PrivacyCounts?
        public var modules: [PrivacyModule]
        public var encryption: [PrivacyEncryption]
        public var account: PrivacyAccount

        enum CodingKeys: String, CodingKey {
            case totals, protection, modules, encryption, account
            case generatedAt = "generated_at"
        }
    }

    // MARK: - Security center / TOTP / devices

    public struct SecurityProfile: Decodable, Identifiable {
        public var uid: String
        public var username: String
        public var nickname: String
        public var role: String
        public var loginFailedCount: Int
        public var loginFreezeUntil: Date?
        public var passwordChangedAt: Date?
        public var sessionVersion: Int
        public var lastLoginIp: String?
        public var lastLoginAt: Date?

        public var id: String { uid }

        enum CodingKeys: String, CodingKey {
            case uid, username, nickname, role
            case loginFailedCount = "login_failed_count"
            case loginFreezeUntil = "login_freeze_until"
            case passwordChangedAt = "password_changed_at"
            case sessionVersion = "session_version"
            case lastLoginIp = "last_login_ip"
            case lastLoginAt = "last_login_at"
        }
    }

    public struct SecurityUserList: Decodable {
        public var items: [SecurityProfile]
        public var total: Int
    }

    public struct LoginDevice: Decodable, Identifiable {
        public var did: String
        public var deviceName: String
        public var ip: String?
        public var userAgent: String?
        public var firstSeenAt: Date?
        public var lastLoginAt: Date?

        public var id: String { did }

        enum CodingKeys: String, CodingKey {
            case did, ip
            case deviceName = "device_name"
            case userAgent = "user_agent"
            case firstSeenAt = "first_seen_at"
            case lastLoginAt = "last_login_at"
        }
    }

    public struct TotpSetup: Decodable {
        public var secret: String
        public var uri: String
    }

    public struct TotpStatus: Decodable {
        public var enabled: Bool
        public var recoveryCodesRemaining: Int

        enum CodingKeys: String, CodingKey {
            case enabled
            case recoveryCodesRemaining = "recovery_codes_remaining"
        }
    }

    public struct TotpEnabled: Decodable {
        public var enabled: Bool
        public var recoveryCodes: [String]
    }

    // MARK: - Site settings & profile

    public struct SiteSettings: Decodable {
        public var siteName: String
        public var loveStartDate: String?
        public var allowRegistration: Bool
        public var partnerAAvatar: String?
        public var partnerBAvatar: String?

        enum CodingKeys: String, CodingKey {
            case siteName = "site_name"
            case loveStartDate = "love_start_date"
            case allowRegistration = "allow_registration"
            case partnerAAvatar = "partner_a_avatar"
            case partnerBAvatar = "partner_b_avatar"
        }
    }
}
