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
import Testing

@testable import LoveCore

private struct StubError: Error, CustomStringConvertible {
    var description: String { "boom" }
}

@Suite("OutboxStore")
struct OutboxTests {
    private func makeStore() -> (store: OutboxStore, url: URL) {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("outbox-tests-\(UUID().uuidString).json")
        return (OutboxStore(fileURL: url), url)
    }

    @Test("enqueue persists across store instances (app restart)")
    func persistenceAcrossRestart() async {
        let (store, url) = makeStore()
        store.enqueue(
            action: "checkin.create",
            payload: Data("{}".utf8),
            idempotencyKey: "key-1"
        )

        let revived = OutboxStore(fileURL: url)
        let pending = revived.pendingItems()
        #expect(pending.count == 1)
        #expect(pending[0].action == "checkin.create")
        #expect(pending[0].idempotencyKey == "key-1")
        #expect(pending[0].payload == Data("{}".utf8))
    }

    @Test("corrupt queue file starts empty instead of crashing")
    func corruptFileRecovers() {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("outbox-tests-corrupt-\(UUID().uuidString).json")
        try? Data("not json at all".utf8).write(to: url)

        let store = OutboxStore(fileURL: url)
        #expect(store.pendingCount() == 0)
    }

    @Test("legacy bare-array queue file starts empty (unattributable scope)")
    func legacyFileStartsEmpty() {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("outbox-tests-legacy-\(UUID().uuidString).json")
        try? Data(#"[{"id":"not-a-scope-envelope"}]"#.utf8).write(to: url)

        #expect(OutboxStore(fileURL: url).pendingCount() == 0)
    }

    @Test("claiming another scope wipes the previous owner's leftovers")
    func claimScopesTheQueue() {
        let (store, url) = makeStore()
        store.claim(scope: "https://a.example|u1")
        store.enqueue(action: "wish.create", payload: Data("{}".utf8), idempotencyKey: "k1")

        // Re-claiming the owning scope keeps the queued mutation.
        store.claim(scope: "https://a.example|u1")
        #expect(store.pendingCount() == 1)

        // A different account (or server) wipes it instead of replaying it
        // into the wrong account.
        store.claim(scope: "https://b.example|u2")
        #expect(store.pendingCount() == 0)

        // The wipe persists.
        let revived = OutboxStore(fileURL: url)
        revived.claim(scope: "https://b.example|u2")
        #expect(revived.pendingCount() == 0)
    }

    @Test("drain flushes FIFO and reports flushed actions")
    func drainOrderAndResult() async {
        let (store, _) = makeStore()
        store.enqueue(action: "wish.create", payload: Data("{}".utf8), idempotencyKey: "k1")
        store.enqueue(action: "checkin.create", payload: Data("{}".utf8), idempotencyKey: "k2")

        var replayed: [String] = []
        let result = await store.drain { item in
            replayed.append(item.action)
        }

        #expect(replayed == ["wish.create", "checkin.create"])
        #expect(result.flushedActions == ["wish.create", "checkin.create"])
        #expect(result.allFlushed)
        #expect(store.pendingCount() == 0)
    }

    @Test("a retryable failure backs off with diagnostics and never wedges the queue")
    func failureKeepsItemAndContinues() async {
        let (store, _) = makeStore()
        store.enqueue(action: "mood.upsert", payload: Data("{}".utf8), idempotencyKey: "k1")
        store.enqueue(action: "wish.create", payload: Data("{}".utf8), idempotencyKey: "k2")

        let now = Date()
        let result = await store.drain({ item in
            if item.action == "mood.upsert" { throw APIError.transport(.offline) }
        }, now: now)

        #expect(result.flushedActions == ["wish.create"])
        #expect(!result.allFlushed)
        #expect(result.remainingCount == 1)

        let stuck = store.pendingItems()
        #expect(stuck.count == 1)
        #expect(stuck[0].action == "mood.upsert")
        #expect(stuck[0].attempts == 1)
        #expect(stuck[0].lastError != nil)
        // Still inside the backoff window: an immediate re-drain skips it.
        var replayed = 0
        _ = await store.drain({ _ in replayed += 1 }, now: now)
        #expect(replayed == 0)
        // The retry wake-up can be scheduled exactly at the backoff expiry.
        #expect(store.nextDueDate() != nil && store.nextDueDate()! > now)
    }

    @Test("a permanent failure dead-letters instead of retrying forever")
    func permanentFailureDeadLetters() async {
        let (store, _) = makeStore()
        store.enqueue(action: "chat.send", payload: Data("{}".utf8), idempotencyKey: "k1")

        _ = await store.drain { _ in throw APIError.http(status: 422, detail: nil) }

        // Dead letters are terminal: excluded from pending work and never
        // re-executed, but kept on disk for diagnostics.
        #expect(store.pendingCount() == 0)
        #expect(store.pendingItems().isEmpty)
    }

    @Test("exhausted retries dead-letter instead of replaying forever")
    func exhaustedRetriesDeadLetter() async {
        let (store, _) = makeStore()
        store.enqueue(action: "chat.send", payload: Data("{}".utf8), idempotencyKey: "k1")

        // Advance the clock far past every backoff window for each attempt.
        var clock = Date()
        for _ in 0..<OutboxRetryPolicy.maxAttempts {
            clock = clock.addingTimeInterval(7 * 24 * 3600)
            _ = await store.drain({ _ in throw APIError.transport(.timedOut) }, now: clock)
        }

        #expect(store.pendingCount() == 0)
    }

    @Test("repeated retryable failures accumulate attempts once backoff elapses")
    func failuresAccumulate() async {
        let (store, _) = makeStore()
        store.enqueue(action: "chat.send", payload: Data("{}".utf8), idempotencyKey: "k1")

        let start = Date()
        // 300s steps clear every backoff window deterministically (attempt 1
        // backs off ≤72s, attempt 2 ≤144s) despite the ±20% jitter.
        for step in 0..<3 {
            _ = await store.drain(
                { _ in throw APIError.transport(.offline) },
                now: start.addingTimeInterval(TimeInterval(step) * 300)
            )
        }

        let item = store.pendingItems()[0]
        #expect(item.attempts == 3)
        #expect(store.pendingCount() == 1)
    }

    @Test("a mutation enqueued mid-drain is flushed by the follow-up pass")
    func enqueueDuringDrainIsFlushed() async {
        let (store, _) = makeStore()
        store.enqueue(action: "wish.create", payload: Data("{}".utf8), idempotencyKey: "k1")

        let result = await store.drain { item in
            if item.idempotencyKey == "k1" {
                store.enqueue(
                    action: "checkin.create",
                    payload: Data("{}".utf8),
                    idempotencyKey: "k2"
                )
            }
        }

        #expect(result.flushedActions == ["wish.create", "checkin.create"])
        #expect(store.pendingCount() == 0)
    }

    @Test("idempotency key survives restart unchanged")
    func keyIsStable() async {
        let (store, url) = makeStore()
        store.enqueue(
            action: "message.create",
            payload: Data("{}".utf8),
            idempotencyKey: "stable-key"
        )

        let revived = OutboxStore(fileURL: url)
        #expect(revived.pendingItems()[0].idempotencyKey == "stable-key")
    }

    @Test("removeAll clears the queue on disk")
    func removeAllPersists() async {
        let (store, url) = makeStore()
        store.enqueue(action: "wish.create", payload: Data("{}".utf8), idempotencyKey: "k1")
        store.removeAll()

        #expect(OutboxStore(fileURL: url).pendingCount() == 0)
    }
}

@Suite("OutboxRetryPolicy")
struct OutboxRetryPolicyTests {
    private func isRetryable(_ error: Error) -> Bool {
        if case .retryable = OutboxRetryPolicy.classify(error) { return true }
        return false
    }

