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

import Foundation
import Network
import UIKit

import LoveCore

/// Action identifiers mirrored 1:1 from Android's `SyncActions`.
enum OutboxActions {
    static let checkinCreate = "checkin.create"
    static let wishCreate = "wish.create"
    static let moodUpsert = "mood.upsert"
    static let messageCreate = "message.create"
    static let momentCreate = "moment.create"
    static let chatSend = "chat.send"
}

extension Notification.Name {
    /// Posted on the main thread after a drain flushed at least one item.
    /// `userInfo["actions"]` carries the flushed action identifiers
    /// (`[String]`) so open screens refresh only what they own.
    static let outboxDidFlush = Notification.Name("love.outbox.didFlush")
}

/// Drains the offline outbox (M6): replays queued mutations over the live API
/// with their original `Idempotency-Key`, mirroring Android's WorkManager
/// setup in spirit — triggers are connectivity recovery, app activation and
/// immediately after enqueue (which also covers post-login drains: MainTabView
/// appears right after login).
@MainActor
final class OutboxSyncer {
    private let store: OutboxStore
    private let api: LoveAPIClient
    private let monitor = NWPathMonitor()
    private var draining = false
    private var hadConnectivity = true

    /// REST route per action. The payload is already the encoded request
    /// body, so replay needs no DTO knowledge — contract drift is impossible.
    private static let routes: [String: (method: String, path: String)] = [
        OutboxActions.checkinCreate: ("POST", "/checkins"),
        OutboxActions.wishCreate: ("POST", "/cottage/wishes"),
        OutboxActions.moodUpsert: ("POST", "/cottage/mood"),
        OutboxActions.messageCreate: ("POST", "/messages"),
        OutboxActions.momentCreate: ("POST", "/timeline"),
        OutboxActions.chatSend: ("POST", "/cottage/chat/messages"),
    ]

    init(api: LoveAPIClient) {
        self.api = api
        store = OutboxStore(fileURL: Self.defaultFileURL())

        monitor.pathUpdateHandler = { [weak self] path in
            let satisfied = path.status == .satisfied
            Task { @MainActor in
                guard let self else { return }
                if satisfied && !self.hadConnectivity {
                    self.drainIfNeeded()
                }
                self.hadConnectivity = satisfied
            }
        }
        monitor.start(queue: DispatchQueue(label: "love.outbox.path-monitor"))

        NotificationCenter.default.addObserver(
            forName: UIApplication.didBecomeActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.drainIfNeeded() }
        }
    }

    var pendingCount: Int { store.pendingCount() }

    /// Queues a mutation for (re)delivery. `idempotencyKey` must be the key
    /// the caller's live attempt already used, so a replay after an ambiguous
    /// timeout cannot duplicate the write server-side.
    func enqueue(action: String, payload: Data, idempotencyKey: String) {
        store.enqueue(action: action, payload: payload, idempotencyKey: idempotencyKey)
        drainIfNeeded()
    }

    func drainIfNeeded() {
        guard !draining, store.pendingCount() > 0 else { return }
        draining = true
        Task { [weak self] in
            await self?.drain()
        }
    }

    private func drain() async {
        defer { draining = false }
        let result = await store.drain { [api] item in
            guard let route = Self.routes[item.action] else {
                // Unknown actions stay queued with diagnostics (Android
                // parity) instead of being silently discarded.
                throw APIError.decoding("未知离线操作: \(item.action)")
            }
            try await api.requestVoid(
                route.method,
                route.path,
                bodyData: item.payload,
                headers: ["Idempotency-Key": item.idempotencyKey]
            )
        }
        guard !result.flushedActions.isEmpty else { return }
        NotificationCenter.default.post(
            name: .outboxDidFlush,
            object: nil,
            userInfo: ["actions": result.flushedActions]
        )
    }

    private static func defaultFileURL() -> URL {
        let fileManager = FileManager.default
        let base = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? fileManager.temporaryDirectory
        try? fileManager.createDirectory(at: base, withIntermediateDirectories: true)
        return base.appendingPathComponent("love-outbox.json", isDirectory: false)
    }
}
