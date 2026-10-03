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

/// The latest love-days/nickname context mirrored by the watch app into the
/// watch-side app-group container, so the WidgetKit complications — a
/// separate process with no connectivity of its own — can render the day
/// count between phone syncs.
public struct WatchLoveSnapshot: Codable, Equatable, Sendable {
    /// App-group container shared between the watch app and its widget
    /// extension. Must match the entitlements in both watch targets.
    public static let appGroupID = "group.com.lovejournal.watchshared"
    static let storageKey = "love.watch.daysSnapshot"

    public let days: Int
    public let selfNickname: String
    public let partnerNickname: String
    public let updatedAt: Date

    public init(days: Int, selfNickname: String, partnerNickname: String, updatedAt: Date) {
        self.days = days
        self.selfNickname = selfNickname
        self.partnerNickname = partnerNickname
        self.updatedAt = updatedAt
    }

    // MARK: - App-group persistence

    public static func load(suiteName: String = appGroupID) -> WatchLoveSnapshot? {
        guard let defaults = UserDefaults(suiteName: suiteName),
              let data = defaults.data(forKey: storageKey) else { return nil }
        return try? decoder.decode(WatchLoveSnapshot.self, from: data)
    }

    public func save(suiteName: String = WatchLoveSnapshot.appGroupID) {
        guard let defaults = UserDefaults(suiteName: suiteName),
              let data = try? WatchLoveSnapshot.encoder.encode(self) else { return }
        defaults.set(data, forKey: WatchLoveSnapshot.storageKey)
    }

    private static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()

    private static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()
}
