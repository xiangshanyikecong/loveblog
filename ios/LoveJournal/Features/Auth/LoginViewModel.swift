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

/// Login flow view model, ported from Android's `AuthViewModel`:
/// address validation → optional health probe → login (with TOTP retry) →
/// session-keep verification → bootstrap / password recovery side flows.
@MainActor
@Observable
final class LoginViewModel {
    // Login form
    var serverAddress = ""
    var username = ""
    var password = ""
    var totpCode = ""
    var showTOTPField = false

    // Flow state
    var loading = false
    var testingConnection = false
    var connectionOk: String?
    var error: String?
    var showBootstrapEntry = false
    var showBootstrapSheet = false
    var showRecoverySheet = false

    private let api: LoveAPIClient
    private let session: SessionStore
    /// The server address whose bootstrap status was last checked, so the
    /// public probe runs lazily and only once per address.
    private var bootstrapCheckedFor: String?

    init(api: LoveAPIClient, session: SessionStore) {
        self.api = api
        self.session = session
        serverAddress = ServerSettings.displayAddress
    }

    var isDebugBuild: Bool {
        #if DEBUG
        true
        #else
        false
        #endif
    }

    /// Mirrors server rules: 3-32 chars, lowercase letters/digits/underscore.
    private static let usernamePattern = "^[a-z0-9_]{3,32}$"

    // MARK: - Login

    func testConnection() async {
        if let message = ServerSettings.validateInput(serverAddress) {
            error = message
            connectionOk = nil
            return
        }
        testingConnection = true
        error = nil
        connectionOk = nil
        defer { testingConnection = false }
        do {
            let message = try await api.checkHealth(candidateAddress: serverAddress)
            ServerSettings.setAddress(serverAddress)
            connectionOk = message
            // The address is now effective; re-probe bootstrap status (the
            // old cache is keyed by the previous address).
            bootstrapCheckedFor = nil
            await checkBootstrapStatus()
        } catch {
            self.error = LoginFlow.presentableMessage(error)
        }
    }

    func login() async {
        if let message = ServerSettings.validateInput(serverAddress) {
            error = message
            return
        }
        if username.trimmingCharacters(in: .whitespaces).isEmpty || password.isEmpty {
            error = "请输入用户名和密码"
            return
        }
        loading = true
        error = nil
        defer { loading = false }

        ServerSettings.setAddress(serverAddress)
        let trimmedCode = totpCode.trimmingCharacters(in: .whitespaces)
        let request = AuthDTOs.LoginRequest(
            username: username.trimmingCharacters(in: .whitespaces),
            password: password,
            totpCode: trimmedCode.isEmpty ? nil : trimmedCode
        )

        do {
            _ = try await api.request(
                AuthDTOs.TokenResponse.self, "POST", "/auth/login", body: request
            )
        } catch {
            presentLoginError(error)
            return
        }

        // Login succeeded; verify the session actually stuck. A cookie that
        // vanishes between login and /auth/me means a reverse proxy or
        // COOKIE_SECURE mismatch — an otherwise confusing failure worth
        // explaining explicitly (ported from Android).
        do {
            let profile = try await api.request(AuthDTOs.UserProfile.self, "GET", "/auth/me")
            session.handleLoginSuccess(profile: profile)
        } catch {
            ServerSettings.clearCookies()
            if case APIError.http(401, _) = error {
                self.error = "登录成功但会话未保持。若使用 http 自部署，请确认服务端 COOKIE_SECURE 未强制开启，且反代未误传 X-Forwarded-Proto: https"
            } else {
                self.error = LoginFlow.presentableMessage(error)
            }
        }
    }

    private func presentLoginError(_ error: Error) {
        if case APIError.http(401, let detail) = error, detail == "totp_required" {
            showTOTPField = true
            self.error = LoginFlow.presentableMessage(LoginError.totpRequired)
            return
        }
        self.error = LoginFlow.presentableMessage(error)
    }

    // MARK: - Bootstrap status probe

    /// Lazily checks whether the site still needs first-time initialization.
    /// Only probes when the field matches the currently effective server, so
    /// requests never go to an unconfirmed candidate address.
    func checkBootstrapStatus() async {
        let address = serverAddress.trimmingCharacters(in: .whitespaces)
        let invalid = address.isEmpty ||
            ServerSettings.validateInput(address) != nil ||
            address != ServerSettings.displayAddress
        if invalid {
            bootstrapCheckedFor = address
            showBootstrapEntry = false
            return
        }
        guard bootstrapCheckedFor != address else { return }
        bootstrapCheckedFor = address
        do {
            let status = try await api.request(AuthDTOs.BootstrapStatus.self, "GET", "/auth/bootstrap-status")
            showBootstrapEntry = !status.bootstrapped
        } catch {
            showBootstrapEntry = false
        }
    }

