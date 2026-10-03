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

/// One queued offline mutation. The payload is the pre-encoded JSON request
/// body exactly as the live attempt sent it, paired with the idempotency key
/// of that attempt — so a replay after an ambiguous timeout can never
/// duplicate the write server-side.
public struct OutboxItem: Codable, Equatable, Identifiable, Sendable {
    public let id: UUID
    public let action: String
    public let payload: Data
    public let idempotencyKey: String
    public let createdAt: Date
    public var attempts: Int
    public var lastError: String?
    /// Earliest moment this mutation may be replayed (retry backoff).
    public var nextAttemptAt: Date
    /// Terminal state: kept on disk for diagnostics, never replayed again.
    public var dead: Bool

    public init(
        id: UUID = UUID(),
        action: String,
        payload: Data,
        idempotencyKey: String,
        createdAt: Date = Date(),
        attempts: Int = 0,
        lastError: String? = nil,
        nextAttemptAt: Date = Date(timeIntervalSince1970: 0),
        dead: Bool = false
    ) {
        self.id = id
        self.action = action
        self.payload = payload
        self.idempotencyKey = idempotencyKey
        self.createdAt = createdAt
        self.attempts = attempts
        self.lastError = lastError
        self.nextAttemptAt = nextAttemptAt
        self.dead = dead
    }
}

/// Summary of one drain pass.
public struct OutboxDrainResult: Equatable, Sendable {
    /// Action identifiers flushed in order, e.g. `["checkin.create", …]`.
    public let flushedActions: [String]
    public let remainingCount: Int

    public init(flushedActions: [String], remainingCount: Int) {
        self.flushedActions = flushedActions
        self.remainingCount = remainingCount
    }

    public var allFlushed: Bool { remainingCount == 0 }
}

/// Durable offline mutation queue (M6), mirroring the Android `SyncEngine`
/// contract:
///
/// - `enqueue` persists to disk before the UI may report success;
/// - `drain` replays strictly FIFO; a failing item is classified by
///   `OutboxRetryPolicy` — temporary failures back off, permanent ones (and
///   exhausted retries) dead-letter — so the queue can never wedge nor
///   replay a poisoned entry forever;
/// - the whole queue belongs to one account `scope` (`server|uid`, the iOS
///   counterpart of Android's `ServerConfig.dataScope`): claiming a
///   different scope wipes leftovers, so one partner's queued mutations can
///   never replay into the other's account on a shared device;
/// - user mutations are never silently discarded (dead letters stay on disk).
///
/// A process crash mid-replay is safe: every item carries a stable backend
/// idempotency key. The store is thread-safe; persistence is an atomic JSON
/// write so a kill between mutations cannot corrupt the queue.
public final class OutboxStore: @unchecked Sendable {
    private let fileURL: URL
    private let lock = NSLock()
    private var scope: String
    private var items: [OutboxItem]

    /// On-disk shape: the owning account scope plus the queued mutations.
    /// (Pre-envelope files stored a bare array; they fail to decode and start
    /// empty — the same recovery contract as a corrupt file.)
    private struct Snapshot: Codable {
        var scope: String
        var items: [OutboxItem]
    }

    public init(fileURL: URL) {
        self.fileURL = fileURL
        if let data = try? Data(contentsOf: fileURL),
           let snapshot = try? Self.decoder.decode(Snapshot.self, from: data) {
            scope = snapshot.scope
            items = snapshot.items
        } else {
            // Missing or corrupt queue file: start empty rather than crash —
            // a broken store must not take the app down with it.
            scope = ""
            items = []
        }
    }

    /// Binds the queue to one account scope. When the scope changes
    /// (different user, different server) the previous owner's leftovers are
    /// wiped: they could never be attributed or delivered under the current
    /// credentials, and replaying them would write into the wrong account.
    public func claim(scope: String) {
        lock.lock()
        if self.scope != scope {
            self.scope = scope
            items.removeAll()
            persistLocked()
        }
        lock.unlock()
    }

