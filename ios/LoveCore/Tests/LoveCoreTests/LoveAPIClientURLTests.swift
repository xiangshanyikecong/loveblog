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

/// Locks the request-URL joining for both deployment forms — a wrong join
/// here makes the whole app unreachable, so it deserves its own tests.
final class LoveAPIClientURLTests: XCTestCase {

    func testReverseProxyDomainJoin() throws {
        let url = try LoveAPIClient.makeURL(apiBase: "https://demo.com/api/v1", path: "/auth/login")
        XCTAssertEqual(url.absoluteString, "https://demo.com/api/v1/auth/login")
        XCTAssertEqual(url.host, "demo.com")
        XCTAssertEqual(url.scheme, "https")
    }

    func testDirectBackendJoin() throws {
        let url = try LoveAPIClient.makeURL(apiBase: "http://192.168.1.5:8000/v1", path: "/auth/me")
        XCTAssertEqual(url.absoluteString, "http://192.168.1.5:8000/v1/auth/me")
        XCTAssertEqual(url.port, 8000)
    }

    func testJoinKeepsCustomSubPath() throws {
        let url = try LoveAPIClient.makeURL(
            apiBase: "https://demo.com/love/api/v1",
            path: "/cottage/chat/messages"
        )
        XCTAssertEqual(url.absoluteString, "https://demo.com/love/api/v1/cottage/chat/messages")
    }

    func testQueryItemsAreAppended() throws {
        let url = try LoveAPIClient.makeURL(
            apiBase: "https://demo.com/api/v1",
            path: "/cottage/chat/messages",
            query: [
                URLQueryItem(name: "before_id", value: "42"),
                URLQueryItem(name: "limit", value: "30"),
            ]
        )
        XCTAssertEqual(url.path, "/api/v1/cottage/chat/messages")
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        XCTAssertEqual(items.first(where: { $0.name == "before_id" })?.value, "42")
        XCTAssertEqual(items.first(where: { $0.name == "limit" })?.value, "30")
    }

    func testEmptyAPIBaseThrows() {
        XCTAssertThrowsError(try LoveAPIClient.makeURL(apiBase: "", path: "/auth/me")) { error in
            XCTAssertEqual(error as? APIError, .serverNotConfigured)
        }
    }

    func testUnparseableAPIBaseThrows() {
        XCTAssertThrowsError(try LoveAPIClient.makeURL(apiBase: "https://de mo.com/api/v1", path: "/auth/me")) { error in
            XCTAssertEqual(error as? APIError, .serverNotConfigured)
        }
    }
}
