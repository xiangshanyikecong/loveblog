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

/// M1 read-model contracts: dashboard, articles, albums, events, messages,
/// timeline moments, search and notifications (`/v1/*`), mirroring
/// `server/app/schemas/*.py`. Decoding is tolerant: unknown fields are
/// ignored, optional fields never fail the decode.
///
/// Contract notes baked into the types:
/// - Two visibility vocabularies exist: content (article/album) uses lowercase
///   snake values, event/moment use capitalized values, search results use a
///   third `VisibilityLevel` set — all kept as plain `String` to stay
///   forward-compatible.
/// - Encrypted album media may answer `file_url: ""` (empty, not null) when
///   the viewer lacks permission — render an encrypted placeholder instead.
/// - datetimes arrive as ISO-8601 with `+00:00` (not `Z`) and may lack
///   fractional seconds; the shared decoder handles all forms.
public enum ContentDTOs {
    // MARK: - Shared envelope

    /// `{items, total}` pagination envelope used by articles/albums/events/
    /// messages. `total` is the full match count (except messages incremental
    /// mode where it equals `items.count`).
    public struct Page<T: Decodable>: Decodable {
        public var items: [T]
        public var total: Int

        public init(items: [T], total: Int) {
            self.items = items
            self.total = total
        }
    }

    // MARK: - Dashboard (`GET /v1/dashboard`)

    public struct LoveClock: Decodable, Equatable {
        public var days: Int
        public var hours: Int
        public var minutes: Int
        public var seconds: Int

        public init(days: Int, hours: Int, minutes: Int, seconds: Int) {
            self.days = days
            self.hours = hours
            self.minutes = minutes
            self.seconds = seconds
        }
    }

    public struct DashboardStats: Decodable, Equatable {
        public var articleCount: Int
        public var albumCount: Int
        public var eventCount: Int
        public var messageCount: Int

        enum CodingKeys: String, CodingKey {
            case articleCount = "article_count"
            case albumCount = "album_count"
            case eventCount = "event_count"
            case messageCount = "message_count"
        }
    }

    public struct CoupleMember: Decodable, Equatable {
        public var role: String?
        public var nickname: String?
        public var avatar: String?
    }

    public struct CoupleInfo: Decodable, Equatable {
        public var partnerA: CoupleMember?
        public var partnerB: CoupleMember?

        enum CodingKeys: String, CodingKey {
            case partnerA = "partner_a"
            case partnerB = "partner_b"
        }
    }

    public struct Dashboard: Decodable {
        public var loveClock: LoveClock
        public var stats: DashboardStats
        public var couple: CoupleInfo
        public var recentEvents: [Event]
        public var latestArticles: [ArticleSummary]
        public var latestAlbums: [AlbumSummary]
        public var latestMessages: [Message]

        enum CodingKeys: String, CodingKey {
            case loveClock = "love_clock"
            case stats, couple
            case recentEvents = "recent_events"
            case latestArticles = "latest_articles"
            case latestAlbums = "latest_albums"
            case latestMessages = "latest_messages"
        }
    }

    /// `GET /v1/memories/on-this-day?date=` (dates are plain strings).
    public struct OnThisDay: Decodable {
        public var date: String
        public var years: [YearGroup]
        public var totals: Totals

        public struct YearGroup: Decodable, Identifiable {
            public var year: Int
            public var articles: [ArticleItem]
            public var albums: [AlbumItem]
            public var songs: [SongItem]
            public var totals: Totals

            public var id: Int { year }
        }

        public struct ArticleItem: Decodable, Identifiable {
            public var aid: String
            public var title: String
            public var excerpt: String?
            public var createdAt: String

            public var id: String { aid }

            enum CodingKeys: String, CodingKey {
                case aid, title, excerpt
                case createdAt = "created_at"
            }
        }

        public struct AlbumItem: Decodable, Identifiable {
            public var albId: String
            public var title: String
            public var coverUrl: String?
            public var createdAt: String

            public var id: String { albId }

            enum CodingKeys: String, CodingKey {
                case title
                case albId = "alb_id"
                case coverUrl = "cover_url"
                case createdAt = "created_at"
            }
        }

        public struct SongItem: Decodable, Identifiable {
            public var songId: String
            public var name: String
            public var artists: [String]
            public var coverUrl: String?
            public var playedAt: String

            public var id: String { songId }

            enum CodingKeys: String, CodingKey {
                case name, artists
                case songId = "song_id"
                case coverUrl = "cover_url"
                case playedAt = "played_at"
            }
        }

        public struct Totals: Decodable, Equatable {
            public var articles: Int
            public var albums: Int
            public var songs: Int
        }
    }

    // MARK: - Events (`/v1/events`)

