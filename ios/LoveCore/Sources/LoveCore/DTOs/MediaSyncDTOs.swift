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

/// M4 contracts: listen-together and watch-together (global single rooms).
public enum MediaSyncDTOs {
    // MARK: - Shared song meta

    public struct SongMeta: Decodable, Identifiable, Equatable {
        public var songId: String
        public var name: String
        public var artists: [String]?
        public var album: String?
        public var durationMs: Int?
        public var coverUrl: String?

        public var id: String { songId }
        public var artistLine: String { artists?.joined(separator: " / ") ?? "" }

        enum CodingKeys: String, CodingKey {
            case name, artists, album
            case songId = "song_id"
            case durationMs = "duration_ms"
            case coverUrl = "cover_url"
        }
    }

    // MARK: - Listen (`/v1/cottage/listen`)

    public struct ListenCurrent: Decodable {
        public var songId: String?
        public var songMeta: SongMeta?
        public var paused: Bool
        public var positionMs: Int
        public var startedBy: String?
        public var eventSeq: Int?
        public var serverTsMs: Int?

        enum CodingKeys: String, CodingKey {
            case paused
            case songId = "song_id"
            case songMeta = "song_meta"
            case positionMs = "position_ms"
            case startedBy = "started_by"
            case eventSeq = "event_seq"
            case serverTsMs = "server_ts_ms"
        }
    }

    public struct ListenPartner: Decodable {
        public var userUid: String
        public var nickname: String
        public var neteaseLoggedIn: Bool

        enum CodingKeys: String, CodingKey {
            case nickname
            case userUid = "user_uid"
            case neteaseLoggedIn = "netease_logged_in"
        }
    }

    public struct ListenState: Decodable {
        public var eventSeq: Int
        public var current: ListenCurrent?
        public var queue: [SongMeta]
        public var partners: [ListenPartner]

        enum CodingKeys: String, CodingKey {
            case current, queue, partners
            case eventSeq = "event_seq"
        }
    }

    public struct SongSearch: Decodable {
        public var items: [SongMeta]
        public var page: Int
        public var pageSize: Int
        public var hasNext: Bool

        enum CodingKeys: String, CodingKey {
            case items, page
            case pageSize = "page_size"
            case hasNext = "has_next"
        }
    }

    public struct SongUrl: Decodable {
        public var songId: String
        /// null + errorKind == "unavailable" = copyright/VIP (skip, not error).
        public var url: String?
        public var expiresAtMs: Int?
        public var provider: String?
        public var errorKind: String?

        enum CodingKeys: String, CodingKey {
            case url, provider
            case songId = "song_id"
            case expiresAtMs = "expires_at_ms"
            case errorKind = "error_kind"
        }
    }

    public struct SongLyricLine: Decodable {
        public var timeMs: Int
        public var text: String
        public var translation: String?

        enum CodingKeys: String, CodingKey {
            case text
            case timeMs = "time_ms"
            case translation = "trans"
        }
    }

    public struct SongLyric: Decodable {
        public var songId: String
        public var lines: [SongLyricLine]
        /// lrc | instrumental | none
        public var kind: String

        enum CodingKeys: String, CodingKey {
            case lines, kind
            case songId = "song_id"
        }
    }

    public struct HistoryEntry: Decodable, Identifiable {
        public var songMeta: SongMeta
        public var playedAtMs: Int
        public var startedByUid: String

        public var id: String { songMeta.songId + String(playedAtMs) }

        enum CodingKeys: String, CodingKey {
            case songMeta = "song_meta"
            case playedAtMs = "played_at_ms"
            case startedByUid = "started_by_uid"
        }
    }

    public struct HistoryList: Decodable {
        public var items: [HistoryEntry]
    }

    public struct NeteasePlaylist: Decodable, Identifiable {
        public var playlistId: String
        public var name: String
        public var coverUrl: String?
        public var trackCount: Int?

        public var id: String { playlistId }

        enum CodingKeys: String, CodingKey {
            case name
            case playlistId = "playlist_id"
            case coverUrl = "cover_url"
            case trackCount = "track_count"
        }
    }

    public struct PlaylistList: Decodable {
        public var items: [NeteasePlaylist]
    }

    public struct CookieImport: Encodable {
        public var cookie: String

        public init(cookie: String) {
            self.cookie = cookie
        }
    }

    // MARK: - Watch (`/v1/cottage/watch`)

    public struct WatchBookmark: Decodable, Identifiable {
        public var bid: String
        public var positionMs: Int
        public var label: String
        public var createdAt: Date
        public var createdByUid: String

        public var id: String { bid }

        enum CodingKeys: String, CodingKey {
            case bid, label
            case positionMs = "position_ms"
            case createdAt = "created_at"
            case createdByUid = "created_by_uid"
        }
    }

    public struct WatchSource: Decodable, Identifiable {
        public var wsid: String
        public var title: String
        /// "upload" | "url"
        public var kind: String
        public var url: String
        public var posterUrl: String?
        public var sizeBytes: Int?
        public var authorUid: String
        public var authorNickname: String
        public var createdAt: Date
        public var lastPositionMs: Int?
        public var lastViewedAt: Date?
        public var bookmarks: [WatchBookmark]

        public var id: String { wsid }

        enum CodingKeys: String, CodingKey {
            case wsid, title, kind, url, bookmarks
            case posterUrl = "poster_url"
            case sizeBytes = "size_bytes"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case createdAt = "created_at"
            case lastPositionMs = "last_position_ms"
            case lastViewedAt = "last_viewed_at"
        }
    }

    public struct WatchSourceList: Decodable {
        public var items: [WatchSource]
        public var total: Int
    }

    public struct WatchSourceCreate: Encodable {
        public var title: String
        public var url: String
        public var posterUrl: String?

        public init(title: String, url: String, posterUrl: String? = nil) {
            self.title = title
            self.url = url
            self.posterUrl = posterUrl
        }

        enum CodingKeys: String, CodingKey {
            case title, url
            case posterUrl = "poster_url"
        }
    }

    public struct WatchPartner: Decodable {
        public var userUid: String
        public var nickname: String
        public var online: Bool

        enum CodingKeys: String, CodingKey {
            case nickname, online
            case userUid = "user_uid"
        }
    }

    public struct WatchCurrent: Decodable {
        public var sourceWsid: String?
        public var sourceUrl: String?
        public var sourceTitle: String?
        public var sourceKind: String?
        public var paused: Bool
        public var positionMs: Int
        public var rate: Double
        public var startedBy: String?
        public var eventSeq: Int?
        public var serverTsMs: Int?

        enum CodingKeys: String, CodingKey {
            case paused, rate
            case sourceWsid = "source_wsid"
            case sourceUrl = "source_url"
            case sourceTitle = "source_title"
            case sourceKind = "source_kind"
            case positionMs = "position_ms"
            case startedBy = "started_by"
            case eventSeq = "event_seq"
            case serverTsMs = "server_ts_ms"
        }
    }

    public struct WatchState: Decodable {
        public var current: WatchCurrent?
        public var partners: [WatchPartner]
    }
}
