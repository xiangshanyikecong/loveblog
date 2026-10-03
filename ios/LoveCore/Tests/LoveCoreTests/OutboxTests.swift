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

    @Test("a failing item stays queued with diagnostics and never wedges the queue")
    func failureKeepsItemAndContinues() async {
        let (store, _) = makeStore()
        store.enqueue(action: "mood.upsert", payload: Data("{}".utf8), idempotencyKey: "k1")
        store.enqueue(action: "wish.create", payload: Data("{}".utf8), idempotencyKey: "k2")

        let result = await store.drain { item in
            if item.action == "mood.upsert" { throw StubError() }
        }

        #expect(result.flushedActions == ["wish.create"])
        #expect(!result.allFlushed)
        #expect(result.remainingCount == 1)

        let stuck = store.pendingItems()
        #expect(stuck.count == 1)
        #expect(stuck[0].action == "mood.upsert")
        #expect(stuck[0].attempts == 1)
        #expect(stuck[0].lastError?.contains("boom") == true)
    }

    @Test("repeated failures accumulate attempts and never discard the mutation")
    func failuresAccumulate() async {
        let (store, _) = makeStore()
        store.enqueue(action: "chat.send", payload: Data("{}".utf8), idempotencyKey: "k1")

        for _ in 0..<3 {
            _ = await store.drain { _ in throw StubError() }
        }

        let item = store.pendingItems()[0]
        #expect(item.attempts == 3)
        #expect(store.pendingCount() == 1)
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
