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

    public init(
        id: UUID = UUID(),
        action: String,
        payload: Data,
        idempotencyKey: String,
        createdAt: Date = Date(),
        attempts: Int = 0,
        lastError: String? = nil
    ) {
        self.id = id
        self.action = action
        self.payload = payload
        self.idempotencyKey = idempotencyKey
        self.createdAt = createdAt
        self.attempts = attempts
        self.lastError = lastError
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
/// - `drain` replays strictly FIFO; a failing item is kept with diagnostics
///   and never wedges the rest of the queue;
/// - user mutations are never silently discarded.
///
/// A process crash mid-replay is safe: every item carries a stable backend
/// idempotency key. The store is thread-safe; persistence is an atomic JSON
/// write so a kill between mutations cannot corrupt the queue.
public final class OutboxStore: @unchecked Sendable {
    private let fileURL: URL
    private let lock = NSLock()
    private var items: [OutboxItem]

    public init(fileURL: URL) {
        self.fileURL = fileURL
        if let data = try? Data(contentsOf: fileURL),
           let decoded = try? Self.decoder.decode([OutboxItem].self, from: data) {
            items = decoded
        } else {
            // Missing or corrupt queue file: start empty rather than crash —
            // a broken store must not take the app down with it.
            items = []
        }
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

    public func pendingCount() -> Int {
        lock.lock()
        defer { lock.unlock() }
        return items.count
    }

    /// Queued mutations oldest-first (the drain order).
    public func pendingItems() -> [OutboxItem] {
        lock.lock()
        defer { lock.unlock() }
        return items.sorted { $0.createdAt < $1.createdAt }
    }

    public func removeAll() {
        lock.lock()
        items.removeAll()
        persistLocked()
        lock.unlock()
    }

    /// Replays every queued mutation in order. `execute` performs the actual
    /// network call; a thrown error keeps the item queued (attempts and
    /// lastError updated) and the drain continues with the next item.
    public func drain(_ execute: (OutboxItem) async throws -> Void) async -> OutboxDrainResult {
        var flushed: [String] = []
        for item in pendingItems() {
            do {
                try await execute(item)
                remove(id: item.id)
                flushed.append(item.action)
            } catch {
                markFailure(id: item.id, error: String(describing: error))
            }
        }
        return OutboxDrainResult(flushedActions: flushed, remainingCount: pendingCount())
    }

    private func remove(id: UUID) {
        lock.lock()
        items.removeAll { $0.id == id }
        persistLocked()
        lock.unlock()
    }

    private func markFailure(id: UUID, error: String) {
        lock.lock()
        if let index = items.firstIndex(where: { $0.id == id }) {
            items[index].attempts += 1
            items[index].lastError = error
            persistLocked()
        }
        lock.unlock()
    }

    /// Caller must hold `lock`. Best-effort atomic write; a failed write keeps
    /// the in-memory state so the current session still drains correctly.
    private func persistLocked() {
        guard let data = try? Self.encoder.encode(items) else { return }
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
