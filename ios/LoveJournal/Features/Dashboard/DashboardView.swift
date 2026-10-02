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

import Observation
import SwiftUI

import LoveCore

@MainActor
@Observable
final class DashboardViewModel {
    var loading = true
    var error: String?
    var dashboard: ContentDTOs.Dashboard?
    var onThisDay: ContentDTOs.OnThisDay?

    private let api: LoveAPIClient
    /// Wall-clock seconds captured at fetch; the ticking card advances from it.
    private var clockBaseSeconds = 0
    private var clockFetchedAt = Date()

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        if dashboard == nil { loading = true }
        do {
            let data = try await api.request(ContentDTOs.Dashboard.self, "GET", "/dashboard")
            dashboard = data
            error = nil
            clockBaseSeconds = clockSeconds(data.loveClock)
            clockFetchedAt = Date()
            // On-this-day is best effort: failures just hide the card.
            onThisDay = try? await api.request(
                ContentDTOs.OnThisDay.self, "GET", "/memories/on-this-day"
            )
        } catch {
            self.error = (error as? APIError)?.message ?? "加载失败，请稍后重试"
        }
        loading = false
    }

    /// Ticking love clock: server snapshot advanced locally each second.
    func clock(at now: Date) -> ContentDTOs.LoveClock {
        let elapsed = max(0, Int(now.timeIntervalSince(clockFetchedAt)))
        let total = clockBaseSeconds + elapsed
        return ContentDTOs.LoveClock(
            days: total / 86_400,
            hours: (total % 86_400) / 3_600,
            minutes: (total % 3_600) / 60,
            seconds: total % 60
        )
    }

    private func clockSeconds(_ clock: ContentDTOs.LoveClock) -> Int {
        ((clock.days * 24 + clock.hours) * 60 + clock.minutes) * 60 + clock.seconds
    }
}

struct DashboardView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: DashboardViewModel?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("tab.dashboard")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = DashboardViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: DashboardViewModel) -> some View {
        ScrollView {
            VStack(spacing: 16) {
                if let error = model.error, model.dashboard == nil {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if let dashboard = model.dashboard {
                    header
                    clockCard(model)
                    statsCard(dashboard.stats)
                    if let memories = model.onThisDay, !memories.years.isEmpty {
                        onThisDayCard(memories)
                    }
                    recentEventsSection(dashboard.recentEvents)
                } else if model.loading {
                    LoveLoadingView()
                }
            }
            .padding(16)
        }
        .scrollDismissesKeyboard(.interactively)
        .refreshable { await model.refresh() }
    }

    private var header: some View {
        VStack(spacing: 6) {
            Text("dashboard.welcome")
                .font(.title2.bold())
                .foregroundStyle(LoveTheme.text)
            Text("dashboard.welcome.subtitle")
                .font(.footnote)
                .foregroundStyle(LoveTheme.secondaryText)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 8)
    }

    private func clockCard(_ model: DashboardViewModel) -> some View {
        TimelineView(.periodic(from: .now, by: 1)) { context in
            let clock = model.clock(at: context.date)
            VStack(spacing: 10) {
                Label("dashboard.clock.title", systemImage: "heart.fill")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white.opacity(0.9))
                Text("\(clock.days)")
                    .font(.system(size: 52, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)
                + Text(" ")
                + Text("dashboard.clock.days")
                    .font(.headline)
                    .foregroundStyle(.white.opacity(0.9))
                Text(String(
                    format: "%02d:%02d:%02d", clock.hours, clock.minutes, clock.seconds
                ))
                .font(.system(.title3, design: .monospaced))
                .foregroundStyle(.white.opacity(0.85))
                .padding(.horizontal, 14)
                .padding(.vertical, 4)
                .background(.white.opacity(0.18), in: Capsule())
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 24)
            .background(LoveTheme.gradient, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .shadow(color: LoveTheme.rose.opacity(0.3), radius: 10, y: 4)
        }
    }

    private func statsCard(_ stats: ContentDTOs.DashboardStats) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: "dashboard.stats.title")
            HStack(spacing: 8) {
                statPill("dashboard.stats.article", value: stats.articleCount)
                statPill("dashboard.stats.album", value: stats.albumCount)
                statPill("dashboard.stats.event", value: stats.eventCount)
                statPill("dashboard.stats.message", value: stats.messageCount)
            }
        }
    }

    private func statPill(_ titleKey: LocalizedStringKey, value: Int) -> some View {
        VStack(spacing: 4) {
            Text("\(value)")
                .font(.headline)
                .foregroundStyle(LoveTheme.primaryAccessible)
            Text(titleKey)
                .font(.caption2)
                .foregroundStyle(LoveTheme.secondaryText)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(LoveTheme.background.opacity(0.6), in: RoundedRectangle(cornerRadius: 14))
    }

    private func onThisDayCard(_ memories: ContentDTOs.OnThisDay) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: "dashboard.memories.title")
            ForEach(memories.years) { year in
                VStack(alignment: .leading, spacing: 6) {
                    Text("dashboard.memories.year \(year.year)")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.primaryAccessible)
                    ForEach(year.articles.prefix(2)) { article in
                        Text("dashboard.memories.article \(article.title)")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.text)
                            .lineLimit(1)
                    }
                    ForEach(year.albums.prefix(2)) { album in
                        Text("dashboard.memories.album \(album.title)")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.text)
                            .lineLimit(1)
                    }
                    ForEach(year.songs.prefix(2)) { song in
                        Text("dashboard.memories.song \(song.name)")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.text)
                            .lineLimit(1)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 4)
            }
            Text("dashboard.memories.total \(memories.totals.articles) \(memories.totals.albums) \(memories.totals.songs)")
                .font(.caption2)
                .foregroundStyle(LoveTheme.secondaryText)
                .padding(.top, 4)
        }
    }

    private func recentEventsSection(_ events: [ContentDTOs.Event]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            LoveSectionTitle(textKey: "dashboard.events.title")
            if events.isEmpty {
                LoveEmptyState(
                    systemImage: "calendar.badge.heart",
                    titleKey: "dashboard.events.empty",
                    messageKey: "dashboard.events.empty.hint"
                )
            } else {
                ForEach(events) { event in
                    LoveSoftCard {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                HStack(spacing: 6) {
                                    Text(event.title)
                                        .font(.subheadline.weight(.semibold))
                                        .foregroundStyle(LoveTheme.text)
                                    if event.isImportant {
                                        Image(systemName: "star.fill")
                                            .font(.caption)
                                            .foregroundStyle(LoveTheme.peach)
                                    }
                                }
                                Text(event.date)
                                    .font(.caption)
                                    .foregroundStyle(LoveTheme.secondaryText)
                            }
                            Spacer()
                            if let days = event.nextOccurrenceDays {
                                LovePill(text: days == 0 ? String(localized: "event.days.today") : String(localized: "event.days.count \(days)"))
                            }
                        }
                    }
                }
            }
        }
    }
}
