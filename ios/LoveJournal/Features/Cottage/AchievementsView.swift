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

import Observation
import SwiftUI

import LoveCore

@MainActor
@Observable
final class AchievementsViewModel {
    private(set) var loading = true
    private(set) var achievements: AchievementDTOs.Achievements?
    var error: String?

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        if achievements == nil { loading = true }
        do {
            achievements = try await api.achievements()
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? String(localized: "cottage.error.generic")
        }
        loading = false
    }
}

/// `GET /cottage/achievements` — couple level card, badge grid and the
/// aggregate stat summary behind them.
struct AchievementsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: AchievementsViewModel?

    private let badgeColumns = [
        GridItem(.flexible(), spacing: 10),
        GridItem(.flexible(), spacing: 10),
        GridItem(.flexible(), spacing: 10),
    ]

    /// Ordered stat rows (server keys → localized labels), mirroring the
    /// server's `achievements.py` stats dict.
    private static let statKeys = [
        "love_days", "articles", "albums", "album_media", "moments", "capsules",
        "checkins", "checkin_streak_days", "moods", "mood_streak_days",
        "chat_messages", "games_played", "wishes_total", "wishes_completed", "songs_played",
    ]

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("achievements.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = AchievementsViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: AchievementsViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let error = model.error, model.achievements == nil {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if let achievements = model.achievements {
                    levelCard(achievements.level)
                    statsCard(achievements.stats)
                    badgesSection(achievements.badges)
                } else if model.loading {
                    LoveLoadingView()
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
    }

    // MARK: Level

    private func levelCard(_ level: AchievementDTOs.CoupleLevel) -> some View {
        VStack(spacing: 10) {
            HStack(spacing: 8) {
                Label("achievements.level.section", systemImage: "sparkles")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white.opacity(0.9))
                Spacer()
                Text(verbatim: "Lv.\(level.level)")
                    .font(.headline.weight(.bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 3)
                    .background(.white.opacity(0.2), in: Capsule())
            }
            Text(level.title)
                .font(.system(size: 34, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
            Text("achievements.points \(level.points)")
                .font(.footnote)
                .foregroundStyle(.white.opacity(0.9))
            // Progress to the next level (full bar at max level).
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(.white.opacity(0.25))
                    Capsule()
                        .fill(.white.opacity(0.9))
                        .frame(width: max(6, geo.size.width * CGFloat(level.progressPercent) / 100))
                }
            }
            .frame(height: 8)
            if let nextTitle = level.nextLevelTitle, let nextPoints = level.nextLevelPoints {
                Text("achievements.next.level \(nextPoints - level.points) \(nextTitle)")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.85))
            } else {
                Text("achievements.max.level")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.85))
            }
        }
        .padding(18)
        .frame(maxWidth: .infinity)
        .background(LoveTheme.gradient, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .shadow(color: LoveTheme.rose.opacity(0.3), radius: 10, y: 4)
    }

    // MARK: Stats summary

    private func statsCard(_ stats: [String: Int]) -> some View {
        let columns = Array(repeating: GridItem(.flexible(), spacing: 10), count: 3)
        return LoveSoftCard {
            LoveSectionTitle(textKey: "achievements.stats.section")
            LazyVGrid(columns: columns, spacing: 14) {
                ForEach(Self.statKeys, id: \.self) { key in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(verbatim: "\(stats[key] ?? 0)")
                            .font(.title3.weight(.bold))
                            .foregroundStyle(LoveTheme.primaryAccessible)
                        Text(LocalizedStringKey("achievements.stat.\(key)"))
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    // MARK: Badges

    private func badgesSection(_ badges: [AchievementDTOs.BadgeProgress]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            LoveSectionTitle(textKey: "achievements.badges.section")
            LazyVGrid(columns: badgeColumns, spacing: 10) {
                ForEach(badges) { badge in
                    badgeCell(badge)
                }
            }
        }
    }

    private func badgeCell(_ badge: AchievementDTOs.BadgeProgress) -> some View {
        let tint = BadgeTint.color(for: badge.tier)
        return VStack(spacing: 6) {
            Text(verbatim: badge.icon)
                .font(.title2)
                .opacity(badge.achieved ? 1 : 0.4)
                .scaleEffect(badge.achieved ? 1 : 0.85)
            Text(badge.name)
                .font(.caption.weight(.semibold))
                .foregroundStyle(badge.achieved ? LoveTheme.text : LoveTheme.secondaryText)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            if badge.achieved {
                LovePill(text: BadgeTint.label(for: badge.tier), tint: tint)
            } else if let next = badge.nextTarget, next > 0 {
                Text("achievements.badge.progress \(badge.current) \(next)")
                    .font(.caption2)
                    .foregroundStyle(LoveTheme.secondaryText)
            } else {
                Text(verbatim: "—")
                    .font(.caption2)
                    .foregroundStyle(LoveTheme.secondaryText)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .padding(.horizontal, 4)
        .background(LoveTheme.background.opacity(badge.achieved ? 0.6 : 0.35))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(badge.achieved ? tint.opacity(0.45) : LoveTheme.outline, lineWidth: 1)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(badge.name)，\(badge.description)")
        .accessibilityHint(badge.achieved ? BadgeTint.label(for: badge.tier) : "")
    }
}

/// Tier colors: gold/silver/bronze plus the greyed-out locked look. Mirrors
/// the Android achievements palette (kept local: only used here).
private enum BadgeTint {
    static let gold = Color(red: 0.85, green: 0.65, blue: 0.20)
    static let silver = Color(red: 0.62, green: 0.65, blue: 0.70)
    static let bronze = Color(red: 0.78, green: 0.52, blue: 0.35)

    static func color(for tier: String) -> Color {
        switch tier {
        case "gold": gold
        case "silver": silver
        case "bronze": bronze
        default: LoveTheme.secondaryText
        }
    }

    static func label(for tier: String) -> String {
        switch tier {
        case "gold": String(localized: "achievements.tier.gold")
        case "silver": String(localized: "achievements.tier.silver")
        case "bronze": String(localized: "achievements.tier.bronze")
        default: String(localized: "achievements.tier.none")
        }
    }
}
