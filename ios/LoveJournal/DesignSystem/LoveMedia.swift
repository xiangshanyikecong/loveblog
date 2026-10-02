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

// MARK: - Media loading

/// Async image against the configured media base with brand placeholder and
/// failure fallback (mirrors Android's AsyncImage + mediaUrl).
struct LoveAsyncImage: View {
    let url: URL?
    var contentMode: SwiftUI.ContentMode = .fill

    var body: some View {
        AsyncImage(url: url) { phase in
            switch phase {
            case .success(let image):
                image
                    .resizable()
                    .aspectRatio(contentMode: contentMode)
            case .failure:
                placeholder
            case .empty:
                ZStack {
                    Rectangle().fill(LoveTheme.outline.opacity(0.4))
                    ProgressView().tint(LoveTheme.primaryAccessible)
                }
            @unknown default:
                placeholder
            }
        }
    }

    private var placeholder: some View {
        Image(systemName: "photo")
            .font(.title3)
            .foregroundStyle(LoveTheme.secondaryText)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(LoveTheme.outline.opacity(0.3))
    }
}

/// Timeline/gallery media: prefers the server-side `_thumb` derivative and
/// falls back to the original when it is missing (Android parity).
struct LoveThumbImage: View {
    let path: String
    @State private var useOriginal = false

    private static func thumbPath(_ path: String) -> String {
        guard let dot = path.lastIndex(of: "."), path.hasPrefix("/") else { return path }
        return String(path[path.startIndex..<dot]) + "_thumb.jpg"
    }

    private var url: URL? {
        ServerSettings.mediaURL(useOriginal ? path : Self.thumbPath(path))
    }

    var body: some View {
        AsyncImage(url: url) { phase in
            switch phase {
            case .success(let image):
                image.resizable().aspectRatio(contentMode: .fill)
            case .failure:
                if !useOriginal {
                    Color.clear
                        .onAppear { useOriginal = true }
                } else {
                    Image(systemName: "photo")
                        .font(.title3)
                        .foregroundStyle(LoveTheme.secondaryText)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .background(LoveTheme.outline.opacity(0.3))
                }
            case .empty:
                ZStack {
                    Rectangle().fill(LoveTheme.outline.opacity(0.4))
                    ProgressView().tint(LoveTheme.primaryAccessible)
                }
            @unknown default:
                EmptyView()
            }
        }
    }
}

/// Small rounded status pill (badges, counts, visibility labels).
struct LovePill: View {
    let text: String
    var tint: Color = LoveTheme.primaryAccessible

    var body: some View {
        Text(text)
            .font(.caption2.weight(.medium))
            .foregroundStyle(tint)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(tint.opacity(0.12), in: Capsule())
    }
}

/// Centered loading indicator for first-screen loads.
struct LoveLoadingView: View {
    var body: some View {
        VStack(spacing: 10) {
            ProgressView().tint(LoveTheme.primaryAccessible)
            Text("common.loading")
                .font(.footnote)
                .foregroundStyle(LoveTheme.secondaryText)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// Inline error state with optional retry (first-screen failures).
struct LoveErrorView: View {
    let message: String
    var retry: (() -> Void)?

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "wifi.exclamationmark")
                .font(.title)
                .foregroundStyle(LoveTheme.rose)
            Text(message)
                .font(.footnote)
                .foregroundStyle(LoveTheme.secondaryText)
                .multilineTextAlignment(.center)
            if let retry {
                LoveSecondaryButton(titleKey: "common.retry") { retry() }
                    .frame(width: 120)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(24)
    }
}
