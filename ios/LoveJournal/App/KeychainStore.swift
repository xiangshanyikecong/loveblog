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
import Security

/// Durable Keychain storage for the session cookie.
///
/// `HTTPCookieStorage` already persists cookies in the app sandbox, but the
/// cookie *is* the bearer credential — the Android client keeps it in
/// EncryptedSharedPreferences for the same reason. The Keychain copy is the
/// source of truth restored on launch; `HTTPCookieStorage` is just the
/// working set handed to URLSession. Each server address gets its own entry
/// (`account = apiBase`) so local data never crosses servers/accounts.
enum KeychainStore {
    private static let service = "com.lovejournal.app.ios.session"

    static func saveSession(_ cookies: [HTTPCookie], account: String) {
        guard let data = try? NSKeyedArchiver.archivedData(
            withRootObject: cookies,
            requiringSecureCoding: true
        ) else { return }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let update: [String: Any] = [kSecValueData as String: data]
        let status = SecItemUpdate(query as CFDictionary, update as CFDictionary)
        guard status == errSecItemNotFound else { return }

        var add = query
        add[kSecValueData as String] = data
        // This-device-only: the session must never ride iCloud Keychain or
        // device backups to another device (mirrors Android's
        // data_extraction_rules excluding cookies from backup).
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }

    static func loadSession(account: String) -> [HTTPCookie]? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data
        else { return nil }
        return try? NSKeyedUnarchiver.unarchivedObject(
            ofClasses: [NSArray.self, HTTPCookie.self],
            from: data
        ) as? [HTTPCookie]
    }

    static func deleteSession(account: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }
}
