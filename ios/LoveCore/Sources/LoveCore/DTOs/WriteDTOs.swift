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

/// M2 write-path contracts: uploads, capsules, content versions and the
/// optimistic-concurrency payload shapes for articles/albums.
public enum WriteDTOs {
    // MARK: - Uploads (`POST /v1/uploads/*`)

    public struct UploadResult: Decodable {
        /// Server-relative path (`/uploads/...`) — resolve via mediaBase.
        public var url: String
        public var thumbnailUrl: String?
        public var fileName: String
        public var contentType: String
        public var size: Int

        enum CodingKeys: String, CodingKey {
            case url, size
            case thumbnailUrl = "thumbnail_url"
            case fileName = "file_name"
            case contentType = "content_type"
        }
    }

    // MARK: - Capsules (`/v1/capsules`)

    public struct Capsule: Decodable, Identifiable {
        public var uuid: String
        /// Sealed (not yet open): always null, even for the author.
        public var content: String?
        public var openAt: Date
        public var createdAt: Date
        public var authorUid: String
        public var authorNickname: String
        public var isOpen: Bool
        public var hasMedia: Bool
        /// "audio" | "video"; null when hasMedia == false.
        public var mediaType: String?
        public var mediaDurationSec: Int?
        /// Only returned once isOpen && hasMedia.
        public var mediaUrl: String?

        public var id: String { uuid }

        enum CodingKeys: String, CodingKey {
            case uuid, content, hasMedia, mediaType, mediaUrl
            case openAt = "open_at"
            case createdAt = "created_at"
            case authorUid = "author_uid"
            case authorNickname = "author_nickname"
            case isOpen = "is_open"
            case mediaDurationSec = "media_duration_sec"
        }
    }

    public struct CapsuleCreate: Encodable {
        public var content: String?
        public var openAt: Date
        public var mediaUrl: String?
        public var mediaType: String?
        public var mediaDurationSec: Int?

        public init(content: String?, openAt: Date) {
            self.content = content
            self.openAt = openAt
        }

        enum CodingKeys: String, CodingKey {
            case content
            case openAt = "open_at"
            case mediaUrl = "media_url"
            case mediaType = "media_type"
            case mediaDurationSec = "media_duration_sec"
        }
    }

    // MARK: - Content versions (`/v1/articles/{aid}/versions`)

    public struct ContentVersion: Decodable, Identifiable {
        public var vid: String
        /// "article" | "message"
        public var contentType: String
        public var contentId: String
        public var version: Int
        public var title: String?
        /// Arbitrary JSON object; stored as the raw dictionary.
        public var snapshot: [String: AnyCodable]?
        public var note: String?
        public var actorUid: String?
        public var actorNickname: String?
        public var createdAt: Date

        public var id: String { vid }

        enum CodingKeys: String, CodingKey {
            case vid, version, title, snapshot, note
            case contentType = "content_type"
            case contentId = "content_id"
            case actorUid = "actor_uid"
            case actorNickname = "actor_nickname"
            case createdAt = "created_at"
        }
    }

    public struct ContentVersionList: Decodable {
        public var items: [ContentVersion]
        public var total: Int
    }

    // MARK: - Article write bodies

    public struct ArticleBlockInput: Encodable {
        public var blockType: String
        public var content: String
        public var sortOrder: Int

        public init(blockType: String, content: String, sortOrder: Int) {
            self.blockType = blockType
            self.content = content
            self.sortOrder = sortOrder
        }

        enum CodingKeys: String, CodingKey {
            case content
            case blockType = "block_type"
            case sortOrder = "sort_order"
        }
    }

    /// `POST /v1/articles` and full-replacement `PUT /v1/articles/{aid}`.
    public struct ArticleUpsert: Encodable {
        public var title: String
        public var excerpt: String?
        public var status: String
        public var isEncrypted: Bool
        public var isCoCreated: Bool
        public var partnerCanEdit: Bool
        public var visibility: String
        public var coverUrl: String?
        public var tags: [String]
        public var blocks: [ArticleBlockInput]

        public init(
            title: String,
            excerpt: String? = nil,
            status: String = "Draft",
            visibility: String = "public",
            coverUrl: String? = nil,
            tags: [String] = [],
            blocks: [ArticleBlockInput] = [],
            isEncrypted: Bool = false,
            isCoCreated: Bool = false,
            partnerCanEdit: Bool = false
        ) {
            self.title = title
            self.excerpt = excerpt
            self.status = status
            self.isEncrypted = isEncrypted
            self.isCoCreated = isCoCreated
            self.partnerCanEdit = partnerCanEdit
            self.visibility = visibility
            self.coverUrl = coverUrl
            self.tags = tags
            self.blocks = blocks
        }

        enum CodingKeys: String, CodingKey {
            case title, excerpt, status, visibility, coverUrl, tags, blocks
            case isEncrypted = "is_encrypted"
            case isCoCreated = "is_co_created"
            case partnerCanEdit = "partner_can_edit"
        }
    }

    // MARK: - Album write body (create + full-replacement PUT)

    public struct AlbumMediaInput: Encodable {
        public var mediaType: String
        public var fileUrl: String
        public var thumbnailUrl: String?
        public var fileSize: Int?
        public var mimeType: String?
        public var isEncrypted: Bool

        public init(
            mediaType: String = "Image",
            fileUrl: String,
            thumbnailUrl: String? = nil,
            fileSize: Int? = nil,
            mimeType: String? = nil,
            isEncrypted: Bool = false
        ) {
            self.mediaType = mediaType
            self.fileUrl = fileUrl
            self.thumbnailUrl = thumbnailUrl
            self.fileSize = fileSize
            self.mimeType = mimeType
            self.isEncrypted = isEncrypted
        }

        enum CodingKeys: String, CodingKey {
            case fileUrl, fileSize
            case mediaType = "media_type"
            case thumbnailUrl = "thumbnail_url"
            case mimeType = "mime_type"
            case isEncrypted = "is_encrypted"
        }
    }

    public struct AlbumUpsert: Encodable {
        public var title: String
        public var description: String?
        public var coverUrl: String?
        public var isEncrypted: Bool
        public var isPublic: Bool
        public var visibility: String
        public var tags: [String]
        public var mediaItems: [AlbumMediaInput]

        public init(
            title: String,
            description: String? = nil,
            coverUrl: String? = nil,
            visibility: String = "public",
            tags: [String] = [],
            mediaItems: [AlbumMediaInput] = [],
            isEncrypted: Bool = false,
            isPublic: Bool = true
        ) {
            self.title = title
            self.description = description
            self.coverUrl = coverUrl
            self.isEncrypted = isEncrypted
            self.isPublic = isPublic
            self.visibility = visibility
            self.tags = tags
            self.mediaItems = mediaItems
        }

        enum CodingKeys: String, CodingKey {
            case title, description, visibility, tags
            case coverUrl = "cover_url"
            case isEncrypted = "is_encrypted"
            case isPublic = "is_public"
            case mediaItems = "media_items"
        }
    }

    // MARK: - Comments (create)

    public struct CommentCreate: Encodable {
        public var content: String
        public var parentCid: String?

        public init(content: String, parentCid: String? = nil) {
            self.content = content
            self.parentCid = parentCid
        }

        enum CodingKeys: String, CodingKey {
            case content
            case parentCid = "parent_cid"
        }
    }
}

/// Minimal JSON value wrapper so version snapshots can decode as a dictionary.
public enum AnyCodable: Decodable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case null

    public var stringValue: String? {
        if case .string(let value) = self { return value }
        return nil
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else {
            self = .null
        }
    }
}
