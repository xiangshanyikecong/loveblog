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

/// Display formatting helpers (fixed patterns, matching the Android client's
/// ISO-prefix truncation style).
enum Format {
    private static let dateTimeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = .current
        return formatter
    }()

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = .current
        return formatter
    }()

    /// `2026-05-20 09:30`
    static func dateTime(_ date: Date) -> String {
        dateTimeFormatter.string(from: date)
    }

    /// `2026-05-20`
    static func date(_ date: Date) -> String {
        dateFormatter.string(from: date)
    }

    /// Today's date as `YYYY-MM-DD` (server query format).
    static func todayString() -> String {
        dateFormatter.string(from: Date())
    }

    /// `2 小时前` style relative time (cottage taps, activity rows).
    static func relative(_ date: Date, relativeTo now: Date = Date()) -> String {
        let seconds = now.timeIntervalSince(date)
        if seconds < 60 { return String(localized: "format.relative.now") }
        let minutes = Int(seconds / 60)
        if minutes < 60 { return String(localized: "format.relative.minutes \(minutes)") }
        let hours = minutes / 60
        if hours < 24 { return String(localized: "format.relative.hours \(hours)") }
        let days = hours / 24
        if days < 30 { return String(localized: "format.relative.days \(days)") }
        return Self.date(date)
    }
}
