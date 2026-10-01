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

import Foundation
import Observation

import LoveCore

/// Owns the login lifecycle: session restore on launch, login/logout, and
/// reacting to remote session revocation.
///
/// The server has no refresh token — a JWT embeds a `session_version` that
/// any revoking action (logout, password change, device wipe) invalidates.
/// Whatever the cause, the outcome is the same: clear local state and show
/// the login screen. Per the Android lesson, a session-expiry handler must
/// never call the server's logout endpoint itself (401 recursion).
@MainActor
@Observable
final class SessionStore {
    enum State {
        case restoring
        case loggedOut
        case loggedIn(AuthDTOs.UserProfile)
    }

    private(set) var state: State = .restoring

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    /// Launch restore: rehydrate the Keychain cookie into the working cookie
    /// store, then verify it is still valid with `GET /auth/me`.
    func restoreSession() async {
        guard ServerSettings.isConfigured else {
            state = .loggedOut
            return
        }
        let account = ServerSettings.apiBase
        if let cookies = KeychainStore.loadSession(account: account) {
            cookies.forEach { HTTPCookieStorage.shared.setCookie($0) }
        }
        do {
            let profile = try await api.request(AuthDTOs.UserProfile.self, "GET", "/auth/me")
            state = .loggedIn(profile)
        } catch {
            // Invalid (401) or unverifiable (transport) session: start from a
            // clean logged-out state. Offline-first caching arrives in M6.
            clearLocalSession()
            state = .loggedOut
        }
    }

    /// Called after a successful login round-trip (cookie now lives in
    /// `HTTPCookieStorage`).
    func handleLoginSuccess(profile: AuthDTOs.UserProfile) {
        persistSessionCookies()
        state = .loggedIn(profile)
    }

    /// Fired by `LoveAPIClient` when any request proves the session is gone.
    func markSessionExpired() {
        guard state != .loggedOut else { return }
        clearLocalSession()
        state = .loggedOut
    }

    func logout() async {
        // Best effort: even a failed network call must clear local state, or
        // the app would come back logged in.
        try? await api.requestVoid("POST", "/auth/logout")
        clearLocalSession()
        state = .loggedOut
    }

    // MARK: - Private

    private func persistSessionCookies() {
        guard let url = URL(string: ServerSettings.apiBase) else { return }
        let cookies = HTTPCookieStorage.shared.cookies(for: url) ?? []
        KeychainStore.saveSession(cookies, account: ServerSettings.apiBase)
    }

    private func clearLocalSession() {
        ServerSettings.clearCookies()
        KeychainStore.deleteSession(account: ServerSettings.apiBase)
    }
}
