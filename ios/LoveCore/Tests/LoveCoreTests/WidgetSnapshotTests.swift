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
import Testing

@testable import LoveCore

@Suite("WidgetSnapshot")
struct WidgetSnapshotTests {
    private func date(_ string: String, calendar: Calendar = .current) -> Date {
        let formatter = DateFormatter()
        formatter.calendar = calendar
        formatter.timeZone = calendar.timeZone
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return formatter.date(from: string)!
    }

    @Test("days and components advance with elapsed time")
    func arithmetic() {
        let fetchedAt = date("2026-10-01 08:00:00")
        // 123 days + 4h 5m at fetch time.
        let snapshot = WidgetSnapshot(baseSeconds: 123 * 86_400 + 4 * 3_600 + 5 * 60, fetchedAt: fetchedAt)

        let now = date("2026-10-03 08:00:00")
        #expect(snapshot.days(at: now) == 125)
        #expect(snapshot.seconds(at: now) == 125 * 86_400 + 4 * 3_600 + 5 * 60)

        let parts = snapshot.components(at: now)
        #expect(parts.days == 125)
        #expect(parts.hours == 4)
        #expect(parts.minutes == 5)
    }

    @Test("seconds never go negative when now precedes the fetch")
    func clamped() {
        let fetchedAt = date("2026-10-03 12:00:00")
        let snapshot = WidgetSnapshot(baseSeconds: 10, fetchedAt: fetchedAt)
        #expect(snapshot.seconds(at: date("2026-10-03 11:00:00")) == 0)
        #expect(snapshot.days(at: date("2026-10-03 11:00:00")) == 0)
    }

    @Test("day count flips exactly at the anniversary boundary")
    func boundaryFlip() {
        // 99 whole days + 82_859s of the current day → boundary in 3_541s.
        let fetchedAt = date("2026-10-01 23:00:00")
        let snapshot = WidgetSnapshot(baseSeconds: 99 * 86_400 + 82_859, fetchedAt: fetchedAt)

        #expect(snapshot.days(at: fetchedAt) == 99)
        #expect(snapshot.secondsUntilDayBoundary(at: fetchedAt) == 3_541)

        let justBefore = fetchedAt.addingTimeInterval(3_540)
        let justAfter = fetchedAt.addingTimeInterval(3_541)
        #expect(snapshot.days(at: justBefore) == 99)
        #expect(snapshot.days(at: justAfter) == 100)
        #expect(snapshot.secondsUntilDayBoundary(at: justAfter) == 86_400)
    }

    @Test("boundary math when exactly on a whole day")
    func wholeDayBoundary() {
        let fetchedAt = date("2026-10-01 08:00:00")
        let snapshot = WidgetSnapshot(baseSeconds: 50 * 86_400, fetchedAt: fetchedAt)
        #expect(snapshot.days(at: fetchedAt) == 50)
        #expect(snapshot.secondsUntilDayBoundary(at: fetchedAt) == 86_400)
    }

    @Test("save/load roundtrips through the app-group defaults")
    func roundtrip() {
        let suite = "love.tests.widget-\(UUID().uuidString)"
        defer { UserDefaults().removePersistentDomain(forName: suite) }

        let snapshot = WidgetSnapshot(baseSeconds: 1_000, fetchedAt: date("2026-10-01 00:00:00"))
        snapshot.save(suiteName: suite)

        let loaded = WidgetSnapshot.load(suiteName: suite)
        #expect(loaded == snapshot)
    }

    @Test("load returns nil for an empty suite")
    func emptySuite() {
        let suite = "love.tests.widget-empty-\(UUID().uuidString)"
        defer { UserDefaults().removePersistentDomain(forName: suite) }
        #expect(WidgetSnapshot.load(suiteName: suite) == nil)
    }
}
