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

import Foundation

/// "Tap / heartbeat" lightweight interactions (`/v1/cottage/taps`), mirroring
/// `server/app/schemas/cottage_tap.py`.
public enum TapDTOs {
    public struct Tap: Decodable, Identifiable, Equatable {
        public var tid: String
        /// "tap" | "heartbeat"
        public var kind: String
        public var fromUid: String
        public var fromNickname: String
        public var toUid: String
        public var toNickname: String
        public var createdAt: Date

        public var id: String { tid }
        public var isHeartbeat: Bool { kind == "heartbeat" }

        enum CodingKeys: String, CodingKey {
            case tid, kind
            case fromUid = "from_uid"
            case fromNickname = "from_nickname"
            case toUid = "to_uid"
            case toNickname = "to_nickname"
            case createdAt = "created_at"
        }
    }

    /// `POST /v1/cottage/taps`.
    public struct TapCreate: Encodable, Equatable {
        /// "tap" | "heartbeat"
        public var kind: String

        public init(kind: String) {
            self.kind = kind
        }
    }

    /// `GET /v1/cottage/taps/recent`.
    public struct TapList: Decodable {
        public var items: [Tap]
        /// How many taps are retained in total (rows are pruned beyond the cap).
        public var totalKept: Int

        enum CodingKeys: String, CodingKey {
            case items
            case totalKept = "total_kept"
        }
    }
}
