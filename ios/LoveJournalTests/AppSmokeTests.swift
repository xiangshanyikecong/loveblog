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
@testable import LoveJournal

/// End-to-end smoke checks for the app-side plumbing that LoveCore's own
/// tests cannot cover: persisted server settings, Keychain session storage
/// and media URL resolution.
final class AppSmokeTests: XCTestCase {
    private var savedApiBase: String?
    private var savedDefaultsKey = ServerSettings.apiBaseDefaultsKey

    override func setUp() {
        super.setUp()
        savedApiBase = UserDefaults.standard.string(forKey: savedDefaultsKey)
    }

    override func tearDown() {
        if let savedApiBase {
            UserDefaults.standard.set(savedApiBase, forKey: savedDefaultsKey)
        } else {
            UserDefaults.standard.removeObject(forKey: savedDefaultsKey)
        }
        super.tearDown()
    }

    func testServerSettingsNormalizesAddressOnSave() {
        UserDefaults.standard.set(ServerAddress.normalize("https://demo.com/api"), forKey: savedDefaultsKey)
        XCTAssertEqual(ServerSettings.apiBase, "https://demo.com/api/v1")
        XCTAssertEqual(ServerSettings.displayAddress, "https://demo.com/api")
        XCTAssertEqual(ServerSettings.mediaBase, "https://demo.com")
    }

    func testMediaURLResolution() {
        UserDefaults.standard.set("https://demo.com/api/v1", forKey: savedDefaultsKey)
        XCTAssertEqual(
            ServerSettings.mediaURL("/uploads/a.jpg")?.absoluteString,
            "https://demo.com/uploads/a.jpg"
        )
        XCTAssertEqual(
            ServerSettings.mediaURL("uploads/a.jpg")?.absoluteString,
            "https://demo.com/uploads/a.jpg"
        )
        XCTAssertEqual(
            ServerSettings.mediaURL("https://cdn.example.com/a.jpg")?.absoluteString,
            "https://cdn.example.com/a.jpg"
        )
        XCTAssertNil(ServerSettings.mediaURL(nil))
        XCTAssertNil(ServerSettings.mediaURL(""))
    }

    func testKeychainSessionRoundtrip() throws {
        // Headless CI simulator runners can deny Keychain access entirely;
        // the integration behavior is verified when running locally on a Mac.
        try XCTSkipUnless(
            KeychainStore.isAvailable(),
            "Keychain unavailable in this environment — skipped, verify locally on a Mac"
        )
        let account = "test:\(UUID().uuidString)"
        defer { KeychainStore.deleteSession(account: account) }

        let cookie = HTTPCookie(
            properties: [
                .domain: "demo.com",
                .path: "/",
                .name: "access_token",
                .value: "test-jwt",
            ]
        )!
        KeychainStore.saveSession([cookie], account: account)
        XCTAssertEqual(KeychainStore.loadSession(account: account)?.first?.value, "test-jwt")

        // Overwrite (update path) and delete.
        let updated = HTTPCookie(
            properties: [
                .domain: "demo.com",
                .path: "/",
                .name: "access_token",
                .value: "rotated-jwt",
            ]
        )!
        KeychainStore.saveSession([updated], account: account)
        XCTAssertEqual(KeychainStore.loadSession(account: account)?.first?.value, "rotated-jwt")

        KeychainStore.deleteSession(account: account)
        XCTAssertNil(KeychainStore.loadSession(account: account))
    }
}
