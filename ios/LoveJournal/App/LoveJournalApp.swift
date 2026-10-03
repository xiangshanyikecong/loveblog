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

/// Composition root: wires the API client and the session store together and
/// publishes them to the view tree.
@MainActor
@Observable
final class AppEnvironment {
    let api: LoveAPIClient
    let session: SessionStore
    let outbox: OutboxSyncer

    init() {
        api = LoveAPIClient(baseURLProvider: { ServerSettings.apiBase })
        session = SessionStore(api: api)
        outbox = OutboxSyncer(api: api)
        api.onSessionExpired = { [weak session] in
            Task { @MainActor in session?.markSessionExpired() }
        }
    }
}

@main
struct LoveJournalApp: App {
    @State private var environment = AppEnvironment()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(environment)
                .task { await environment.session.restoreSession() }
        }
    }
}

struct RootView: View {
    @Environment(AppEnvironment.self) private var environment

    var body: some View {
        switch environment.session.state {
        case .restoring:
            LaunchPlaceholderView()
        case .loggedOut:
            LoginView()
        case .loggedIn:
            MainTabView()
                // Entering the main UI means a (fresh) session: replay
                // anything the previous session left queued offline.
                .onAppear { environment.outbox.drainIfNeeded() }
        }
    }
}

/// Brand splash shown while the launch-time session restore is in flight.
struct LaunchPlaceholderView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "heart.fill")
                .font(.system(size: 44, weight: .semibold))
                .foregroundStyle(LoveTheme.gradient)
            Text("session.restoring")
                .font(.footnote)
                .foregroundStyle(LoveTheme.secondaryText)
        }
        .loveScreenBackground()
    }
}
