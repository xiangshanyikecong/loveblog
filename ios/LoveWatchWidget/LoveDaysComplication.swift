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

import SwiftUI
import WidgetKit

import LoveCore

@main
struct LoveWatchDaysWidgetBundle: WidgetBundle {
    var body: some Widget {
        LoveDaysComplication()
    }
}

struct LoveDaysComplicationEntry: TimelineEntry {
    let date: Date
    let snapshot: WatchLoveSnapshot?
}

struct LoveDaysComplicationProvider: TimelineProvider {
    func placeholder(in context: Context) -> LoveDaysComplicationEntry {
        LoveDaysComplicationEntry(
            date: .now,
            snapshot: WatchLoveSnapshot(
                days: 520,
                selfNickname: "",
                partnerNickname: "",
                updatedAt: .now
            )
        )
    }

    func getSnapshot(in context: Context, completion: @escaping (LoveDaysComplicationEntry) -> Void) {
        completion(current())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<LoveDaysComplicationEntry>) -> Void) {
        let entry = current()
        // The day count flips at local midnight; refresh just past it. The
        // watch app rewrites the snapshot (and reloads timelines) whenever
        // the phone pushes a fresher context.
        let calendar = Calendar.current
        let boundary = calendar.nextDate(
            after: entry.date,
            matching: DateComponents(hour: 0, minute: 1),
            matchingPolicy: .nextTime
        ) ?? entry.date.addingTimeInterval(3_600)
        let flip = LoveDaysComplicationEntry(date: boundary, snapshot: entry.snapshot)
        completion(
            Timeline(entries: [entry, flip], policy: .after(boundary.addingTimeInterval(120)))
        )
    }

    private func current() -> LoveDaysComplicationEntry {
        LoveDaysComplicationEntry(date: .now, snapshot: WatchLoveSnapshot.load())
    }
}

struct LoveDaysComplicationView: View {
    @Environment(\.widgetFamily) private var family
    let entry: LoveDaysComplicationEntry

    var body: some View {
        Group {
            if let snapshot = entry.snapshot {
                switch family {
                case .accessoryRectangular:
                    rectangular(snapshot)
                case .accessoryInline:
                    inline(snapshot)
                default:
                    circular(snapshot)
                }
            } else {
                Image(systemName: "heart")
                    .font(.title3)
                    .widgetAccentable()
            }
        }
        .containerBackground(for: .widget) { Color.clear }
    }

    private var daysText: Text {
        Text("\(snapshotDays)")
    }

    private var snapshotDays: Int {
        entry.snapshot?.days ?? 0
    }

    private func circular(_ snapshot: WatchLoveSnapshot) -> some View {
        VStack(spacing: 0) {
            daysText
                .font(.system(.title3, design: .rounded).weight(.bold))
                .widgetAccentable()
                .minimumScaleFactor(0.6)
                .lineLimit(1)
            Text("watchwidget.days.unit")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .widgetAccentable()
        }
    }

    private func rectangular(_ snapshot: WatchLoveSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            HStack(spacing: 3) {
                Image(systemName: "heart.fill")
                    .font(.caption2)
                    .widgetAccentable()
                Text("watchwidget.title")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.secondary)
            }
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                daysText
                    .font(.system(.title2, design: .rounded).weight(.bold))
                    .widgetAccentable()
                    .minimumScaleFactor(0.5)
                    .lineLimit(1)
                Text("watchwidget.days.unit")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            if !snapshot.partnerNickname.isEmpty, !snapshot.selfNickname.isEmpty {
                Text(verbatim: "\(snapshot.selfNickname) & \(snapshot.partnerNickname)")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }

    private func inline(_ snapshot: WatchLoveSnapshot) -> some View {
        Text("watchwidget.inline \(snapshot.days)")
            .widgetAccentable()
    }
}

struct LoveDaysComplication: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "LoveWatchDaysWidget", provider: LoveDaysComplicationProvider()) { entry in
            LoveDaysComplicationView(entry: entry)
        }
        .configurationDisplayName(String(localized: "watchwidget.name"))
        .description(String(localized: "watchwidget.description"))
        .supportedFamilies([.accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}
