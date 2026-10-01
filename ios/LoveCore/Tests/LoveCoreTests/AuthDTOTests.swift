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

import XCTest

@testable import LoveCore

final class AuthDTOTests: XCTestCase {

    func testTokenResponseDecodesPlaceholderToken() throws {
        // The body's access_token is the literal "http-only"; the real JWT
        // arrives via Set-Cookie. The DTO must decode this body without
        // treating the placeholder as a credential.
        let data = Data(
            #"{"access_token":"http-only","token_type":"bearer","expires_in":86400,"role":"partner_a"}"#.utf8
        )
        let response = try LoveAPIClient.decode(AuthDTOs.TokenResponse.self, from: data)
        XCTAssertEqual(response.accessToken, "http-only")
        XCTAssertEqual(response.expiresIn, 86_400)
        XCTAssertEqual(response.role, "partner_a")
    }

    func testUserProfileDecodesWithUnknownFieldsTolerated() throws {
        let data = Data(
            #"{"uid":"u1","username":"admin","nickname":"管理员","avatar":null,"role":"partner_a","session_version":3,"future_field":{"x":1}}"#
                .utf8
        )
        let profile = try LoveAPIClient.decode(AuthDTOs.UserProfile.self, from: data)
        XCTAssertEqual(profile, AuthDTOs.UserProfile(uid: "u1", username: "admin", nickname: "管理员", avatar: nil, role: "partner_a"))
    }

    func testLoginRequestOmitsAbsentTOTPCode() throws {
        let plain = try JSONSerialization.jsonObject(with: LoveAPIClient.encoder.encode(AuthDTOs.LoginRequest(username: "admin", password: "pw"))) as? [String: Any]
        XCTAssertEqual(plain?["username"] as? String, "admin")
        XCTAssertNil(plain?["totp_code"], "totp_code must be absent when unset")

        let withTotp = try JSONSerialization.jsonObject(
            with: LoveAPIClient.encoder.encode(AuthDTOs.LoginRequest(username: "admin", password: "pw", totpCode: "123456"))
        ) as? [String: Any]
        XCTAssertEqual(withTotp?["totp_code"] as? String, "123456")
    }

    func testBootstrapRegisterRequestUsesSnakeCaseKeys() throws {
        let payload = AuthDTOs.BootstrapRegisterRequest(
            username: "admin",
            password: "abc12345",
            nickname: "我",
            siteName: "恋爱记",
            loveStartDate: "2024-05-01T00:00:00Z"
        )
        let json = try JSONSerialization.jsonObject(with: LoveAPIClient.encoder.encode(payload)) as? [String: Any]
        XCTAssertEqual(json?["role"] as? String, "partner_a")
        XCTAssertEqual(json?["site_name"] as? String, "恋爱记")
        XCTAssertEqual(json?["love_start_date"] as? String, "2024-05-01T00:00:00Z")
        XCTAssertNil(json?["totp_code"])
    }

    func testBootstrapStatusDecodes() throws {
        let data = Data(#"{"bootstrapped":false}"#.utf8)
        let status = try LoveAPIClient.decode(AuthDTOs.BootstrapStatus.self, from: data)
        XCTAssertFalse(status.bootstrapped)
    }

    func testHealthResponseToleratesExtraFields() throws {
        let data = Data(#"{"app":"ok","database":"ok","redis":"ok","uptime_s":123}"#.utf8)
        let health = try LoveAPIClient.decode(AuthDTOs.HealthResponse.self, from: data)
        XCTAssertEqual(health.database, "ok")
    }
}
