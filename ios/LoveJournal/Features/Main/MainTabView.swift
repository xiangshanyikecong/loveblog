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

/// Secondary pages reachable from every tab's toolbar (mirrors Android's
/// MainRoute entries: search icon, bell icon, overflow menu).
enum MainRoute: Hashable {
    case search
    case notifications
    case timeline
    case capsules
    case settings
}

/// Cottage sub-pages reached from the cottage hub grid.
enum CottageRoute: Hashable {
    case chat
    case mood
    case checkin
    case wishes
    case questions
    case achievements
    case listen
    case watch
    case games
    case gameStats
    case draw
    case canvas
    case coupons
    case reminders
    case plans
    case ledger
    case reports
    case footprints
    case period
    case vault
    case privacy
    case security
    case recycleBin
    /// Message board — a hub card since iOS tab bars cap at five tabs.
    case boardMessages
}

/// Bottom tab scaffold. iOS tab bars cap at five items on iPhone — a sixth
/// tab silently collapses into UIKit's "More" list, whose nested navigation
/// controller stacks a second back button on top of SwiftUI's own. The
/// message board therefore lives as a cottage hub card (`boardMessages`).
struct MainTabView: View {
    var body: some View {
        TabView {
            RoutedScreen { DashboardView() }
                .tabItem { Label("tab.dashboard", systemImage: "house.fill") }

            RoutedScreen { EventsView() }
                .tabItem { Label("tab.events", systemImage: "calendar") }

            RoutedScreen { ArticlesView() }
                .tabItem { Label("tab.articles", systemImage: "doc.text.fill") }

            RoutedScreen { AlbumsView() }
                .tabItem { Label("tab.albums", systemImage: "photo.on.rectangle") }

            RoutedScreen { CottageHubView() }
                .tabItem { Label("tab.cottage", systemImage: "leaf.fill") }
        }
        .tint(LoveTheme.primaryAccessible)
    }
}

/// Per-tab navigation stack with the shared toolbar: search entry, bell
/// (notifications) and the overflow menu (timeline, capsules, server, logout).
private struct RoutedScreen<Content: View>: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var path = NavigationPath()
    @ViewBuilder var content: Content

    var body: some View {
        NavigationStack(path: $path) {
            content
                .navigationDestination(for: MainRoute.self) { route in
                    switch route {
                    case .search:
                        SearchView()
                    case .notifications:
                        NotificationsView()
                    case .timeline:
                        TimelineScreenView()
                    case .capsules:
                        CapsulesView()
                    case .settings:
                        SettingsView()
                    }
                }
                .navigationDestination(for: CottageRoute.self) { route in
                    switch route {
                    case .chat: CottageChatView()
                    case .mood: CottageMoodView()
                    case .checkin: CottageCheckInView()
                    case .wishes: CottageWishesView()
                    case .questions: CottageQuestionsView()
                    case .achievements: AchievementsView()
                    case .listen: CottageListenView()
                    case .watch: CottageWatchView()
                    case .games: CottageGamesView()
                    case .gameStats: GameStatsView()
                    case .draw: DrawGameView()
                    case .canvas: CanvasBoardView()
                    case .coupons: CouponsView()
                    case .reminders: RemindersView()
                    case .plans: PlansView()
                    case .ledger: LedgerView()
                    case .reports: ReportsView()
                    case .footprints: FootprintsView()
                    case .period: PeriodView()
                    case .vault: VaultView()
                    case .privacy: PrivacyCenterView()
                    case .security: SecurityCenterView()
                    case .recycleBin: RecycleBinView()
                    case .boardMessages: MessagesView()
                    }
                }
                .toolbar {
                    ToolbarItemGroup(placement: .topBarTrailing) {
                        NavigationLink(value: MainRoute.search) {
                            Image(systemName: "magnifyingglass")
                        }
                        NavigationLink(value: MainRoute.notifications) {
                            Image(systemName: "bell")
                        }
                        Menu {
                            Section {
                                Button {
                                    path.append(MainRoute.timeline)
                                } label: {
                                    Label("menu.timeline", systemImage: "clock.arrow.circlepath")
                                }
                                Button {
                                    path.append(MainRoute.capsules)
                                } label: {
                                    Label("menu.capsules", systemImage: "seal")
                                }
                                Button {
                                    path.append(MainRoute.settings)
                                } label: {
                                    Label("menu.settings", systemImage: "gearshape")
                                }
                            }
                            Section {
                                Label("menu.server \(ServerSettings.displayAddress)", systemImage: "server.rack")
                            }
                            Section {
                                Button(role: .destructive) {
                                    Task { await environment.session.logout() }
                                } label: {
                                    Label("menu.logout", systemImage: "rectangle.portrait.and.arrow.right")
                                }
                            }
                        } label: {
                            Image(systemName: "ellipsis.circle")
                        }
                    }
                }
        }
    }
}