    public struct Event: Decodable, Identifiable, Equatable {
        public var eid: String
        public var title: String
        /// `YYYY-MM-DD`.
        public var date: String
        /// `"Countdown"` | `"Anniversary"`.
        public var type: String
        public var creatorUid: String
        public var creatorNickname: String
        public var isImportant: Bool
        public var isYearlyRepeat: Bool
        public var visibility: String
        public var tags: [String]
        /// Days until the next yearly occurrence; null for one-shot events.
        public var nextOccurrenceDays: Int?
        public var createdAt: Date

        public var id: String { eid }
        public var isAnniversary: Bool { type == "Anniversary" }

        enum CodingKeys: String, CodingKey {
            case eid, title, date, type, visibility, tags
            case creatorUid = "creator_uid"
            case creatorNickname = "creator_nickname"
            case isImportant = "is_important"
            case isYearlyRepeat = "is_yearly_repeat"
            case nextOccurrenceDays = "next_occurrence_days"
            case createdAt = "created_at"
        }
    }

    /// `POST /v1/events` / `PUT /v1/events/{eid}` body.
    public struct EventUpsert: Encodable {
        public var title: String
        public var date: String
        public var type: String
        public var isImportant: Bool
        public var isYearlyRepeat: Bool
        public var visibility: String
        public var tags: [String]

        public init(
            title: String,
            date: String,
            type: String,
            isImportant: Bool,
            isYearlyRepeat: Bool,
            visibility: String = "PartnersOnly",
            tags: [String] = []
        ) {
            self.title = title
            self.date = date
            self.type = type
            self.isImportant = isImportant
            self.isYearlyRepeat = isYearlyRepeat
            self.visibility = visibility
            self.tags = tags
        }

        enum CodingKeys: String, CodingKey {
            case title, date, type, visibility, tags
            case isImportant = "is_important"
            case isYearlyRepeat = "is_yearly_repeat"
        }
    }

    // MARK: - Comments (shared by article/album/moment)

    public struct CommentNode: Decodable, Identifiable {
        public var cid: String
        public var parentCid: String?
        public var content: String
        public var authorUid: String
        public var authorNickname: String
        public var mentionUids: [String]
        public var createdAt: Date
        public var replies: [CommentNode]

        public var id: String { cid }

        enum CodingKeys: String, CodingKey {
            case cid, content, replies
            case parentCid = "parent_cid"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case mentionUids = "mention_uids"
            case createdAt = "created_at"
        }
    }

    // MARK: - Articles (`/v1/articles`)

    public struct ArticleSummary: Decodable, Identifiable {
        public var aid: String
        public var title: String
        public var excerpt: String?
        /// `"Draft"` | `"Published"`.
        public var status: String
        public var isEncrypted: Bool
        public var isCoCreated: Bool
        public var partnerCanEdit: Bool
        public var visibility: String
        public var requiresPassword: Bool
        public var tags: [String]
        public var version: Int
        public var authorUid: String
        public var authorNickname: String
        public var publishedAt: Date?
        public var createdAt: Date
        public var collaboratorUids: [String]

        public var id: String { aid }
        public var isPublished: Bool { status == "Published" }

        enum CodingKeys: String, CodingKey {
            case aid, title, excerpt, status, visibility, tags, version
            case isEncrypted = "is_encrypted"
            case isCoCreated = "is_co_created"
            case partnerCanEdit = "partner_can_edit"
            case requiresPassword = "requires_password"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case publishedAt = "published_at"
            case createdAt = "created_at"
            case collaboratorUids = "collaborator_uids"
        }
    }

    public struct ArticleBlock: Decodable, Identifiable {
        public var bid: String
        /// `"Heading" | "Paragraph" | "Quote" | "Image"`.
        public var blockType: String
        public var content: String
        public var sortOrder: Int
        public var authorUid: String
        public var authorNickname: String

        public var id: String { bid }
        public var isHeading: Bool { blockType == "Heading" }
        public var isQuote: Bool { blockType == "Quote" }

        enum CodingKeys: String, CodingKey {
            case bid, content
            case blockType = "block_type"
            case sortOrder = "sort_order"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
        }
    }

    /// `GET /v1/articles/{aid}` — summary fields plus blocks and comments.
    public struct ArticleDetail: Decodable, Identifiable {
        public var aid: String
        public var title: String
        public var excerpt: String?
        public var status: String
        public var isEncrypted: Bool
        public var isCoCreated: Bool
        public var partnerCanEdit: Bool
        public var visibility: String
        public var requiresPassword: Bool
        public var tags: [String]
        public var version: Int
        public var authorUid: String
        public var authorNickname: String
        public var publishedAt: Date?
        public var createdAt: Date
        public var collaboratorUids: [String]
        public var blocks: [ArticleBlock]
        public var comments: [CommentNode]

