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

import SwiftUI
import UIKit

/// Design tokens, ported from the Android client's `ui/theme/Color.kt`.
/// Values are 1:1 so the two clients stay visually identical; dark-mode
/// variants follow the Android dark scheme. Typography intentionally uses
/// system Dynamic Type styles (iOS convention) instead of porting the fixed
/// sp scale — text scales with the user's accessibility settings.
enum LoveTheme {
    /// Brand pink; dark mode brightens to the Android `LovePinkDarkScheme`.
    static let pink = dynamic(light: 0xE5_73_9B, dark: 0xFF_B1_C8)
    static let pinkDeep = Color(uiColor: UIColor(hex: 0xC7_5A_82))
    static let rose = dynamic(light: 0xFF_5C_8A, dark: 0xFF_7F_A0)
    static let peach = dynamic(light: 0xFF_9A_76, dark: 0xFF_B3_9C)
    static let lavender = dynamic(light: 0x9B_87_F5, dark: 0xB7_A8_FF)
    static let mint = dynamic(light: 0x56_C8_A5, dark: 0x7C_DC_BE)

    /// Light-mode primary: deepened so white text keeps ≥ 4.5:1 contrast
    /// (WCAG AA) while staying in the brand hue.
    static let primaryAccessible = dynamic(light: 0xB4_4A_6F, dark: 0xFF_B1_C8)

    static let background = dynamic(light: 0xFF_F8_FA, dark: 0x17_11_14)
    static let surface = dynamic(light: 0xFF_FF_FF, dark: 0x24_1C_20)
    static let outline = dynamic(light: 0xE6_D9_DE, dark: 0x45_33_3B)
    static let text = dynamic(light: 0x33_26_2B, dark: 0xFF_F3_F7)
    static let secondaryText = dynamic(light: 0x8A_6E_78, dark: 0xC9_A8_B4)

    /// Signature CTA gradient (Android `LoveGradientCard`).
    static let gradient = LinearGradient(
        colors: [rose, peach],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    static func dynamic(light: UInt32, dark: UInt32) -> Color {
        Color(uiColor: UIColor { trait in
            UIColor(hex: trait.userInterfaceStyle == .dark ? dark : light)
        })
    }
}

extension UIColor {
    convenience init(hex: UInt32) {
        self.init(
            red: CGFloat((hex >> 16) & 0xFF) / 255,
            green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255,
            alpha: 1
        )
    }
}
