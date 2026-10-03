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

import Observation
import SwiftUI
import UIKit

import LoveCore

@MainActor
@Observable
final class CottageTapsModel {
    private(set) var loading = false
    /// Most recent tap (mine or the partner's) for the hub banner.
    private(set) var recent: TapDTOs.Tap?
    private(set) var sending = false
    var error: String?

    private let api: LoveAPIClient
    /// Optional sink (the phone-watch bridge) fed by the same fetch, so
    /// partner taps reach the watch without a second polling loop.
    var onNewTaps: ((_ taps: [TapDTOs.Tap], _ myUid: String?) -> Void)?

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh(myUid: String?) async {
        loading = true
        do {
            let list = try await api.recentTaps(limit: 5)
            recent = list.items.first
            error = nil
            onNewTaps?(list.items, myUid)
        } catch {
            // The banner is decorative on the hub; failures surface inline
            // only when the user acts (send), not on background refreshes.
        }
        loading = false
    }

    /// Returns true on success (the caller then plays haptics + animation).
    func send(kind: String) async -> Bool {
        guard !sending else { return false }
        sending = true
        defer { sending = false }
        do {
            let tap = try await api.sendTap(kind: kind)
            recent = tap
            error = nil
            return true
        } catch {
            self.error = (error as? APIError)?.message ?? String(localized: "cottage.error.generic")
            return false
        }
    }
}

/// Hub card: the latest tap between the couple plus the two send actions.
/// A successful send fires an impact haptic and a small heart burst.
struct CottageTapsCard: View {
    let model: CottageTapsModel
    let myUid: String?

    @State private var pulse = 0

    private let impact = UIImpactFeedbackGenerator(style: .medium)

    var body: some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    Label("cottage.taps.title", systemImage: "hand.tap.fill")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.text)
                    Spacer()
                    heartBurst
                }
                if let recent = model.recent {
                    recentLine(recent)
                } else {
                    Text("cottage.taps.hint")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                if let error = model.error {
                    LoveErrorBanner(message: error)
                }
                HStack(spacing: 10) {
                    tapButton(kind: "tap", titleKey: "cottage.taps.tap", icon: "hand.tap.fill")
                    tapButton(kind: "heartbeat", titleKey: "cottage.taps.heartbeat", icon: "heart.circle.fill")
                }
            }
        }
    }

    private func recentLine(_ recent: TapDTOs.Tap) -> some View {
        let action = recent.isHeartbeat
            ? String(localized: "cottage.taps.action.heartbeat \(Format.relative(recent.createdAt))")
            : String(localized: "cottage.taps.action.tap \(Format.relative(recent.createdAt))")
        return Text("cottage.taps.recent \(recent.fromNickname) \(action) \(recent.toNickname)")
            .font(.footnote)
            .foregroundStyle(LoveTheme.secondaryText)
            .lineLimit(2)
    }

    private func tapButton(kind: String, titleKey: LocalizedStringKey, icon: String) -> some View {
        Button {
            let currentModel = model
            Task {
                if await currentModel.send(kind: kind) {
                    impact.impactOccurred()
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.55)) {
                        pulse += 1
                    }
                }
            }
        } label: {
            HStack(spacing: 6) {
                if model.sending {
                    ProgressView()
                        .tint(LoveTheme.primaryAccessible)
                } else {
                    Image(systemName: icon)
                }
                Text(titleKey)
                    .font(.subheadline.weight(.semibold))
            }
            .frame(maxWidth: .infinity)
            .frame(height: 40)
        }
        .foregroundStyle(LoveTheme.primaryAccessible)
        .background(LoveTheme.primaryAccessible.opacity(0.1), in: Capsule())
        .disabled(model.sending)
    }

    /// Tiny heart burst anchored top-right; replays on every successful send.
    private var heartBurst: some View {
        ZStack {
            Image(systemName: "heart.fill")
                .font(.caption)
                .foregroundStyle(LoveTheme.rose.opacity(0.9))
                .scaleEffect(pulse % 2 == 0 ? 1 : 1.6)
                .opacity(pulse % 2 == 0 ? 1 : 0)
                .animation(.easeOut(duration: 0.45), value: pulse)
            Image(systemName: "heart.fill")
                .font(.caption2)
                .foregroundStyle(LoveTheme.peach.opacity(0.9))
                .offset(x: pulse % 2 == 0 ? 0 : 12, y: pulse % 2 == 0 ? 0 : -12)
                .opacity(pulse % 2 == 0 ? 1 : 0)
                .animation(.easeOut(duration: 0.45), value: pulse)
        }
        .accessibilityHidden(true)
    }
}
