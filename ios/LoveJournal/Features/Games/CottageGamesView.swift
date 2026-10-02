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

// MARK: - Game catalog

/// Shared game metadata for the hub grid, board screens and stats sections.
enum GameCatalog {
    /// Server-accepted EMOTE whitelist for the five board games.
    static let emotes = ["❤️", "😘", "😝", "👍", "🤝", "😭", "🎉", "🤔"]

    static let boardGames = ["gomoku", "tictactoe", "reversi", "memory", "linklink"]

    /// Games aggregated by the match-history screen (draw has its own REST prefix).
    static let statsGames = ["gomoku", "tictactoe", "reversi", "memory", "linklink", "draw"]

    static func emoji(_ game: String) -> String {
        switch game {
        case "gomoku": return "⚫️"
        case "tictactoe": return "❌"
        case "reversi": return "🔵"
        case "memory": return "🃏"
        case "linklink": return "🧩"
        case "draw": return "🖌️"
        case "canvas": return "🎨"
        default: return "🎮"
        }
    }

    static func titleKey(_ game: String) -> LocalizedStringKey {
        switch game {
        case "gomoku": return "m5a.game.gomoku"
        case "tictactoe": return "m5a.game.tictactoe"
        case "reversi": return "m5a.game.reversi"
        case "memory": return "m5a.game.memory"
        case "linklink": return "m5a.game.linklink"
        case "draw": return "m5a.games.draw"
        case "canvas": return "m5a.games.canvas"
        default: return "m5a.games.title"
        }
    }

    static func subtitleKey(_ game: String) -> LocalizedStringKey {
        switch game {
        case "gomoku": return "m5a.game.gomoku.sub"
        case "tictactoe": return "m5a.game.tictactoe.sub"
        case "reversi": return "m5a.game.reversi.sub"
        case "memory": return "m5a.game.memory.sub"
        case "linklink": return "m5a.game.linklink.sub"
        case "draw": return "m5a.games.draw.sub"
        case "canvas": return "m5a.games.canvas.sub"
        default: return "m5a.games.subtitle"
        }
    }
}

/// Game lobby: the five shared-protocol board games plus the draw/canvas
/// realtime modules and the shared match-history entry.
struct CottageGamesView: View {
    private let columns = [
        GridItem(.flexible(), spacing: 12),
        GridItem(.flexible(), spacing: 12),
    ]

    var body: some View {
        ScrollView {
            LazyVGrid(columns: columns, spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("m5a.games.title")
                        .font(.title3.weight(.bold))
                        .foregroundStyle(LoveTheme.text)
                    Text("m5a.games.subtitle")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                .gridCellColumns(2)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.bottom, 4)

                ForEach(GameCatalog.boardGames, id: \.self) { game in
                    NavigationLink {
                        GameBoardScreen(game: game)
                    } label: {
                        tile(
                            emoji: GameCatalog.emoji(game),
                            titleKey: GameCatalog.titleKey(game),
                            subtitleKey: GameCatalog.subtitleKey(game)
                        )
                    }
                    .buttonStyle(.plain)
                }

                NavigationLink(value: CottageRoute.draw) {
                    tile(
                        emoji: GameCatalog.emoji("draw"),
                        titleKey: GameCatalog.titleKey("draw"),
                        subtitleKey: GameCatalog.subtitleKey("draw")
                    )
                }
                .buttonStyle(.plain)

                NavigationLink(value: CottageRoute.canvas) {
                    tile(
                        emoji: GameCatalog.emoji("canvas"),
                        titleKey: GameCatalog.titleKey("canvas"),
                        subtitleKey: GameCatalog.subtitleKey("canvas")
                    )
                }
                .buttonStyle(.plain)

                NavigationLink(value: CottageRoute.gameStats) {
                    tile(
                        emoji: "🏆",
                        titleKey: "m5a.games.stats",
                        subtitleKey: "m5a.games.stats.sub"
                    )
                }
                .buttonStyle(.plain)
            }
            .padding(16)
        }
        .loveScreenBackground()
        .navigationTitle("m5a.games.title")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func tile(
        emoji: String,
        titleKey: LocalizedStringKey,
        subtitleKey: LocalizedStringKey
    ) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(emoji)
                        .font(.title2)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                Text(titleKey)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                Text(subtitleKey)
                    .font(.caption)
                    .foregroundStyle(LoveTheme.secondaryText)
            }
        }
    }
}
