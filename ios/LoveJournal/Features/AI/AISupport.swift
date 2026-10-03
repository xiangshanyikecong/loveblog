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

import LoveCore

/// Loads `GET /ai/status` once and answers per-feature visibility. The
/// status endpoint itself always succeeds when the session is valid; any
/// transport failure simply hides the AI entries (they are optional chrome).
@MainActor
@Observable
final class AIStatusModel {
    private(set) var status: AIDTOs.Status?
    private var loaded = false

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func loadIfNeeded() async {
        guard !loaded else { return }
        loaded = true
        status = try? await api.aiStatus()
    }

    func supports(_ feature: String) -> Bool {
        status?.supports(feature) ?? false
    }
}

/// Maps an AI-endpoint failure to a user-presentable message: the contract
/// reserves 503 for "no AI configured on this instance", which deserves its
/// own dedicated copy instead of a raw HTTP error.
enum AIFeature {
    static func message(for error: Error) -> String {
        if let apiError = error as? APIError, case .http(let status, _) = apiError, status == 503 {
            return String(localized: "ai.unavailable")
        }
        return (error as? APIError)?.message ?? String(localized: "ai.unavailable")
    }
}
