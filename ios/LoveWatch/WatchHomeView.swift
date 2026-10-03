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

struct WatchHomeView: View {
    @Environment(WatchLink.self) private var link

    var body: some View {
        ScrollView {
            VStack(spacing: 8) {
                if let days = link.days {
                    daysBlock(days)
                } else {
                    Text("watch.waiting")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.vertical, 6)
                }
                HeartbeatPulseView(pulse: link.pulse)
                    .padding(.bottom, 2)
                Button {
                    link.sendTap(kind: "tap")
                } label: {
                    Label("watch.tap.button", systemImage: "hand.tap.fill")
                        .frame(maxWidth: .infinity)
                }
                .tint(.pink)
                .disabled(link.sending)
                Button {
                    link.sendTap(kind: "heartbeat")
                } label: {
                    Label("watch.heartbeat.button", systemImage: "heart.circle.fill")
                        .frame(maxWidth: .infinity)
                }
                .tint(.red)
                .disabled(link.sending)
                if link.sending {
                    ProgressView()
                }
                if let status = link.statusText {
                    Text(status)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
            }
            .padding(.horizontal, 4)
        }
    }

    private func daysBlock(_ days: Int) -> some View {
        VStack(spacing: 2) {
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text("\(days)")
                    .font(.system(size: 44, weight: .bold, design: .rounded))
                    .foregroundStyle(.pink)
                    .minimumScaleFactor(0.5)
                    .lineLimit(1)
                Text("watch.days.unit")
                    .font(.headline)
                    .foregroundStyle(.secondary)
            }
            if !nicknamesLine.isEmpty {
                Text(verbatim: nicknamesLine)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
            }
            Text("watch.days.caption")
                .font(.footnote)
                .foregroundStyle(.secondary.opacity(0.8))
        }
        .frame(maxWidth: .infinity)
    }

    private var nicknamesLine: String {
        switch (link.selfNickname.isEmpty, link.partnerNickname.isEmpty) {
        case (false, false):
            return "\(link.selfNickname) ❤️ \(link.partnerNickname)"
        case (false, true):
            return link.selfNickname
        case (true, false):
            return link.partnerNickname
        default:
            return ""
        }
    }
}

/// Heartbeat animation played on incoming partner taps (and as send
/// feedback on the phone side). Re-triggers whenever `pulse` changes.
struct HeartbeatPulseView: View {
    let pulse: Int
    @State private var beating = false

    var body: some View {
        Image(systemName: "heart.fill")
            .font(.system(size: 26))
            .foregroundStyle(.pink)
            .scaleEffect(beating ? 1.4 : 1.0)
            .opacity(beating ? 0.75 : 1.0)
            .animation(.easeInOut(duration: 0.22), value: beating)
            .onChange(of: pulse) { _, _ in
                beating = true
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.24) {
                    beating = false
                }
            }
            .accessibilityHidden(true)
    }
}
