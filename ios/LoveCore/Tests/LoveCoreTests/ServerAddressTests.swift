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

/// 地址归一化规则单测，逐条移植自 Android 的 `ServerAddressTest.kt`。
/// 覆盖「直连 :8000 后端」与「反代 /api 域名」两种部署形态——这是登录页
/// 最核心的纯逻辑，出错会导致整站不可达。
final class ServerAddressTests: XCTestCase {

    // MARK: - normalize

    func testBareDomainUsesProxyPathAndDefaultPort() {
        XCTAssertEqual(ServerAddress.normalize("demo.com"), "https://demo.com/api/v1")
    }

    func testExplicitAPIPathIsPreserved() {
        XCTAssertEqual(ServerAddress.normalize("https://demo.com/api"), "https://demo.com/api/v1")
        XCTAssertEqual(ServerAddress.normalize("https://demo.com/api/v1"), "https://demo.com/api/v1")
    }

    func testDomainWithoutPathAppendsAPIV1() {
        XCTAssertEqual(ServerAddress.normalize("https://demo.com"), "https://demo.com/api/v1")
    }

    func testDomainWithCustomPathAppendsV1() {
        XCTAssertEqual(ServerAddress.normalize("https://demo.com/love"), "https://demo.com/love/v1")
    }

    func testIPLiteralDefaultsToBackendPort8000() {
        XCTAssertEqual(ServerAddress.normalize("http://192.168.1.5"), "http://192.168.1.5:8000/v1")
        // 裸主机名按原实现补 https 协议
        XCTAssertEqual(ServerAddress.normalize("192.168.1.5"), "https://192.168.1.5:8000/v1")
    }

    func testEmulatorStyleHostKeepsExplicitPortAndSkipsProxyPath() {
        XCTAssertEqual(ServerAddress.normalize("http://10.0.2.2:8000"), "http://10.0.2.2:8000/v1")
    }

    func testLocalhostDefaultsToBackendPort8000() {
        XCTAssertEqual(ServerAddress.normalize("https://localhost"), "https://localhost:8000/v1")
    }

    func testExplicitNonDefaultPortIsKept() {
        XCTAssertEqual(ServerAddress.normalize("https://demo.com:8443/v1"), "https://demo.com:8443/v1")
    }

    func testQueryAndFragmentAreStripped() {
        XCTAssertEqual(ServerAddress.normalize("https://demo.com/?from=qr#top"), "https://demo.com/api/v1")
    }

    func testTrailingSlashStrippedAndCaseInsensitiveV1Recognized() {
        // 已带 v1（大小写不敏感）的路径原样保留大小写
        XCTAssertEqual(ServerAddress.normalize("http://192.168.1.5:8000/V1/"), "http://192.168.1.5:8000/V1")
    }

    func testEmptyInputReturnsEmpty() {
        XCTAssertEqual(ServerAddress.normalize(""), "")
        XCTAssertEqual(ServerAddress.normalize("   "), "")
    }

    func testUnparseableInputIsReturnedAsIs() {
        let weird = "https://de mo.com"
        XCTAssertEqual(ServerAddress.normalize(weird), weird)
    }

    func testExplicitPort8000OnDomainSkipsProxyPath() {
        XCTAssertEqual(ServerAddress.normalize("https://demo.com:8000"), "https://demo.com:8000/v1")
    }

    // MARK: - stripping

    func testStripAPIVersionRemovesV1Only() {
        // 原实现仅去掉 "/v1"，/api 前缀保留
        XCTAssertEqual(ServerAddress.stripApiVersion("https://demo.com/api/v1"), "https://demo.com/api")
        XCTAssertEqual(ServerAddress.stripApiVersion("http://192.168.1.5:8000/v1"), "http://192.168.1.5:8000")
        XCTAssertEqual(ServerAddress.stripApiVersion("https://demo.com"), "https://demo.com")
    }

    func testStripMediaAPIPrefixRemovesFullAPIV1Prefix() {
        XCTAssertEqual(ServerAddress.stripMediaApiPrefix("https://demo.com/api/v1"), "https://demo.com")
        XCTAssertEqual(ServerAddress.stripMediaApiPrefix("http://192.168.1.5:8000/v1"), "http://192.168.1.5:8000")
    }

    // MARK: - validateAddressInput

    func testBlankInputReportsMissingAddress() {
        XCTAssertEqual(ServerAddress.validateAddressInput("   ", allowCleartext: false), "请输入服务器地址")
    }

    func testMissingSchemeReportsIncompleteAddress() {
        XCTAssertEqual(
            ServerAddress.validateAddressInput("demo.com", allowCleartext: false),
            "请填写完整的 https:// 服务器地址"
        )
    }

    func testValidHTTPSAddressPasses() {
        XCTAssertNil(ServerAddress.validateAddressInput("https://demo.com", allowCleartext: false))
    }

    func testCleartextAllowedOnlyForLocalDevelopmentHostsWhenEnabled() {
        XCTAssertNil(ServerAddress.validateAddressInput("http://192.168.1.5:8000", allowCleartext: true))
        XCTAssertNil(ServerAddress.validateAddressInput("http://10.0.2.2:8000", allowCleartext: true))
        // 公网域名走 HTTP 始终拒绝，即便调试版放开了明文限制
        XCTAssertNotNil(ServerAddress.validateAddressInput("http://demo.com", allowCleartext: true))
        // 正式版（allowCleartext=false）一切明文都拒绝
        XCTAssertNotNil(ServerAddress.validateAddressInput("http://192.168.1.5:8000", allowCleartext: false))
    }

    func testGarbageHostReportsFormatError() {
        let error = ServerAddress.validateAddressInput("https://de mo.com", allowCleartext: false)
        XCTAssertNotNil(error)
        XCTAssertTrue(error?.contains("格式") == true)
    }

    // MARK: - healthBase

    func testHealthBaseStripsAPIVersion() {
        XCTAssertEqual(ServerAddress.healthBase(for: "https://demo.com/api"), "https://demo.com/api")
        XCTAssertEqual(ServerAddress.healthBase(for: "192.168.1.5"), "https://192.168.1.5:8000")
    }

    // MARK: - local host classification

    func testLocalDevelopmentHosts() {
        XCTAssertTrue(ServerAddress.isLocalDevelopmentHost("localhost"))
        XCTAssertTrue(ServerAddress.isLocalDevelopmentHost("127.0.0.1"))
        XCTAssertTrue(ServerAddress.isLocalDevelopmentHost("192.168.1.5"))
        XCTAssertTrue(ServerAddress.isLocalDevelopmentHost("10.1.2.3"))
        XCTAssertTrue(ServerAddress.isLocalDevelopmentHost("172.16.0.1"))
        XCTAssertTrue(ServerAddress.isLocalDevelopmentHost("172.31.255.255"))
        XCTAssertFalse(ServerAddress.isLocalDevelopmentHost("172.32.0.1"))
        XCTAssertFalse(ServerAddress.isLocalDevelopmentHost("demo.com"))
        XCTAssertFalse(ServerAddress.isLocalDevelopmentHost("11.0.0.1"))
    }
}
