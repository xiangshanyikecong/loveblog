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

/// Bottom tab scaffold mirroring the Android client's six sections. The
/// feature screens land in milestones M1–M6; every tab renders a branded
/// placeholder until then.
struct MainTabView: View {
    var body: some View {
        TabView {
            PlaceholderView(titleKey: "tab.dashboard", systemImage: "house.fill", milestone: "M1")
                .tabItem { Label("tab.dashboard", systemImage: "house.fill") }

            PlaceholderView(titleKey: "tab.events", systemImage: "calendar", milestone: "M1")
                .tabItem { Label("tab.events", systemImage: "calendar") }

            PlaceholderView(titleKey: "tab.articles", systemImage: "doc.text.fill", milestone: "M1")
                .tabItem { Label("tab.articles", systemImage: "doc.text.fill") }

            PlaceholderView(titleKey: "tab.albums", systemImage: "photo.on.rectangle", milestone: "M1")
                .tabItem { Label("tab.albums", systemImage: "photo.on.rectangle") }

            PlaceholderView(titleKey: "tab.cottage", systemImage: "leaf.fill", milestone: "M3")
                .tabItem { Label("tab.cottage", systemImage: "leaf.fill") }

            PlaceholderView(titleKey: "tab.messages", systemImage: "bubble.left.and.bubble.right.fill", milestone: "M1")
                .tabItem { Label("tab.messages", systemImage: "bubble.left.and.bubble.right.fill") }
        }
        .tint(LoveTheme.primaryAccessible)
    }
}

/// Signed-in session menu available on every tab: shows the active server
/// and provides the only logout entry point (mirrors Android's settings
/// entry, simplified until the settings screens exist).
struct SessionMenu: View {
    @Environment(AppEnvironment.self) private var environment

    var body: some View {
        Menu {
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
            Image(systemName: "person.crop.circle")
        }
    }
}

/// Branded placeholder for features landing in later milestones.
struct PlaceholderView: View {
    let titleKey: LocalizedStringKey
    let systemImage: String
    let milestone: String

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveEmptyState(
                    systemImage: systemImage,
                    titleKey: titleKey,
                    messageKey: "placeholder.note \(milestone)"
                )
                .padding(.top, 80)
            }
            .loveScreenBackground()
            .navigationTitle(titleKey)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    SessionMenu()
                }
            }
        }
    }
}
