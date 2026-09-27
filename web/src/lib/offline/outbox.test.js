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

import "fake-indexeddb/auto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IDBFactory } from "fake-indexeddb";

import { resetOfflineDbForTests } from "./db";
import {
  enqueueFailedRequest,
  flushOutbox,
  listOutboxItems,
  matchQueueable,
  outboxState,
  setOutboxSender,
} from "./outbox";

function networkError(message = "network down") {
  const error = new Error(message);
  error.name = "TypeError"; // axios 网络失败的实际形态：无 response
  return error;
}

function httpError(status, data = {}) {
  const error = new Error(`HTTP ${status}`);
  error.response = { status, data, config: {} };
  return error;
}

beforeEach(async () => {
  globalThis.indexedDB = new IDBFactory();
  await resetOfflineDbForTests();
  outboxState.authPaused.value = false;
  setOutboxSender(() => Promise.reject(new Error("sender not configured in test")));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("matchQueueable", () => {
  it("matches whitelisted write operations", () => {
    expect(matchQueueable("post", "/v1/articles")?.kind).toBe("article.create");
    expect(matchQueueable("PUT", "/v1/articles/42")?.kind).toBe("article.update");
    expect(matchQueueable("delete", "/v1/timeline/m1")?.kind).toBe("moment.delete");
    expect(matchQueueable("post", "/v1/timeline/m1/comments")?.kind).toBe("moment.comment");
    expect(matchQueueable("post", "/v1/checkins")?.kind).toBe("checkin.create");
  });

  it("rejects non-whitelisted operations", () => {
    expect(matchQueueable("post", "/v1/listen/session")).toBeNull();
    expect(matchQueueable("post", "/v1/uploads/timeline")).toBeNull();
    expect(matchQueueable("get", "/v1/articles")).toBeNull();
    expect(matchQueueable("put", "/v1/albums/1")).toBeNull();
    expect(matchQueueable("post", "/v1/articles/1/comments")).toBeNull();
  });
});

describe("outbox replay engine", () => {
  it("replays a queued creation and removes the item on success", async () => {
    const send = vi.fn().mockResolvedValue({ data: { aid: "a1" } });
    setOutboxSender(send);

    const item = await enqueueFailedRequest(matchQueueable("post", "/v1/articles"), {
      method: "post",
      url: "/v1/articles",
      data: JSON.stringify({ title: "hi" }),
      headers: { "Content-Type": "application/json", "Idempotency-Key": "k1" },
      __outboxKey: "k1",
    });
    expect(item).not.toBeNull();
    expect(outboxState.pendingCount.value).toBe(1);

    await flushOutbox();

    expect(send).toHaveBeenCalledTimes(1);
    const config = send.mock.calls[0][0];
    expect(config.method).toBe("POST");
    expect(config.url).toBe("/v1/articles");
    expect(config.headers["Idempotency-Key"]).toBe("k1");
    expect(await listOutboxItems()).toHaveLength(0);
    expect(outboxState.pendingCount.value).toBe(0);
  });

  it("treats 404 on queued deletes as success", async () => {
    setOutboxSender(vi.fn().mockRejectedValue(httpError(404, { detail: "gone" })));

    await enqueueFailedRequest(matchQueueable("delete", "/v1/timeline/m9"), {
      method: "delete",
      url: "/v1/timeline/m9",
      data: null,
      headers: {},
    });
    await flushOutbox();

    expect(await listOutboxItems()).toHaveLength(0);
  });

  it("dead-letters non-retryable 4xx validation failures", async () => {
    setOutboxSender(vi.fn().mockRejectedValue(httpError(422, { detail: "bad" })));

    await enqueueFailedRequest(matchQueueable("post", "/v1/checkins"), {
      method: "post",
      url: "/v1/checkins",
      data: JSON.stringify({ mood: "x" }),
      headers: {},
    });
    await flushOutbox();

    const items = await listOutboxItems();
    expect(items).toHaveLength(1);
    expect(items[0].status).toBe("dead");
    expect(items[0].lastError).toBe("HTTP 422");
  });

  it("pauses the whole queue on 401 and keeps the item", async () => {
    setOutboxSender(vi.fn().mockRejectedValue(httpError(401)));

    await enqueueFailedRequest(matchQueueable("post", "/v1/timeline"), {
      method: "post",
      url: "/v1/timeline",
      data: JSON.stringify({ content: "hi" }),
      headers: {},
    });
    await flushOutbox();

    expect(outboxState.authPaused.value).toBe(true);
    const items = await listOutboxItems();
    expect(items).toHaveLength(1);
    expect(items[0].status).toBe("pending");
  });

  it("backs off on network failures and dead-letters after max attempts", async () => {
    const send = vi.fn().mockRejectedValue(networkError());
    setOutboxSender(send);

    await enqueueFailedRequest(matchQueueable("post", "/v1/timeline"), {
      method: "post",
      url: "/v1/timeline",
      data: JSON.stringify({ content: "hi" }),
      headers: {},
    });

    // 连续 8 次网络失败 → 第 8 次后转死信。
    for (let round = 0; round < 8; round += 1) {
      const items = await listOutboxItems();
      // 绕过退避等待：直接把 nextAttemptAt 清零模拟时间流逝。
      const { offlineStore } = await import("./db");
      const store = await offlineStore("outbox");
      await store.put({ ...items[0], nextAttemptAt: 0 });
      await flushOutbox();
    }

    const items = await listOutboxItems();
    expect(items).toHaveLength(1);
    expect(items[0].status).toBe("dead");
    expect(items[0].attempts).toBe(8);
    expect(send).toHaveBeenCalledTimes(8);
  });

  it("resolves 409 on update as already-applied when server content matches", async () => {
    const payload = {
      title: "same title",
      blocks: [{ block_type: "Paragraph", content: "same", sort_order: 0 }],
    };
    const send = vi.fn((config) => {
      if (config.method === "GET") {
        return Promise.resolve({ data: { title: "same title", __etag: 5, blocks: payload.blocks } });
      }
      return Promise.reject(httpError(409, { detail: "article_version_conflict" }));
    });
    setOutboxSender(send);

    await enqueueFailedRequest(matchQueueable("put", "/v1/articles/aa"), {
      method: "put",
      url: "/v1/articles/aa",
      data: JSON.stringify(payload),
      headers: { "If-Match": "4" },
    });
    await flushOutbox();

    expect(await listOutboxItems()).toHaveLength(0);
  });

  it("marks a real 409 conflict when server content differs", async () => {
    const send = vi.fn((config) => {
      if (config.method === "GET") {
        return Promise.resolve({ data: { title: "partner changed", blocks: [], __etag: 6 } });
      }
      return Promise.reject(httpError(409, { detail: "article_version_conflict" }));
    });
    setOutboxSender(send);

    await enqueueFailedRequest(matchQueueable("put", "/v1/articles/aa"), {
      method: "put",
      url: "/v1/articles/aa",
      data: JSON.stringify({ title: "mine", blocks: [] }),
      headers: { "If-Match": "4" },
    });
    await flushOutbox();

    const items = await listOutboxItems();
    expect(items).toHaveLength(1);
    expect(items[0].status).toBe("conflict");
  });

  it("does not enqueue FormData bodies", async () => {
    const form = new FormData();
    form.append("file", "x");
    const item = await enqueueFailedRequest(matchQueueable("post", "/v1/timeline"), {
      method: "post",
      url: "/v1/timeline",
      data: form,
      headers: {},
    });
    expect(item).toBeNull();
    expect(await listOutboxItems()).toHaveLength(0);
  });
});
