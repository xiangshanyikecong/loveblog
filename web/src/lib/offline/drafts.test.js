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
import { beforeEach, describe, expect, it } from "vitest";
import { IDBFactory } from "fake-indexeddb";

import { resetOfflineDbForTests } from "./db";

import {
  draftIsWorthRestoring,
  draftKeyForArticle,
  loadArticleDraft,
  removeArticleDraft,
  saveArticleDraft,
  updatedAtToMs,
} from "./drafts";

// 每个用例独立一份 IndexedDB，避免用例间串数据。
beforeEach(async () => {
  // fake-indexeddb 的全局结构允许直接重置。
  globalThis.indexedDB = new IDBFactory();
  await resetOfflineDbForTests();
});

describe("article draft persistence", () => {
  it("uses a stable key per article route", () => {
    expect(draftKeyForArticle(undefined)).toBe("article:new");
    expect(draftKeyForArticle("new")).toBe("article:new");
    expect(draftKeyForArticle(42)).toBe("article:42");
  });

  it("saves and loads a draft round-trip", async () => {
    await saveArticleDraft({
      aid: null,
      title: "Hello",
      content: "# world",
      coverUrl: "/v1/uploads/x.jpg",
      baseVersion: 3,
      serverUpdatedAt: "2026-09-27T00:00:00Z",
    });

    const draft = await loadArticleDraft("new");
    expect(draft).not.toBeNull();
    expect(draft.title).toBe("Hello");
    expect(draft.content).toBe("# world");
    expect(draft.baseVersion).toBe(3);
    expect(draft.updatedAt).toBeGreaterThan(0);
  });

  it("drops the draft when both title and content are empty", async () => {
    await saveArticleDraft({ aid: 7, title: "t", content: "c" });
    expect(await loadArticleDraft(7)).not.toBeNull();

    await saveArticleDraft({ aid: 7, title: "  ", content: "" });
    expect(await loadArticleDraft(7)).toBeNull();
  });

  it("removes the draft after a successful save", async () => {
    await saveArticleDraft({ aid: 9, title: "t", content: "c" });
    await removeArticleDraft(9);
    expect(await loadArticleDraft(9)).toBeNull();
  });
});

describe("draft restore decision", () => {
  const NOW = Date.parse("2026-09-27T12:00:00Z");

  it("restores when the server timestamp is unknown", () => {
    const draft = { updatedAt: NOW - 86400000 };
    expect(draftIsWorthRestoring(draft, null)).toBe(true);
    expect(draftIsWorthRestoring(draft, "not-a-date")).toBe(true);
  });

  it("restores when the draft is newer than the server copy", () => {
    const draft = { updatedAt: NOW, serverUpdatedAt: "2026-09-26T12:00:00Z" };
    expect(draftIsWorthRestoring(draft, "2026-09-26T12:00:00Z")).toBe(true);
  });

  it("restores when the server is unchanged since the draft started", () => {
    const serverIso = "2026-09-27T10:00:00Z";
    const draft = { updatedAt: Date.parse("2026-09-27T09:00:00Z"), serverUpdatedAt: serverIso };
    expect(draftIsWorthRestoring(draft, serverIso)).toBe(true);
  });

  it("skips the restore prompt when the server changed after the draft", () => {
    const draft = { updatedAt: Date.parse("2026-09-27T09:00:00Z"), serverUpdatedAt: "2026-09-27T08:00:00Z" };
    expect(draftIsWorthRestoring(draft, "2026-09-27T11:00:00Z")).toBe(false);
  });

  it("treats a missing draft as nothing to restore", () => {
    expect(draftIsWorthRestoring(null, "2026-09-27T11:00:00Z")).toBe(false);
  });
});

describe("updatedAtToMs", () => {
  it("parses ISO timestamps and rejects junk", () => {
    expect(updatedAtToMs("2026-09-27T00:00:00Z")).toBe(Date.parse("2026-09-27T00:00:00Z"));
    expect(updatedAtToMs(undefined)).toBe(0);
    expect(updatedAtToMs("")).toBe(0);
    expect(updatedAtToMs("junk")).toBe(0);
  });
});
