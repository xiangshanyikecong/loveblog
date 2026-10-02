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

// MARK: - M5C localization + formatting helpers (life modules)

/// M5 life-module lookups. The new keys live in `M5C.xcstrings`, whose table
/// name is `"M5C"` — every lookup must therefore pass the table explicitly
/// (String Catalogs are per-file tables; the default table stays
/// `Localizable`).
enum M5CL10n {
    static func value(_ keyAndValue: String.LocalizationValue) -> String {
        String(localized: keyAndValue, table: "M5C")
    }
}

extension LocalizedStringKey {
    /// Resolves an M5C key up front. The default-table lookup then misses and
    /// falls back to the resolved text itself, so shared components that only
    /// take `LocalizedStringKey` (LoveField, LovePrimaryButton, …) render the
    /// translated string.
    init(m5c key: String) {
        self.init(stringLiteral: M5CL10n.value(String.LocalizationValue(key)))
    }
}

/// Shared formatting for the M5 life modules: money, months and the ledger
/// category vocabulary.
enum M5CFormat {
    /// `¥12.34` — cent amounts always render with two decimals.
    static func money(_ cents: Int) -> String {
        String(format: "¥%.2f", Double(cents) / 100.0)
    }

    private static let monthKeyFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = .current
        return formatter
    }()

    private static let monthLabelFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.setLocalizedDateFormatFromTemplate("yMMMM")
        return formatter
    }()

    /// `2026-10` — server query format, local calendar.
    static func monthKey(_ date: Date) -> String {
        monthKeyFormatter.string(from: date)
    }

    /// Locale-aware month label for the ledger header.
    static func monthLabel(_ date: Date) -> String {
        monthLabelFormatter.string(from: date)
    }

    /// Ledger category quick-chips: stable storage keys so `by_category`
    /// aggregation stays locale-independent; labels are localized for display.
    static let categoryKeys = [
        "food", "transport", "shopping", "entertainment", "housing", "other",
    ]

    /// Localized label for a stored category key; unknown/custom values and
    /// `nil` pass through (`nil` only when the raw value was empty/nil).
    static func categoryLabel(_ raw: String?) -> String? {
        guard let raw, !raw.isEmpty else { return nil }
        switch raw {
        case "food": return M5CL10n.value("m5c.ledger.category.food")
        case "transport": return M5CL10n.value("m5c.ledger.category.transport")
        case "shopping": return M5CL10n.value("m5c.ledger.category.shopping")
        case "entertainment": return M5CL10n.value("m5c.ledger.category.entertainment")
        case "housing": return M5CL10n.value("m5c.ledger.category.housing")
        case "other": return M5CL10n.value("m5c.ledger.category.other")
        default: return raw
        }
    }
}
