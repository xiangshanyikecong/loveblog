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

import LoveCore

/// Runtime-configurable backend address, persisted to UserDefaults so each
/// couple can point the app at their own self-hosted node without rebuilding.
///
/// The normalization rules live in LoveCore's `ServerAddress` (shared with the
/// Android port); this type only owns persistence, cookie hygiene and URL
/// derivation. Static accessors are deliberate: `LoveAPIClient` reads the
/// base URL from arbitrary executors and UserDefaults is thread-safe.
enum ServerSettings {
    static let apiBaseDefaultsKey = "love.server.apiBase"

    /// Full API base without trailing slash, e.g. `https://demo.com/api/v1`
    /// or `http://192.168.1.10:8000/v1`.
    static var apiBase: String {
        UserDefaults.standard.string(forKey: apiBaseDefaultsKey) ?? ""
    }

    static var isConfigured: Bool { !apiBase.isEmpty }

    /// Value shown in the login field (origin, no `/v1` suffix).
    static var displayAddress: String {
        ServerAddress.stripApiVersion(apiBase)
    }

    /// Applies a new address. When the normalized address actually changes,
    /// cookies are cleared first: cookies are domain-based and ignore ports
    /// and path prefixes, so carrying them across a server switch could send
    /// one node's session to another node on the same host.
    @discardableResult
    static func setAddress(_ raw: String) -> String {
        let normalized = ServerAddress.normalize(raw)
        let previous = apiBase
        if !normalized.isEmpty && normalized != previous {
            clearCookies()
        }
        UserDefaults.standard.set(normalized, forKey: apiBaseDefaultsKey)
        return normalized
    }

    /// Validates user input before login. Returns an error message or nil.
    /// Debug builds may reach private-network HTTP; release is HTTPS-only
    /// (same policy as the Android client).
    static func validateInput(_ raw: String) -> String? {
        ServerAddress.validateAddressInput(raw, allowCleartext: allowCleartext)
    }

    static var allowCleartext: Bool {
        #if DEBUG
        true
        #else
        false
        #endif
    }

    /// Base for health checks, e.g. `https://demo.com/api`.
    static var healthBase: String { ServerAddress.stripApiVersion(apiBase) }

    /// Origin used to fetch uploaded media, e.g. `https://demo.com`.
    static var mediaBase: String { ServerAddress.stripMediaApiPrefix(apiBase) }

    /// Resolves a server-relative media path (`/uploads/x.jpg`) to an
    /// absolute URL. Server responses may add fields/paths freely — absolute
    /// http(s) URLs pass through untouched.
    static func mediaURL(_ path: String?) -> URL? {
        guard let path, !path.isEmpty else { return nil }
        if path.hasPrefix("http://") || path.hasPrefix("https://") {
            return URL(string: path)
        }
        let suffix = path.hasPrefix("/") ? path : "/" + path
        return URL(string: mediaBase + suffix)
    }

    static func clearCookies() {
        HTTPCookieStorage.shared.cookies?.forEach { HTTPCookieStorage.shared.deleteCookie($0) }
    }
}
