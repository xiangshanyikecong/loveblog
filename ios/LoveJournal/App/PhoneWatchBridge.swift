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

import LoveCore

/// The iOS side of the WatchConnection link.
///
/// The watch never talks to the server (keeping session/cookie management on
/// the phone): every watch tap rides `sendMessage`/`transferUserInfo` here and
/// is posted to `/v1/cottage/taps` with the phone's session; the result rides
/// back as the sendMessage reply (or a follow-up message for the queued
/// userInfo path).
///
/// The phone pushes the love-days/nickname context through
/// `updateApplicationContext` (latest-wins, delivered on next watch wake) and
/// forwards freshly discovered partner taps so the watch can haptic.
///
/// Message keys (mirrored in `WatchLink.swift` on the watch side):
/// - context: `love_days` / `self_nickname` / `partner_nickname` / `updated_at`
/// - watch→phone tap: `watch_tap` ("tap" | "heartbeat")
/// - phone→watch tap result: `ok` / `kind` / `error` (reply or `watch_tap_result`)
/// - phone→watch partner tap: `watch_partner_tap` (`tid`/`kind`/`from_nickname`/`created_at`)
@MainActor
@Observable
final class PhoneWatchBridge: NSObject {
    private(set) var watchReachable = false

    /// Newest tap createdAt already seen (baseline after the first fetch —
    /// history is never replayed to the watch, only fresh partner taps).
    private var lastSeenTapDate: Date?

    private let api: LoveAPIClient
    private let session: SessionStore

    init(api: LoveAPIClient, session: SessionStore) {
        self.api = api
        self.session = session
        super.init()
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
    }

    // MARK: - Phone → watch context

    func pushLoveContext(days: Int, selfNickname: String, partnerNickname: String) {
        guard WCSession.isSupported() else { return }
        let context: [String: Any] = [
            "love_days": days,
            "self_nickname": selfNickname,
            "partner_nickname": partnerNickname,
            "updated_at": Date().timeIntervalSince1970,
        ]
        try? WCSession.default.updateApplicationContext(context)
    }

    /// Derives days + both nicknames from a dashboard payload (self nickname
    /// comes from the logged-in profile, the partner's is the *other* couple
    /// member).
    func syncFromDashboard(_ dashboard: ContentDTOs.Dashboard) {
        guard case .loggedIn(let profile) = session.state else { return }
        let partnerNickname = [dashboard.couple.partnerA?.nickname, dashboard.couple.partnerB?.nickname]
            .compactMap { $0 }
            .first { $0 != profile.nickname } ?? ""
        pushLoveContext(
            days: dashboard.loveClock.days,
            selfNickname: profile.nickname,
            partnerNickname: partnerNickname
        )
    }

    // MARK: - Partner tap discovery

    /// Feeds a `GET /cottage/taps/recent` result (shared with the hub banner's
    /// fetch). The first ingest only sets the baseline; later partner taps
    /// newer than the baseline are forwarded to the watch.
    func ingest(taps: [TapDTOs.Tap], myUid: String?) {
        guard let newest = taps.max(by: { $0.createdAt < $1.createdAt }) else { return }
        if let baseline = lastSeenTapDate {
            for tap in taps where tap.createdAt > baseline && tap.fromUid != myUid {
                forwardPartnerTap(tap)
            }
        }
        if lastSeenTapDate == nil || newest.createdAt > (lastSeenTapDate ?? .distantPast) {
            lastSeenTapDate = newest.createdAt
        }
    }

    /// Foreground poll (scenePhase → active): one cheap fetch keeps the watch
    /// in sync even when the user never opens the cottage tab.
    func pollPartnerTaps() async {
        guard case .loggedIn(let profile) = session.state else { return }
        guard let list = try? await api.recentTaps(limit: 10) else { return }
        ingest(taps: list.items, myUid: profile.uid)
    }

    private func forwardPartnerTap(_ tap: TapDTOs.Tap) {
        guard WCSession.isSupported() else { return }
        let payload: [String: Any] = [
            "tid": tap.tid,
            "kind": tap.kind,
            "from_nickname": tap.fromNickname,
            "created_at": tap.createdAt.timeIntervalSince1970,
        ]
        let wcSession = WCSession.default
        if wcSession.isReachable {
            wcSession.sendMessage(["watch_partner_tap": payload], replyHandler: nil) { _ in }
        } else {
            wcSession.transferUserInfo(["watch_partner_tap": payload])
        }
    }

    // MARK: - Watch tap relay

    /// Posts a watch-originated tap with the phone's session. Returns the
    /// reply dictionary for the watch (`ok`/`kind`/`error`).
    private func performTap(kind: String) async -> [String: Any] {
        do {
            let tap = try await api.sendTap(kind: kind)
            ingest(taps: [tap], myUid: tap.fromUid)
            return ["ok": true, "kind": tap.kind]
        } catch {
            return ["ok": false, "kind": kind, "error": (error as? APIError)?.message ?? "发送失败"]
        }
    }

    /// Result push for the queued (`transferUserInfo`) path, where no
    /// replyHandler exists.
    private func sendTapResult(_ result: [String: Any]) {
        guard WCSession.isSupported(), WCSession.default.isReachable else { return }
        WCSession.default.sendMessage(["watch_tap_result": result], replyHandler: nil) { _ in }
    }
}

// MARK: - WCSessionDelegate (callbacks arrive off-main)

extension PhoneWatchBridge: WCSessionDelegate {
    nonisolated func session(
        _ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?
    ) {}

    nonisolated func sessionDidBecomeInactive(_ session: WCSession) {}

    nonisolated func sessionDidDeactivate(_ session: WCSession) {
        // Re-pairing support: hand the session to the new watch.
        session.activate()
    }

    nonisolated func session(
        _ session: WCSession, didReceiveMessage message: [String: Any], replyHandler: @escaping ([String: Any]) -> Void
    ) {
        guard let kind = message["watch_tap"] as? String else {
            replyHandler([: ])
            return
        }
        Task { @MainActor in
            replyHandler(await self.performTap(kind: kind))
        }
    }

    nonisolated func session(_ session: WCSession, didReceiveUserInfo userInfo: [String: Any] = [:]) {
        guard let kind = userInfo["watch_tap"] as? String else { return }
        Task { @MainActor in
            let result = await self.performTap(kind: kind)
            self.sendTapResult(result)
        }
    }

    nonisolated func sessionReachabilityDidChange(_ session: WCSession) {
        let reachable = session.isReachable
        Task { @MainActor in
            self.watchReachable = reachable
        }
    }
}