        public var id: String { aid }
        public var isPublished: Bool { status == "Published" }
        public var sortedBlocks: [ArticleBlock] { blocks.sorted { $0.sortOrder < $1.sortOrder } }

        enum CodingKeys: String, CodingKey {
            case aid, title, excerpt, status, visibility, tags, version, blocks, comments
            case isEncrypted = "is_encrypted"
            case isCoCreated = "is_co_created"
            case partnerCanEdit = "partner_can_edit"
            case requiresPassword = "requires_password"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case publishedAt = "published_at"
            case createdAt = "created_at"
            case collaboratorUids = "collaborator_uids"
        }
    }

    // MARK: - Albums (`/v1/albums`)

    public struct AlbumSummary: Decodable, Identifiable {
        public var albId: String
        public var title: String
        public var description: String?
        public var coverUrl: String?
        public var isEncrypted: Bool
        public var isPublic: Bool
        public var visibility: String
        public var requiresPassword: Bool
        public var tags: [String]
        public var authorUid: String
        public var authorNickname: String
        public var mediaCount: Int
        public var createdAt: Date

        public var id: String { albId }

        enum CodingKeys: String, CodingKey {
            case title, description, visibility, tags
            case albId = "alb_id"
            case coverUrl = "cover_url"
            case isEncrypted = "is_encrypted"
            case isPublic = "is_public"
            case requiresPassword = "requires_password"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case mediaCount = "media_count"
            case createdAt = "created_at"
        }
    }

    public struct AlbumMedia: Decodable, Identifiable {
        public var mediaId: String
        /// `"Image"` | `"Video"`.
        public var mediaType: String
        /// Empty string (not null) when the viewer lacks decryption permission.
        public var fileUrl: String
        public var thumbnailUrl: String?
        public var fileSize: Int?
        public var mimeType: String?
        public var isEncrypted: Bool

        public var id: String { mediaId }
        public var isVideo: Bool { mediaType == "Video" }
        public var isLocked: Bool { isEncrypted && fileUrl.isEmpty }

        enum CodingKeys: String, CodingKey {
            case fileSize
            case mediaId = "media_id"
            case mediaType = "media_type"
            case fileUrl = "file_url"
            case thumbnailUrl = "thumbnail_url"
            case mimeType = "mime_type"
            case isEncrypted = "is_encrypted"
        }
    }

    public struct AlbumDetail: Decodable, Identifiable {
        public var albId: String
        public var title: String
        public var description: String?
        public var coverUrl: String?
        public var isEncrypted: Bool
        public var isPublic: Bool
        public var visibility: String
        public var requiresPassword: Bool
        public var tags: [String]
        public var authorUid: String
        public var authorNickname: String
        public var mediaCount: Int
        public var createdAt: Date
        public var mediaItems: [AlbumMedia]
        public var comments: [CommentNode]

        public var id: String { albId }

        enum CodingKeys: String, CodingKey {
            case title, description, visibility, tags, comments
            case albId = "alb_id"
            case coverUrl = "cover_url"
            case isEncrypted = "is_encrypted"
            case isPublic = "is_public"
            case requiresPassword = "requires_password"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case mediaCount = "media_count"
            case createdAt = "created_at"
            case mediaItems = "media_items"
        }
    }

    // MARK: - Messages (`/v1/messages`)

    public struct Message: Decodable, Identifiable, Equatable {
        public var msgId: String
        public var content: String
        public var isPublic: Bool
        public var tags: [String]
        public var isDeleted: Bool
        public var version: Int
        public var createdAt: Date
        public var updatedAt: Date
        public var authorUid: String?
        public var authorNickname: String?
        public var visitorName: String?

        public var id: String { msgId }
        public var displayAuthor: String { authorNickname ?? visitorName ?? "" }

        enum CodingKeys: String, CodingKey {
            case content, tags, version
            case msgId = "msg_id"
            case isPublic = "is_public"
            case isDeleted = "is_deleted"
            case createdAt = "created_at"
            case updatedAt = "updated_at"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case visitorName = "visitor_name"
        }
    }

    /// `POST /v1/messages` body (server rejects extra fields).
    public struct MessageCreate: Encodable {
        public var content: String
        public var isPublic: Bool
        public var tags: [String]

        public init(content: String, isPublic: Bool, tags: [String] = []) {
            self.content = content
            self.isPublic = isPublic
            self.tags = tags
        }

        enum CodingKeys: String, CodingKey {
            case content, tags
            case isPublic = "is_public"
        }
    }

