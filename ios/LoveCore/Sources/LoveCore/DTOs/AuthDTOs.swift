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

/// Auth/session request and response contracts (`/v1/auth/*`), mirroring
/// `server/app/schemas/auth.py`. Every DTO decodes tolerantly: unknown
/// fields are ignored (the server may add fields at any time) and optional
/// fields never fail the decode.
public enum AuthDTOs {
    /// `POST /v1/auth/login`. `totpCode` accepts a 6-digit TOTP code or a
    /// one-time recovery code of the form `xxxx-xxxx`.
    public struct LoginRequest: Encodable {
        public var username: String
        public var password: String
        public var totpCode: String?

        public init(username: String, password: String, totpCode: String? = nil) {
            self.username = username
            self.password = password
            self.totpCode = totpCode
        }

        enum CodingKeys: String, CodingKey {
            case username, password
            case totpCode = "totp_code"
        }
    }

    /// Response body of `/auth/login`. **The `accessToken` field is a literal
    /// placeholder string (`"http-only"`), never a usable token** — the real
    /// JWT arrives via `Set-Cookie: access_token=...` and is handled by the
    /// cookie store.
    public struct TokenResponse: Decodable {
        public var accessToken: String?
        public var tokenType: String?
        public var expiresIn: Int?
        public var role: String?

        enum CodingKeys: String, CodingKey {
            case accessToken = "access_token"
            case tokenType = "token_type"
            case expiresIn = "expires_in"
            case role
        }
    }

    /// `GET /v1/auth/me` and `/v1/auth/bootstrap` responses.
    public struct UserProfile: Decodable, Equatable {
        public var uid: String
        public var username: String
        public var nickname: String
        public var avatar: String?
        public var role: String

        public init(uid: String, username: String, nickname: String, avatar: String?, role: String) {
            self.uid = uid
            self.username = username
            self.nickname = nickname
            self.avatar = avatar
            self.role = role
        }
    }

    /// `GET /v1/auth/bootstrap-status`.
    public struct BootstrapStatus: Decodable {
        public var bootstrapped: Bool
    }

    /// `POST /v1/auth/bootstrap` — creates Partner A plus site settings in one
    /// shot; requires the `X-Bootstrap-Token` header.
    public struct BootstrapRegisterRequest: Encodable {
        public var username: String
        public var password: String
        public var nickname: String
        public var role: String
        public var siteName: String?
        /// ISO-8601 datetime string, e.g. `2024-05-01T00:00:00Z`.
        public var loveStartDate: String?

        public init(
            username: String,
            password: String,
            nickname: String,
            role: String = "partner_a",
            siteName: String? = nil,
            loveStartDate: String? = nil
        ) {
            self.username = username
            self.password = password
            self.nickname = nickname
            self.role = role
            self.siteName = siteName
            self.loveStartDate = loveStartDate
        }

        enum CodingKeys: String, CodingKey {
            case username, password, nickname, role
            case siteName = "site_name"
            case loveStartDate = "love_start_date"
        }
    }

    /// `POST /v1/auth/register` — the logged-in partner creates the second
    /// partner account (one empty slot per role).
    public struct RegisterRequest: Encodable {
        public var username: String
        public var password: String
        public var nickname: String
        public var role: String

        public init(username: String, password: String, nickname: String, role: String) {
            self.username = username
            self.password = password
            self.nickname = nickname
            self.role = role
        }
    }

    /// `POST /v1/auth/password-recovery` — unauthenticated reset authorized by
    /// the `X-Bootstrap-Token` header.
    public struct PasswordRecoveryRequest: Encodable {
        public var username: String
        public var newPassword: String

        public init(username: String, newPassword: String) {
            self.username = username
            self.newPassword = newPassword
        }

        enum CodingKeys: String, CodingKey {
            case username
            case newPassword = "new_password"
        }
    }

    /// `GET /health` — public, used by the login screen's "test connection".
    public struct HealthResponse: Decodable {
        public var app: String?
        public var database: String?
        public var redis: String?
    }
}

/// Typed failures of the login flow, so the UI can react to the 2FA challenge
/// instead of just showing text.
public enum LoginError: Error, Equatable {
    /// The account has TOTP enabled — retry with a `totpCode`.
    case totpRequired
    /// A presentable failure message (validation, credentials, freeze, …).
    case message(String)
}

/// Login-specific status→message mapping, ported from Android
/// `AuthRepository.login`. Generic API errors fall back to `APIError.message`.
public enum LoginFlow {
    public static func presentableMessage(_ error: Error) -> String {
        if let loginError = error as? LoginError {
            switch loginError {
            case .totpRequired:
                return "该账号已启用两步验证，请输入 6 位验证码或恢复码"
            case .message(let text):
                return text
            }
        }
        if case APIError.http(let status, let detail) = error {
            switch status {
            case 401 where detail == "totp_required":
                return "该账号已启用两步验证，请输入 6 位验证码或恢复码"
            case 401:
                return "用户名或密码错误"
            case 403:
                return detail.flatMap { $0.isEmpty ? nil : $0 } ?? "账号被冻结或封禁，请稍后再试"
            case 429:
                return "尝试过于频繁，请稍后再试"
            default:
                break
            }
        }
        return (error as? APIError)?.message ?? "登录失败，请稍后再试"
    }
}
