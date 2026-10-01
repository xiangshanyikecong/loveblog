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

final class APIErrorTests: XCTestCase {

    func testServerDetailExtractsStringDetail() throws {
        let data = Data(#"{"detail":"Bootstrap is already completed"}"#.utf8)
        XCTAssertEqual(APIError.serverDetail(from: data), "Bootstrap is already completed")
    }

    func testServerDetailFormats422ValidationArray() throws {
        let data = Data(
            #"{"detail":[{"loc":["body","username"],"msg":"String should have at least 3 characters","type":"string_too_short"}]}"#
                .utf8
        )
        XCTAssertEqual(
            APIError.serverDetail(from: data),
            "body.username: String should have at least 3 characters"
        )
    }

    func testServerDetailJoinsMultipleValidationItems() throws {
        let data = Data(
            #"{"detail":[{"loc":["body","a"],"msg":"bad a"},{"loc":["body","b"],"msg":"bad b"}]}"#.utf8
        )
        XCTAssertEqual(APIError.serverDetail(from: data), "body.a: bad a；body.b: bad b")
    }

    func testServerDetailReturnsNilForUnreadableBody() {
        XCTAssertNil(APIError.serverDetail(from: nil))
        XCTAssertNil(APIError.serverDetail(from: Data("not json".utf8)))
        XCTAssertNil(APIError.serverDetail(from: Data(#"{"other":1}"#.utf8)))
    }

    func testSessionExpiredDetection() {
        XCTAssertTrue(APIError.http(status: 401, detail: nil).isSessionExpired)
        XCTAssertFalse(APIError.http(status: 403, detail: nil).isSessionExpired)
        XCTAssertFalse(APIError.transport(.timedOut).isSessionExpired)
    }

    func testHTTPMessagePrefersServerDetail() {
        XCTAssertEqual(
            APIError.http(status: 500, detail: "Internal server error").message,
            "Internal server error"
        )
        XCTAssertEqual(APIError.http(status: 404, detail: nil).message.contains(":8000"), true)
    }

    func testLoginFlowMapping() {
        XCTAssertEqual(
            LoginFlow.presentableMessage(APIError.http(status: 401, detail: "totp_required")),
            "该账号已启用两步验证，请输入 6 位验证码或恢复码"
        )
        XCTAssertEqual(LoginFlow.presentableMessage(APIError.http(status: 401, detail: nil)), "用户名或密码错误")
        XCTAssertEqual(LoginFlow.presentableMessage(APIError.http(status: 429, detail: nil)), "尝试过于频繁，请稍后再试")
        XCTAssertEqual(
            LoginFlow.presentableMessage(LoginError.totpRequired),
            "该账号已启用两步验证，请输入 6 位验证码或恢复码"
        )
        let frozen = LoginFlow.presentableMessage(APIError.http(status: 403, detail: "Frozen for 29 minutes"))
        XCTAssertEqual(frozen, "Frozen for 29 minutes")
    }
}