    /// `PATCH /v1/messages/{msg_id}` body — only changed fields are sent.
    public struct MessagePatch: Encodable {
        public var content: String?
        public var isPublic: Bool?

        public init(content: String? = nil, isPublic: Bool? = nil) {
            self.content = content
            self.isPublic = isPublic
        }

        enum CodingKeys: String, CodingKey {
            case content
            case isPublic = "is_public"
        }
    }

    // MARK: - Timeline moments (`/v1/timeline`)

    public struct Moment: Decodable, Identifiable {
        public var mid: String
        public var authorUid: String
        public var authorNickname: String
        public var content: String
        public var mediaUrls: [String]
        public var audioUrl: String?
        public var audioDurationSec: Int?
        public var location: String?
        /// `"Public" | "PartnersOnly" | "Encrypted"`.
        public var visibility: String
        public var tags: [String]
        public var timestamp: Date
        public var comments: [CommentNode]

        public var id: String { mid }
        public var commentCount: Int {
            comments.reduce(0) { $0 + 1 + $1.replies.count }
        }

        enum CodingKeys: String, CodingKey {
            case mid, content, visibility, tags, comments
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case mediaUrls = "media_urls"
            case audioUrl = "audio_url"
            case audioDurationSec = "audio_duration_sec"
            case location, timestamp
        }
    }

    public struct TimelineList: Decodable {
        public var items: [Moment]
        public var page: Int
        public var pageSize: Int
        public var total: Int
        public var hasNext: Bool
        public var sort: String

        enum CodingKeys: String, CodingKey {
            case items, page, total, sort
            case pageSize = "page_size"
            case hasNext = "has_next"
        }
    }

    /// `POST /v1/timeline` body (M1: text-only moments; media arrives in M2).
    public struct MomentCreate: Encodable {
        public var content: String
        public var mediaUrls: [String]
        public var visibility: String

        public init(content: String, mediaUrls: [String] = [], visibility: String = "PartnersOnly") {
            self.content = content
            self.mediaUrls = mediaUrls
            self.visibility = visibility
        }

        enum CodingKeys: String, CodingKey {
            case content, visibility
            case mediaUrls = "media_urls"
        }
    }

    // MARK: - Search (`GET /v1/search`)

    public struct SearchResultItem: Decodable, Identifiable {
        /// `"article" | "album" | "event" | "moment" | "message"`.
        public var type: String
        public var id: String
        public var title: String
        public var snippet: String
        public var url: String
        public var date: Date
        public var tags: [String]
        public var visibility: String
        public var isEncrypted: Bool
        public var authorNickname: String?

        public init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            type = try container.decode(String.self, forKey: .type)
            id = try container.decode(String.self, forKey: .id)
            title = try container.decode(String.self, forKey: .title)
            snippet = try container.decode(String.self, forKey: .snippet)
            url = try container.decode(String.self, forKey: .url)
            date = try container.decode(Date.self, forKey: .date)
            tags = try container.decodeIfPresent([String].self, forKey: .tags) ?? []
            visibility = try container.decodeIfPresent(String.self, forKey: .visibility) ?? "Public"
            isEncrypted = try container.decodeIfPresent(Bool.self, forKey: .isEncrypted) ?? false
            authorNickname = try container.decodeIfPresent(String.self, forKey: .authorNickname)
        }

        enum CodingKeys: String, CodingKey {
            case type, id, title, snippet, url, date, tags, visibility, authorNickname
            case isEncrypted = "is_encrypted"
        }
    }

    public struct SearchResponse: Decodable {
        public var items: [SearchResultItem]
        public var total: Int
        public var page: Int
        public var pageSize: Int

        enum CodingKeys: String, CodingKey {
            case items, total, page
            case pageSize = "page_size"
        }
    }

    // MARK: - Notifications (`/v1/notifications`)

    public struct AppNotification: Decodable, Identifiable, Equatable {
        public var nid: String
        public var type: String
        public var title: String
        public var body: String?
        public var link: String?
        public var sourceType: String?
        public var sourceId: String?
        public var isRead: Bool
        public var createdAt: Date
        public var readAt: Date?

        public var id: String { nid }

        enum CodingKeys: String, CodingKey {
            case nid, type, title, body, link
            case sourceType = "source_type"
            case sourceId = "source_id"
            case isRead = "is_read"
            case createdAt = "created_at"
            case readAt = "read_at"
        }
    }

    public struct NotificationList: Decodable {
        public var items: [AppNotification]
        /// Count of items returned in this response (truncated to `limit`).
        public var total: Int
        public var unreadCount: Int

        enum CodingKeys: String, CodingKey {
            case items, total
            case unreadCount = "unread_count"
        }
    }
}
