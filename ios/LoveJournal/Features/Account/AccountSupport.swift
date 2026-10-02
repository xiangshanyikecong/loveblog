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

import SwiftUI

import LoveCore

// MARK: - M6 account-module shared helpers

/// M6 account-module lookups. The keys live in `M6A.xcstrings`, whose table
/// name is `"M6A"` — every lookup must pass the table explicitly (String
/// Catalogs are per-file tables; the default table stays `Localizable`).
enum M6AL10n {
    static func value(_ keyAndValue: String.LocalizationValue) -> String {
        String(localized: keyAndValue, table: "M6A")
    }
}

extension LocalizedStringKey {
    /// Resolves an M6A key up front. The default-table lookup then misses and
    /// falls back to the resolved text itself, so shared components that only
    /// take `LocalizedStringKey` (LoveField, LovePrimaryButton, …) render the
    /// translated string.
    init(m6a key: String) {
        self.init(stringLiteral: M6AL10n.value(String.LocalizationValue(key)))
    }
}

/// Maps any error onto a presentable message (server detail wins).
enum M6AErrorText {
    static func describe(_ error: Error) -> String {
        (error as? APIError)?.message ?? M6AL10n.value("m6a.error.generic")
    }
}

// MARK: - Copy-to-clipboard row (TOTP secret / otpauth URI / recovery codes)

struct M6ACopyRow: View {
    let titleKey: LocalizedStringKey
    let value: String
    @State private var copied = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(titleKey)
                .font(.caption.weight(.medium))
                .foregroundStyle(LoveTheme.secondaryText)
            HStack(spacing: 8) {
                Text(value)
                    .font(.footnote.weight(.medium).monospaced())
                    .foregroundStyle(LoveTheme.text)
                    .lineLimit(2)
                    .truncationMode(.middle)
                    .textSelection(.enabled)
                Spacer(minLength: 8)
                Button {
                    UIPasteboard.general.string = value
                    withAnimation(.easeOut(duration: 0.2)) { copied = true }
                    Task {
                        try? await Task.sleep(for: .seconds(1.6))
                        withAnimation(.easeOut(duration: 0.2)) { copied = false }
                    }
                } label: {
                    Image(systemName: copied ? "checkmark.circle.fill" : "doc.on.doc")
                        .font(.footnote)
                        .foregroundStyle(copied ? LoveTheme.mint : LoveTheme.primaryAccessible)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(LoveTheme.background.opacity(0.6))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .stroke(LoveTheme.outline, lineWidth: 1)
            }
        }
    }
}