    /// Appends a mutation and persists it synchronously.
    @discardableResult
    public func enqueue(action: String, payload: Data, idempotencyKey: String) -> OutboxItem {
        let item = OutboxItem(action: action, payload: payload, idempotencyKey: idempotencyKey)
        lock.lock()
        items.append(item)
        persistLocked()
        lock.unlock()
        return item
    }

    /// Mutations not yet dead-lettered (due now or backing off).
    public func pendingCount() -> Int {
        lock.lock()
        defer { lock.unlock() }
        return items.count { !$0.dead }
    }

    /// Queued mutations oldest-first (the replay order); dead letters excluded.
    public func pendingItems() -> [OutboxItem] {
        lock.lock()
        defer { lock.unlock() }
        return items.filter { !$0.dead }.sorted { $0.createdAt < $1.createdAt }
    }

    /// Earliest `nextAttemptAt` among live (non-dead) items, so callers can
    /// wake up exactly when the next retry comes due. Nil when nothing waits.
    public func nextDueDate() -> Date? {
        lock.lock()
        defer { lock.unlock() }
        return items.filter { !$0.dead }.map(\.nextAttemptAt).min()
    }

    public func removeAll() {
        lock.lock()
        items.removeAll()
        scope = ""
        persistLocked()
        lock.unlock()
    }

    /// Replays every due mutation in order until no due work is left — so a
    /// mutation enqueued while a drain is in flight is picked up by the next
    /// pass instead of waiting for the next app activation. `execute` performs
    /// the actual network call; a thrown error keeps the item on disk (dead or
    /// rescheduled with diagnostics) and the drain continues with the next.
    /// `now` is injectable so tests can advance the retry clock.
    public func drain(
        _ execute: (OutboxItem) async throws -> Void,
        now: Date = Date()
    ) async -> OutboxDrainResult {
        var flushed: [String] = []
        while true {
            let due = dueItems(now: now)
            guard !due.isEmpty else { break }
            for item in due {
                do {
                    try await execute(item)
                    remove(id: item.id)
                    flushed.append(item.action)
                } catch {
                    handleFailure(item, error: error, now: now)
                }
            }
        }
        return OutboxDrainResult(flushedActions: flushed, remainingCount: pendingCount())
    }

    private func dueItems(now: Date) -> [OutboxItem] {
        lock.lock()
        defer { lock.unlock() }
        return items
            .filter { !$0.dead && $0.nextAttemptAt <= now }
            .sorted { $0.createdAt < $1.createdAt }
    }

    private func remove(id: UUID) {
        lock.lock()
        items.removeAll { $0.id == id }
        persistLocked()
        lock.unlock()
    }

    private func handleFailure(_ item: OutboxItem, error: Error, now: Date) {
        switch OutboxRetryPolicy.classify(error) {
        case .retryable(let reason):
            let attempts = item.attempts + 1
            if attempts >= OutboxRetryPolicy.maxAttempts {
                markDead(id: item.id, "exhausted after \(attempts) attempts: \(reason)")
            } else {
                reschedule(
                    id: item.id,
                    attempts: attempts,
                    error: reason,
                    nextAttemptAt: now.addingTimeInterval(
                        OutboxRetryPolicy.backoffSeconds(attemptsSoFar: attempts)
                    )
                )
            }
        case .permanent(let reason):
            markDead(id: item.id, reason)
        }
    }

    private func reschedule(id: UUID, attempts: Int, error: String, nextAttemptAt: Date) {
        lock.lock()
        if let index = items.firstIndex(where: { $0.id == id }) {
            items[index].attempts = attempts
            items[index].lastError = error
            items[index].nextAttemptAt = nextAttemptAt
            persistLocked()
        }
        lock.unlock()
    }

    private func markDead(id: UUID, _ reason: String) {
        lock.lock()
        if let index = items.firstIndex(where: { $0.id == id }) {
            items[index].dead = true
            items[index].lastError = reason
            persistLocked()
        }
        lock.unlock()
    }

    /// Caller must hold `lock`. Best-effort atomic write; a failed write keeps
    /// the in-memory state so the current session still drains correctly.
    private func persistLocked() {
        guard let data = try? Self.encoder.encode(Snapshot(scope: scope, items: items)) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }

    private static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()

    private static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()
}
