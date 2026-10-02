/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

import CryptoKit
import XCTest

@testable import LoveCore

/// Known-answer vectors, byte-identical to Android's `ChatCryptoTest.kt`
/// (generated offline with Python cryptography ≡ WebCrypto parameters).
/// The Swift implementation MUST reproduce these exactly to stay
/// interoperable with the web/Android clients.
final class ChatCryptoTests: XCTestCase {
    private static let katSalt = "AAECAwQFBgcICQoLDA0ODw=="
    private static let katIV = "AAECAwQFBgcICQoL"
    private static let katCiphertext = "sAE2xhkEeFbhunxtWd/IpnEjMx0yfSUDJu35jJVl24hWTQatYRJ/6xg="
    private static let katPassphrase = "恋爱记-test-❤️"
    private static let katPlaintext = "你好，悄悄话 ❤️"
    private static let katVerifierHash = "11bb4439c5094c93d794bc29f4abc0ad24323a412f4b69cc6e188d596e593fa4"

    private func katKey() -> SymmetricKey {
        (try? ChatCrypto.deriveKey(
            passphrase: Self.katPassphrase, saltBase64: Self.katSalt, iterations: 210_000
        ))!
    }

    func testDecryptKnownAnswerVector() throws {
        let key = katKey()
        let plaintext = try ChatCrypto.decryptString(
            key: key, ivBase64: Self.katIV, ciphertextBase64: Self.katCiphertext
        )
        XCTAssertEqual(plaintext, Self.katPlaintext)
    }

    func testEncryptKnownAnswerVector() throws {
        let key = katKey()
        let sealed = try ChatCrypto.encryptString(
            key: key, plaintext: Self.katPlaintext, ivBase64: Self.katIV
        )
        XCTAssertEqual(sealed.ciphertextBase64, Self.katCiphertext)
    }

    func testVerifierHashVector() {
        XCTAssertEqual(ChatCrypto.sha256Hex(Self.katCiphertext), Self.katVerifierHash)
    }

    func testRoundtripChineseEmojiAndNewlines() throws {
        let key = try ChatCrypto.deriveKey(passphrase: "口令🔐", saltBase64: ChatCrypto.randomSaltBase64())
        let text = "多行文本\n第二行 ❤️ https://example.com?a=1&b=2"
        let sealed = try ChatCrypto.encryptString(key: key, plaintext: text)
        XCTAssertEqual(try ChatCrypto.decryptString(key: key, ivBase64: sealed.ivBase64, ciphertextBase64: sealed.ciphertextBase64), text)
    }

    func testWrongPassphraseFailsToDecrypt() throws {
        let key = try ChatCrypto.deriveKey(passphrase: "correct", saltBase64: Self.katSalt)
        XCTAssertThrowsError(
            try ChatCrypto.decryptString(key: key, ivBase64: Self.katIV, ciphertextBase64: Self.katCiphertext)
        )
    }

    func testTamperedCiphertextFails() throws {
        let key = katKey()
        var bytes = Data(base64Encoded: Self.katCiphertext)!
        bytes[3] ^= 0xFF
        XCTAssertThrowsError(
            try ChatCrypto.decryptString(key: key, ivBase64: Self.katIV, ciphertextBase64: bytes.base64EncodedString())
        )
    }

    func testBytesRoundtrip() throws {
        let key = try ChatCrypto.deriveKey(passphrase: "media", saltBase64: Self.katSalt)
        let raw = Data((0..<4096).map { UInt8($0 % 251) })
        let sealed = try ChatCrypto.encryptData(key: key, plaintext: raw)
        XCTAssertEqual(try ChatCrypto.decryptData(key: key, ivBase64: sealed.ivBase64, ciphertextBase64: sealed.ciphertextBase64), raw)
    }

    func testVerifierMatchesAndProof() throws {
        let key = try ChatCrypto.deriveKey(passphrase: "shared", saltBase64: Self.katSalt)
        let verifier = try ChatCrypto.makeVerifier(key: key)
        XCTAssertEqual(verifier.hashHex, ChatCrypto.sha256Hex(verifier.cipherBase64))
        XCTAssertTrue(ChatCrypto.verifierMatches(
            key: key, verifierIvBase64: verifier.ivBase64, verifierCipherBase64: verifier.cipherBase64
        ))
        let otherKey = try ChatCrypto.deriveKey(passphrase: "wrong", saltBase64: Self.katSalt)
        XCTAssertFalse(ChatCrypto.verifierMatches(
            key: otherKey, verifierIvBase64: verifier.ivBase64, verifierCipherBase64: verifier.cipherBase64
        ))
        let proof = try ChatCrypto.makeProof(key: key)
        let opened = try ChatCrypto.decryptString(key: key, ivBase64: proof.ivBase64, ciphertextBase64: proof.cipherBase64)
        XCTAssertTrue(opened.hasPrefix(ChatCrypto.verifierToken + "::proof::"))
    }
}
