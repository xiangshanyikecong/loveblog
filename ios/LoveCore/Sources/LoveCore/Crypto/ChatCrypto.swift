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

import CommonCrypto
import CryptoKit
import Foundation

/// Shared-passphrase E2EE for cottage chat, byte-compatible with the web
/// (WebCrypto) and Android (JVM) implementations:
///
/// - PBKDF2-HMAC-SHA256, 210,000 iterations, 32-byte key; the salt is a
///   standard-base64 *string* on the wire, decoded to bytes for derivation.
/// - AES-256-GCM with a 12-byte random IV; the wire ciphertext is one base64
///   blob of `ct‖tag` (CryptoKit's `SealedBox` without the nonce prefix).
/// - No asymmetric handshake: both partners derive the same key from the
///   shared passphrase. The server stores only a verifier it can't open.
public enum ChatCrypto {
    public static let verifierToken = "cottage-chat::verify::v1"
    public static let defaultIterations = 210_000

    // MARK: - Key derivation

    /// PBKDF2(passphrase, saltB64-decoded bytes, iterations) → 256-bit key.
    public static func deriveKey(
        passphrase: String,
        saltBase64: String,
        iterations: Int = ChatCrypto.defaultIterations
    ) throws -> SymmetricKey {
        guard let salt = Data(base64Encoded: saltBase64), !salt.isEmpty else {
            throw ChatCryptoError.badBase64("salt")
        }
        return deriveKey(passphrase: passphrase, salt: salt, iterations: iterations)
    }

    public static func deriveKey(
        passphrase: String,
        salt: Data,
        iterations: Int
    ) -> SymmetricKey {
        let password = Array(passphrase.utf8)
        let passwordCount = password.count
        let saltCount = salt.count
        let keyLength = 32
        var derived = [UInt8](repeating: 0, count: keyLength)

        let status = derived.withUnsafeMutableBufferPointer { derivedBuffer -> Int32 in
            password.withUnsafeBufferPointer { passwordBuffer -> Int32 in
                salt.withUnsafeBytes { saltRaw -> Int32 in
                    CCKeyDerivationPBKDF(
                        CCPBKDFAlgorithm(kCCPBKDF2),
                        passwordBuffer.baseAddress.map { UnsafeRawPointer($0).assumingMemoryBound(to: Int8.self) },
                        passwordCount,
                        saltRaw.bindMemory(to: UInt8.self).baseAddress,
                        saltCount,
                        CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256),
                        UInt32(iterations),
                        derivedBuffer.baseAddress,
                        keyLength
                    )
                }
            }
        }
        precondition(status == kCCSuccess, "PBKDF2 failed: \(status)")
        return SymmetricKey(data: Data(derived))
    }

    // MARK: - String encryption

    public static func encryptString(
        key: SymmetricKey,
        plaintext: String,
        ivBase64: String? = nil
    ) throws -> (ivBase64: String, ciphertextBase64: String) {
        let sealed = try encryptData(key: key, plaintext: Data(plaintext.utf8), ivBase64: ivBase64)
        return (sealed.ivBase64, sealed.ciphertextBase64)
    }

    /// Decrypts a `base64(ct‖tag)` envelope; throws on wrong key/tampering.
    public static func decryptString(
        key: SymmetricKey,
        ivBase64: String,
        ciphertextBase64: String
    ) throws -> String {
        let data = try decryptData(
            key: key, ivBase64: ivBase64, ciphertextBase64: ciphertextBase64
        )
        guard let text = String(data: data, encoding: .utf8) else {
            throw ChatCryptoError.notUTF8
        }
        return text
    }

    // MARK: - Raw byte encryption (E2EE media files)

    public static func encryptData(
        key: SymmetricKey,
        plaintext: Data,
        ivBase64: String? = nil
    ) throws -> (ivBase64: String, ciphertextBase64: String) {
        let nonce: AES.GCM.Nonce
        if let ivBase64, let ivData = Data(base64Encoded: ivBase64) {
            nonce = try AES.GCM.Nonce(data: ivData)
        } else {
            nonce = AES.GCM.Nonce()
        }
        let sealed = try AES.GCM.seal(plaintext, using: key, nonce: nonce)
        // `combined` = nonce‖ct‖tag; the wire format wants only ct‖tag.
        return (Data(nonce).base64EncodedString(), sealed.ciphertextAndTag.base64EncodedString())
    }

    public static func decryptData(
        key: SymmetricKey,
        ivBase64: String,
        ciphertextBase64: String
    ) throws -> Data {
        guard let iv = Data(base64Encoded: ivBase64),
              let blob = Data(base64Encoded: ciphertextBase64),
              blob.count > 16
        else { throw ChatCryptoError.badBase64("iv/ciphertext") }
        let tag = blob.suffix(16)
        let ciphertext = blob.dropLast(16)
        let box = try AES.GCM.SealedBox(
            nonce: AES.GCM.Nonce(data: iv), ciphertext: ciphertext, tag: tag
        )
        return try AES.GCM.open(box, using: key)
    }

    // MARK: - Verifier / proofs

    public static let vaultVerifierToken = "cottage-vault::verify::v1"

    /// `verifier_cipher = AES-GCM(key, verifierToken)`; `verifier_hash` is
    /// sha256-hex of the *base64 ciphertext string* (not the raw bytes).
    /// Pass `token:` to target another scope (vault uses its own constant).
    public static func makeVerifier(
        key: SymmetricKey,
        token: String = verifierToken
    ) throws -> (ivBase64: String, cipherBase64: String, hashHex: String) {
        let sealed = try encryptString(key: key, plaintext: token)
        return (sealed.ivBase64, sealed.ciphertextBase64, sha256Hex(sealed.ciphertextBase64))
    }

    /// Unlock proof sent to the key-verify endpoint after a successful unlock.
    public static func makeProof(key: SymmetricKey, token: String = verifierToken) throws -> (ivBase64: String, cipherBase64: String) {
        let proof = try encryptString(key: key, plaintext: "\(token)::proof::\(Int(Date().timeIntervalSince1970 * 1000))")
        return (proof.ivBase64, proof.ciphertextBase64)
    }

    /// True when the stored verifier decrypts under `key` to the token.
    public static func verifierMatches(
        key: SymmetricKey,
        verifierIvBase64: String,
        verifierCipherBase64: String,
        token: String = verifierToken
    ) -> Bool {
        (try? decryptString(key: key, ivBase64: verifierIvBase64, ciphertextBase64: verifierCipherBase64)) == token
    }

    // MARK: - Hashing / randomness

    public static func sha256Hex(_ string: String) -> String {
        SHA256.hash(data: Data(string.utf8)).map { String(format: "%02x", $0) }.joined()
    }

    public static func randomSaltBase64() -> String {
        var bytes = [UInt8](repeating: 0, count: 16)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return Data(bytes).base64EncodedString()
    }
}

public enum ChatCryptoError: Error {
    case badBase64(String)
    case notUTF8
}

private extension AES.GCM.SealedBox {
    /// ciphertext + tag, i.e. `combined` minus the 12-byte nonce prefix.
    var ciphertextAndTag: Data {
        combined.map { $0.dropFirst(12) } ?? ciphertext + tag
    }
}
