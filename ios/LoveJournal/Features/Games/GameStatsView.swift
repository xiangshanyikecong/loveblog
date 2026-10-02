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

// MARK: - View model

/// Aggregates per-game match lists (the five board games + draw) — there is
/// no dedicated report endpoint, `GET /{game}/matches` carries it all.
@MainActor
@Observable
final class GameStatsViewModel {
    struct Section: Identifiable {
        let gameKey: String
        let list: GameDTOs.MatchList?
        var id: String { gameKey }
    }

    private(set) var loading = true
    private(set) var sections: [Section] = []
    var error: String?

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    var hasAnyMatch: Bool {
        sections.contains { !($0.list?.items.isEmpty ?? true) }
    }

    func refresh() async {
        if sections.isEmpty { loading = true }
        var collected: [Section] = []
        var firstError: String?
        for game in GameCatalog.statsGames {
            let path = game == "draw"
                ? "/cottage/draw/matches"
                : "/cottage/games/\(game)/matches"
            do {
                let list = try await api.request(
                    GameDTOs.MatchList.self, "GET", path,
                    query: [URLQueryItem(name: "limit", value: "20")]
                )
                collected.append(Section(gameKey: game, list: list))
            } catch {
                if firstError == nil {
                    firstError = (error as? APIError)?.message ?? String(localized: "m5a.error.generic")
                }
                collected.append(Section(gameKey: game, list: nil))
            }
        }
        sections = collected
        error = collected.allSatisfy { $0.list == nil } ? firstError : nil
        loading = false
    }
}

// MARK: - View

/// Match history across all M5 games: per-game wins, draws and the five
/// most recent matches.
struct GameStatsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: GameStatsViewModel?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("m5a.stats.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = GameStatsViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: GameStatsViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if model.loading {
                    LoveLoadingView()
                        .frame(height: 160)
                } else if let error = model.error, !model.hasAnyMatch {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if !model.hasAnyMatch {
                    LoveEmptyState(
                        systemImage: "trophy",
                        titleKey: "m5a.stats.empty",
                        messageKey: "m5a.stats.empty.hint"
                    )
                } else {
                    ForEach(model.sections) { section in
                        if let list = section.list, !list.items.isEmpty {
                            sectionCard(section.gameKey, list)
                        }
                    }
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
    }

    // MARK: Section card

    private func sectionCard(_ gameKey: String, _ list: GameDTOs.MatchList) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(GameCatalog.emoji(gameKey))
                        .font(.title3)
                    Text(GameCatalog.titleKey(gameKey))
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.text)
                    Spacer()
                    LovePill(
                        text: String(localized: "m5a.stats.total \(list.total)"),
                        tint: LoveTheme.lavender
                    )
                }
                HStack(spacing: 8) {
                    ForEach(list.stats) { stat in
                        HStack(spacing: 4) {
                            Text(stat.nickname)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(LoveTheme.text)
                            Text("m5a.stats.wins \(stat.wins)")
                                .font(.caption)
                                .foregroundStyle(LoveTheme.primaryAccessible)
                        }
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(LoveTheme.background.opacity(0.6), in: Capsule())
                    }
                    Text("m5a.stats.draws \(list.draws)")
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                Text("m5a.stats.recent")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(LoveTheme.secondaryText)
                ForEach(Array(list.items.prefix(5))) { match in
                    matchRow(match)
                }
            }
        }
    }

    private func matchRow(_ match: GameDTOs.GameMatch) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            if match.isDraw || match.winnerUid == nil {
                Text("m5a.stats.match.draw")
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(LoveTheme.secondaryText)
            } else {
                let winner = match.winnerUid == match.blackUid
                    ? match.blackNickname
                    : match.whiteNickname
                let loser = match.winnerUid == match.blackUid
                    ? match.whiteNickname
                    : match.blackNickname
                Text("m5a.stats.match.won \(winner ?? "") \(loser ?? "")")
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(LoveTheme.text)
            }
            HStack {
                if let reason = match.endReason {
                    LovePill(text: GameText.endReason(reason), tint: LoveTheme.peach)
                }
                Spacer()
                Text(Format.dateTime(match.createdAt))
                    .font(.caption2)
                    .foregroundStyle(LoveTheme.secondaryText)
            }
        }
        .padding(.vertical, 4)
    }
}
