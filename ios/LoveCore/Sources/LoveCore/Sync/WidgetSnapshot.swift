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

/// The love-days count mirrored into the app-group container so the home
/// screen widget — a separate process without its own session — can render
/// without talking to the server.
///
/// The app writes the wall-clock seconds observed at the last dashboard
/// fetch plus the fetch timestamp; readers re-derive the current value from
/// `now`, so the widget stays correct across midnights without another
/// server round-trip.
public struct WidgetSnapshot: Codable, Equatable, Sendable {
    /// App-group container shared between the app and the widget extension.
    /// Must match the entitlements in both targets.
    public static let appGroupID = "group.com.lovejournal.shared"
    static let storageKey = "love.widget.daysSnapshot"

    /// Total seconds together at `fetchedAt`.
    public let baseSeconds: Int
    public let fetchedAt: Date

    public init(baseSeconds: Int, fetchedAt: Date) {
        self.baseSeconds = baseSeconds
        self.fetchedAt = fetchedAt
    }

    public func seconds(at now: Date) -> Int {
        max(0, baseSeconds + Int(now.timeIntervalSince(fetchedAt)))
    }

    public func days(at now: Date) -> Int {
        seconds(at: now) / 86_400
    }

    /// (days, hours, minutes) at `now`, for the medium widget detail line.
    public func components(at now: Date) -> (days: Int, hours: Int, minutes: Int) {
        let total = seconds(at: now)
        return (total / 86_400, (total % 86_400) / 3_600, (total % 3_600) / 60)
    }

    // MARK: - App-group persistence

    public static func load(suiteName: String = appGroupID) -> WidgetSnapshot? {
        guard let defaults = UserDefaults(suiteName: suiteName),
              let data = defaults.data(forKey: storageKey) else { return nil }
        return try? decoder.decode(WidgetSnapshot.self, from: data)
    }

    public func save(suiteName: String = WidgetSnapshot.appGroupID) {
        guard let defaults = UserDefaults(suiteName: suiteName),
              let data = try? WidgetSnapshot.encoder.encode(self) else { return }
        defaults.set(data, forKey: WidgetSnapshot.storageKey)
    }

    /// Seconds from `now` until `days(at:)` increments. Day boundaries fall on
    /// the anniversary time-of-day of the couple's start date (the same
    /// instant the server's love clock flips), which is a fixed offset from
    /// `baseSeconds` — not necessarily local midnight. Drives the widget
    /// timeline refresh.
    public func secondsUntilDayBoundary(at now: Date) -> TimeInterval {
        let remainder = seconds(at: now) % 86_400
        if remainder == 0 { return 86_400 }
        return TimeInterval(86_400 - remainder)
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
