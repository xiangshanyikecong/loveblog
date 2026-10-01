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

// MARK: - Screen scaffold

extension View {
    /// Full-bleed brand background used by every screen (Android `LovePage`).
    func loveScreenBackground() -> some View {
        frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(LoveTheme.background.ignoresSafeArea())
    }
}

// MARK: - Cards

/// Soft rounded card (Android `LoveSoftCard`).
struct LoveSoftCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) { content }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(LoveTheme.surface)
            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            .shadow(color: .black.opacity(0.06), radius: 10, x: 0, y: 3)
    }
}

// MARK: - Text bits

struct LoveSectionTitle: View {
    let textKey: LocalizedStringKey

    var body: some View {
        Text(textKey)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(LoveTheme.secondaryText)
            .textCase(nil)
    }
}

struct LoveEmptyState: View {
    let systemImage: String
    let titleKey: LocalizedStringKey
    var messageKey: LocalizedStringKey?

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: systemImage)
                .font(.system(size: 40, weight: .light))
                .foregroundStyle(LoveTheme.pink.opacity(0.6))
            Text(titleKey)
                .font(.headline)
                .foregroundStyle(LoveTheme.text)
            if let messageKey {
                Text(messageKey)
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 32)
    }
}

/// Red-tinted error banner under forms.
struct LoveErrorBanner: View {
    let message: String

    var body: some View {
        Text(message)
            .font(.footnote)
            .foregroundStyle(LoveTheme.rose)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(10)
            .background(LoveTheme.rose.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

/// Green-tinted success banner under forms.
struct LoveSuccessBanner: View {
    let message: String

    var body: some View {
        Text(message)
            .font(.footnote)
            .foregroundStyle(LoveTheme.mint)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(10)
            .background(LoveTheme.mint.opacity(0.14))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

// MARK: - Fields

/// Labeled field container with the brand outline style (rounded 14, tinted
/// border on focus).
struct LoveField<Content: View>: View {
    let labelKey: LocalizedStringKey
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(labelKey)
                .font(.footnote.weight(.medium))
                .foregroundStyle(LoveTheme.secondaryText)
            content
                .font(.body)
                .foregroundStyle(LoveTheme.text)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .padding(.horizontal, 14)
                .padding(.vertical, 12)
                .background(LoveTheme.background.opacity(0.6))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .stroke(LoveTheme.outline, lineWidth: 1)
                }
        }
    }
}

// MARK: - Buttons

/// Gradient capsule CTA (Android primary button).
struct LovePrimaryButton: View {
    let titleKey: LocalizedStringKey
    var loading = false
    var enabled = true
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if loading {
                    ProgressView()
                        .tint(.white)
                }
                Text(titleKey)
                    .font(.headline)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 50)
        }
        .foregroundStyle(.white)
        .background(LoveTheme.gradient, in: Capsule())
        .disabled(loading || !enabled)
        .opacity(loading || !enabled ? 0.6 : 1)
    }
}

/// Outlined secondary action (e.g. "test connection").
struct LoveSecondaryButton: View {
    let titleKey: LocalizedStringKey
    var loading = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if loading {
                    ProgressView()
                        .tint(LoveTheme.primaryAccessible)
                }
                Text(titleKey)
                    .font(.subheadline.weight(.semibold))
            }
            .frame(maxWidth: .infinity)
            .frame(height: 42)
        }
        .foregroundStyle(LoveTheme.primaryAccessible)
        .overlay(Capsule().stroke(LoveTheme.primaryAccessible.opacity(0.5), lineWidth: 1))
        .disabled(loading)
        .opacity(loading ? 0.6 : 1)
    }
}