    // MARK: - Bootstrap (first-time initialization)

    func submitBootstrap(
        token: String,
        username: String,
        password: String,
        nickname: String,
        siteName: String,
        startDate: Date?,
        dateEnabled: Bool
    ) async -> String? {
        var failure: String?
        if let message = ServerSettings.validateInput(serverAddress) {
            failure = message
        } else if token.trimmingCharacters(in: .whitespaces).isEmpty {
            failure = "请输入初始化令牌"
        } else if !Self.matchesUsernamePolicy(username) {
            failure = "用户名需为 3-32 位小写字母、数字或下划线"
        } else if !Self.validPassword(password) {
            failure = "密码至少 8 位，且需同时包含字母和数字"
        } else if nickname.trimmingCharacters(in: .whitespaces).isEmpty {
            failure = "请输入昵称"
        }
        if let failure {
            return failure
        }

        let isoStart: String?
        if dateEnabled, let startDate {
            var calendar = Calendar(identifier: .gregorian)
            calendar.timeZone = TimeZone(identifier: "UTC") ?? .current
            let components = calendar.dateComponents([.year, .month, .day], from: startDate)
            guard let dayStart = calendar.date(from: components) else {
                return "恋爱开始日格式应为 yyyy-MM-dd"
            }
            isoStart = Self.utcISOFormatter.string(from: dayStart)
        } else {
            isoStart = nil
        }

        ServerSettings.setAddress(serverAddress)
        let payload = AuthDTOs.BootstrapRegisterRequest(
            username: username.trimmingCharacters(in: .whitespaces),
            password: password,
            nickname: nickname.trimmingCharacters(in: .whitespaces),
            siteName: siteName.trimmingCharacters(in: .whitespaces).isEmpty
                ? nil
                : siteName.trimmingCharacters(in: .whitespaces),
            loveStartDate: isoStart
        )
        do {
            _ = try await api.request(
                AuthDTOs.UserProfile.self,
                "POST",
                "/auth/bootstrap",
                body: payload,
                headers: ["X-Bootstrap-Token": token.trimmingCharacters(in: .whitespaces)]
            )
            // The site is initialized now; the entry point disappears and the
            // login form is prefilled (no auto-login, matching Android).
            bootstrapCheckedFor = nil
            showBootstrapEntry = false
            showBootstrapSheet = false
            connectionOk = "初始化成功，请使用新账号登录"
            error = nil
            self.username = username.trimmingCharacters(in: .whitespaces)
            return nil
        } catch {
            return LoginFlow.presentableMessage(error)
        }
    }

    // MARK: - Password recovery (bootstrap-token authorized)

    func submitRecovery(username: String, newPassword: String, token: String) async -> String? {
        if let message = ServerSettings.validateInput(serverAddress) {
            return message
        }
        if username.trimmingCharacters(in: .whitespaces).isEmpty || token.trimmingCharacters(in: .whitespaces).isEmpty {
            return "请填写用户名与恢复令牌"
        }
        if !Self.validPassword(newPassword) {
            return "新密码至少 8 位，且需同时包含字母和数字"
        }
        ServerSettings.setAddress(serverAddress)
        let payload = AuthDTOs.PasswordRecoveryRequest(
            username: username.trimmingCharacters(in: .whitespaces),
            newPassword: newPassword
        )
        do {
            try await api.requestVoid(
                "POST",
                "/auth/password-recovery",
                body: payload,
                headers: ["X-Bootstrap-Token": token.trimmingCharacters(in: .whitespaces)]
            )
            showRecoverySheet = false
            return nil
        } catch {
            return LoginFlow.presentableMessage(error)
        }
    }

    // MARK: - Helpers

    private static func matchesUsernamePolicy(_ username: String) -> Bool {
        let trimmed = username.trimmingCharacters(in: .whitespaces)
        guard let regex = try? NSRegularExpression(pattern: usernamePattern) else { return false }
        let range = NSRange(trimmed.startIndex..., in: trimmed)
        return regex.firstMatch(in: trimmed, range: range) != nil
    }

    /// Mirrors server validation: ≥ 8 chars with both letters and digits.
    private static func validPassword(_ password: String) -> Bool {
        password.count >= 8 &&
            password.contains(where: \.isLetter) &&
            password.contains(where: \.isNumber)
    }

    private static let utcISOFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        return formatter
    }()
}
