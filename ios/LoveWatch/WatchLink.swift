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
import Observation
import WatchConnectivity
import WatchKit
import WidgetKit

import LoveCore

/// The watch side of the WatchConnection link.
///
/// The watch never talks to the server: taps ride `sendMessage` (with the
/// phone's reply carrying the POST result) or `transferUserInfo` when the
/// phone is unreachable, in which case the result arrives later as a
/// `watch_tap_result` message. Incoming partner taps (forwarded by the
/// phone's `PhoneWatchBridge`) trigger a notification haptic plus the
/// heartbeat animation; a tid-based throttle keeps replays quiet.
///
/// Message keys (mirrored in `PhoneWatchBridge.swift` on the phone side):
/// - context: `love_days` / `self_nickname` / `partner_nickname` / `updated_at`
/// - watch→phone tap: `watch_tap` ("tap" | "heartbeat")
/// - phone→watch tap result: `ok` / `kind` / `error` (reply or `watch_tap_result`)
/// - phone→watch partner tap: `watch_partner_tap` (`tid`/`kind`/`from_nickname`/`created_at`)
@MainActor
@Observable
final class WatchLink: NSObject {
    private(set) var days: Int?
    private(set) var selfNickname = ""
    private(set) var partnerNickname = ""
    private(set) var sending = false
    private(set) var statusText: String?
    /// Bumped on every incoming partner tap; drives the heartbeat animation.
    private(set) var pulse = 0

    private var lastIncomingTapId: String?
    private var lastIncomingAt: Date?

    /// Minimum spacing between incoming-tap haptics (replayed contexts or a
    /// phone retry must not machine-gun the wrist).
    private static let incomingThrottle: TimeInterval = 5

    override init() {
        super.init()
        // Instant UI from the cached snapshot while the session wakes up.
        if let snapshot = WatchLoveSnapshot.load() {
            days = snapshot.days
            selfNickname = snapshot.selfNickname
            partnerNickname = snapshot.partnerNickname
        }
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
        // The phone may have pushed a newer context while we were asleep.
        applyContext(WCSession.default.receivedApplicationContext)
    }

    // MARK: Watch → phone taps

    func sendTap(kind: String) {
        guard !sending else { return }
        sending = true
        statusText = nil
        let session = WCSession.default
        guard session.isReachable else {
            // Queued path: the phone posts it when connectivity returns and
            // acknowledges via a follow-up `watch_tap_result` message.
            session.transferUserInfo(["watch_tap": kind])
            sending = false
            statusText = String(localized: "watch.status.queued")
            return
        }
        session.sendMessage(["watch_tap": kind]) { [weak self] reply in
            Task { @MainActor in
                self?.handleTapResult(reply)
            }
        } errorHandler: { [weak self] _ in
            // Live send failed: fall back to the queued path.
            session.transferUserInfo(["watch_tap": kind])
            Task { @MainActor in
                self?.sending = false
                self?.statusText = String(localized: "watch.status.queued")
            }
        }
    }

    private func handleTapResult(_ result: [String: Any]) {
        sending = false
        if let ok = result["ok"] as? Bool, ok {
            statusText = String(localized: "watch.status.sent")
            WKInterfaceDevice.current().play(.success)
        } else {
            statusText = (result["error"] as? String) ?? String(localized: "watch.status.failed")
            WKInterfaceDevice.current().play(.failure)
        }
    }

    // MARK: Phone → watch payloads

    private func applyContext(_ context: [String: Any]) {
        guard let newDays = context["love_days"] as? Int else { return }
        days = newDays
        selfNickname = context["self_nickname"] as? String ?? selfNickname
        partnerNickname = context["partner_nickname"] as? String ?? partnerNickname
        WatchLoveSnapshot(
            days: newDays,
            selfNickname: selfNickname,
            partnerNickname: partnerNickname,
            updatedAt: Date()
        ).save()
        WidgetCenter.shared.reloadAllTimelines()
    }

    private func handlePartnerTap(_ payload: [String: Any]) {
        let tid = payload["tid"] as? String ?? UUID().uuidString
        let now = Date()
        // Throttle: dedupe by tid and clamp the minimum spacing between
        // distinct haptic events.
        if tid == lastIncomingTapId {
            return
        }
        if let last = lastIncomingAt, now.timeIntervalSince(last) < Self.incomingThrottle {
            lastIncomingTapId = tid
            return
        }
        lastIncomingTapId = tid
        lastIncomingAt = now

        let kind = payload["kind"] as? String ?? "tap"
        let from = payload["from_nickname"] as? String ?? ""
        statusText = from.isEmpty
            ? (kind == "heartbeat"
                ? String(localized: "watch.tap.heartbeat.anon")
                : String(localized: "watch.tap.anon"))
            : (kind == "heartbeat"
                ? String(localized: "watch.tap.heartbeat \(from)")
                : String(localized: "watch.tap \(from)"))
        pulse += 1
        WKInterfaceDevice.current().play(.notification)
    }
}

// MARK: - WCSessionDelegate (callbacks arrive off-main)

extension WatchLink: WCSessionDelegate {
    nonisolated func session(
        _ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?
    ) {
        Task { @MainActor in
            self.applyContext(session.receivedApplicationContext)
        }
    }

    nonisolated func session(_ session: WCSession, didReceiveMessage message: [String: Any]) {
        let partnerTap = message["watch_partner_tap"] as? [String: Any]
        let tapResult = message["watch_tap_result"] as? [String: Any]
        Task { @MainActor in
            if let tapResult {
                self.handleTapResult(tapResult)
            }
            if let partnerTap {
                self.handlePartnerTap(partnerTap)
            }
        }
    }

    nonisolated func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String: Any]) {
        Task { @MainActor in
            self.applyContext(applicationContext)
        }
    }

    nonisolated func session(_ session: WCSession, didReceiveUserInfo userInfo: [String: Any] = [:]) {
        let partnerTap = userInfo["watch_partner_tap"] as? [String: Any]
        let tapResult = userInfo["watch_tap_result"] as? [String: Any]
        Task { @MainActor in
            if let tapResult {
                self.handleTapResult(tapResult)
            }
            if let partnerTap {
                self.handlePartnerTap(partnerTap)
            }
        }
    }
}