    @Test("transport-level and server-side hiccups are retryable")
    func retryableClassification() {
        #expect(isRetryable(APIError.transport(.offline)))
        #expect(isRetryable(APIError.transport(.timedOut)))
        #expect(isRetryable(APIError.transport(.cannotReachHost)))
        #expect(isRetryable(APIError.serverNotConfigured))
        #expect(isRetryable(APIError.http(status: 408, detail: nil)))
        #expect(isRetryable(APIError.http(status: 429, detail: nil)))
        #expect(isRetryable(APIError.http(status: 500, detail: nil)))
        #expect(isRetryable(APIError.http(status: 503, detail: nil)))
    }

    @Test("client-side and 4xx failures are permanent")
    func permanentClassification() {
        #expect(!isRetryable(APIError.http(status: 400, detail: nil)))
        #expect(!isRetryable(APIError.http(status: 401, detail: nil)))
        #expect(!isRetryable(APIError.http(status: 403, detail: nil)))
        #expect(!isRetryable(APIError.http(status: 413, detail: nil)))
        #expect(!isRetryable(APIError.http(status: 422, detail: nil)))
        #expect(!isRetryable(APIError.decoding("payload drift")))
        #expect(!isRetryable(StubError()))
    }

    @Test("backoff grows exponentially, is jittered and capped")
    func backoffBounds() {
        let first = OutboxRetryPolicy.backoffSeconds(attemptsSoFar: 1)
        #expect(first >= 48 && first <= 72)

        // Far past the shift range: capped at ~6h, still jittered ±20%.
        let capped = OutboxRetryPolicy.backoffSeconds(attemptsSoFar: 30)
        #expect(capped >= 6 * 3600 * 0.8 && capped <= 6 * 3600 * 1.2)

        // The floor keeps a jittered first retry from firing too soon.
        #expect(OutboxRetryPolicy.backoffSeconds(attemptsSoFar: 1) >= 30)
    }
}
