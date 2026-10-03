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

import SwiftUI
import WidgetKit

import LoveCore

@main
struct LoveDaysWidgetBundle: WidgetBundle {
    var body: some Widget {
        LoveDaysWidget()
    }
}

struct LoveDaysEntry: TimelineEntry {
    let date: Date
    let snapshot: WidgetSnapshot?
}

struct LoveDaysProvider: TimelineProvider {
    func placeholder(in context: Context) -> LoveDaysEntry {
        // Gallery/placeholder rendering: show plausible data.
        LoveDaysEntry(date: .now, snapshot: WidgetSnapshot(baseSeconds: 1_234 * 86_400, fetchedAt: .now))
    }

    func getSnapshot(in context: Context, completion: @escaping (LoveDaysEntry) -> Void) {
        completion(current())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<LoveDaysEntry>) -> Void) {
        let entry = current()
        guard let snapshot = entry.snapshot else {
            // No mirror yet (user never reached the dashboard in the app):
            // retry hourly until the app writes one.
            completion(Timeline(entries: [entry], policy: .after(.now.addingTimeInterval(3_600))))
            return
        }
        // The day count flips at the couple's anniversary time-of-day, not
        // local midnight; one entry now, one just past the boundary.
        let boundary = entry.date.addingTimeInterval(snapshot.secondsUntilDayBoundary(at: entry.date))
        let flip = LoveDaysEntry(date: boundary.addingTimeInterval(1), snapshot: snapshot)
        completion(
            Timeline(entries: [entry, flip], policy: .after(boundary.addingTimeInterval(120)))
        )
    }

    private func current() -> LoveDaysEntry {
        LoveDaysEntry(date: .now, snapshot: WidgetSnapshot.load())
    }
}

/// Brand tokens mirrored from the app's `LoveTheme` (the widget target does
/// not compile app sources; values must be kept in sync manually).
private enum WidgetTheme {
    static let rose = Color(red: 1.0, green: 0.361, blue: 0.541)
    static let peach = Color(red: 1.0, green: 0.604, blue: 0.463)
    static let gradient = LinearGradient(
        colors: [rose, peach],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
}

struct LoveDaysWidgetView: View {
    @Environment(\.widgetFamily) private var family
    let entry: LoveDaysEntry

    var body: some View {
        Group {
            if let snapshot = entry.snapshot {
                daysContent(snapshot)
            } else {
                placeholderContent
            }
        }
        .containerBackground(for: .widget) { WidgetTheme.gradient }
    }

    private var placeholderContent: some View {
        VStack(spacing: 8) {
            Image(systemName: "heart.fill")
                .font(.title2)
                .foregroundStyle(.white)
            Text("widget.placeholder")
                .font(.caption)
                .foregroundStyle(.white.opacity(0.9))
                .multilineTextAlignment(.center)
        }
        .padding(8)
    }

    @ViewBuilder
    private func daysContent(_ snapshot: WidgetSnapshot) -> some View {
        if family == .systemMedium {
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 2) {
                    header
                    counter(snapshot.days(at: entry.date))
                }
                Spacer()
                let parts = snapshot.components(at: entry.date)
                Text("widget.love.elapsed \(parts.days) \(parts.hours) \(parts.minutes)")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.white.opacity(0.92))
                    .multilineTextAlignment(.trailing)
            }
            .padding(6)
        } else {
            VStack(spacing: 2) {
                header
                counter(snapshot.days(at: entry.date))
            }
        }
    }

    private var header: some View {
        Label("widget.love.title", systemImage: "heart.fill")
            .font(.caption.weight(.semibold))
            .foregroundStyle(.white.opacity(0.9))
    }

    private func counter(_ days: Int) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 4) {
            Text("\(days)")
                .font(.system(size: 38, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
                .minimumScaleFactor(0.5)
                .lineLimit(1)
            Text("widget.love.days.unit")
                .font(.headline)
                .foregroundStyle(.white.opacity(0.9))
        }
    }
}

struct LoveDaysWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "LoveDaysWidget", provider: LoveDaysProvider()) { entry in
            LoveDaysWidgetView(entry: entry)
        }
        .configurationDisplayName(String(localized: "widget.love.name"))
        .description(String(localized: "widget.love.description"))
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
