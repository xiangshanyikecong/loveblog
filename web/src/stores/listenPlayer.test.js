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

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetchListenState: vi.fn(),
  fetchMe: vi.fn(),
  getDirectUrl: vi.fn(),
  clearDirectUrlCache: vi.fn(),
  getLyric: vi.fn(),
  socketOptions: [],
  socketHandles: []
}));

vi.mock("../lib/api", () => ({
  fetchListenState: mocks.fetchListenState,
  fetchMe: mocks.fetchMe
}));

vi.mock("../lib/cottageListenAudio", () => ({
  getDirectUrl: mocks.getDirectUrl,
  clearDirectUrlCache: mocks.clearDirectUrlCache
}));

vi.mock("../lib/cottageListenLyrics", () => ({
  getLyric: mocks.getLyric
}));

vi.mock("../lib/cottageListenWs", () => ({
  createListenSocket: vi.fn((options) => {
    const handle = {
      send: vi.fn(() => true),
      close: vi.fn(),
      get isOpen() { return true; }
    };
    mocks.socketOptions.push(options);
    mocks.socketHandles.push(handle);
    return handle;
  })
}));

import { disposeListenPlayer, useListenPlayer } from "./listenPlayer";

function emptyState() {
  return {
    event_seq: 0,
    current: {
      song_id: null,
      song_meta: null,
      paused: true,
      position_ms: 0,
      event_seq: 0,
      server_ts_ms: 0
    },
    queue: [],
    partners: []
  };
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

class FakeAudio {
  constructor() {
    this.currentTime = 0;
    this.duration = 180;
    this.src = "";
    this.listeners = new Map();
    this.play = vi.fn(() => Promise.resolve());
    this.pause = vi.fn();
    this.load = vi.fn();
    FakeAudio.instances.push(this);
  }

  addEventListener(type, handler) { this.listeners.set(type, handler); }
  removeEventListener(type) { this.listeners.delete(type); }
  removeAttribute(name) { if (name === "src") this.src = ""; }
}
FakeAudio.instances = [];

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

beforeEach(() => {
  disposeListenPlayer();
  mocks.socketOptions.length = 0;
  mocks.socketHandles.length = 0;
  FakeAudio.instances.length = 0;
  globalThis.Audio = FakeAudio;
  mocks.fetchMe.mockReset().mockResolvedValue({ uid: "me" });
  mocks.fetchListenState.mockReset().mockResolvedValue(emptyState());
  mocks.getDirectUrl.mockReset().mockResolvedValue({ url: "https://media.test/default.mp3" });
  mocks.getLyric.mockReset().mockResolvedValue({ lines: [], kind: "none" });
  mocks.clearDirectUrlCache.mockClear();
});

afterEach(() => {
  disposeListenPlayer();
  delete globalThis.Audio;
});

describe("listen player lifecycle", () => {
  it("ignores a direct URL that resolves after a newer song", async () => {
    const first = deferred();
    const second = deferred();
    mocks.getDirectUrl.mockImplementation((songId) => (
      songId === "first" ? first.promise : second.promise
    ));

    const player = useListenPlayer();
    await player.init();
    const { onEvent } = mocks.socketOptions[0];
    onEvent({
      type: "PLAY",
      event_seq: 1,
      server_ts_ms: 1,
      origin_uid: "a",
      payload: { song_id: "first", position_ms: 0, song_meta: { name: "first" } }
    });
    onEvent({
      type: "PLAY",
      event_seq: 2,
      server_ts_ms: 2,
      origin_uid: "b",
      payload: { song_id: "second", position_ms: 0, song_meta: { name: "second" } }
    });

    second.resolve({ url: "https://media.test/second.mp3" });
    await flushPromises();
    first.resolve({ url: "https://media.test/first.mp3" });
    await flushPromises();

    expect(FakeAudio.instances[0].src).toBe("https://media.test/second.mp3");
    expect(player.current.value.song_id).toBe("second");
  });

  it("does not apply a REST snapshot older than a WS event", async () => {
    const player = useListenPlayer();
    await player.init();
    const staleSnapshot = deferred();
    mocks.fetchListenState.mockReturnValueOnce(staleSnapshot.promise);

    const socketOptions = mocks.socketOptions[0];
    socketOptions.onOpen();
    socketOptions.onEvent({
      type: "PLAY",
      event_seq: 6,
      server_ts_ms: 6,
      origin_uid: "partner",
      payload: { song_id: "new", position_ms: 0, song_meta: { name: "new" } }
    });
    staleSnapshot.resolve({
      ...emptyState(),
      event_seq: 5,
      current: { ...emptyState().current, song_id: "old", paused: false, event_seq: 5 }
    });
    await flushPromises();

    expect(player.current.value.song_id).toBe("new");
  });

  it("uses the room sequence to recover queue-only events after reconnect", async () => {
    const player = useListenPlayer();
    await player.init();
    const { onEvent, onOpen } = mocks.socketOptions[0];

    onEvent({
      type: "QUEUE_APPEND",
      event_seq: 4,
      server_ts_ms: 4,
      origin_uid: "partner",
      payload: { song_id: "queued-a", song_meta: { song_id: "queued-a", name: "A", artists: [] } }
    });

    mocks.fetchListenState.mockResolvedValueOnce({
      ...emptyState(),
      event_seq: 6,
      // current.event_seq intentionally remains behind queue-only events.
      current: { ...emptyState().current, event_seq: 0 },
      queue: [{ song_id: "queued-b", name: "B", artists: [] }]
    });
    onOpen();
    await flushPromises();

    expect(player.queue.value.map((item) => item.song_id)).toEqual(["queued-b"]);
  });

  it("preserves repeated songs from distinct queue events", async () => {
    const player = useListenPlayer();
    await player.init();
    const { onEvent } = mocks.socketOptions[0];

    const payload = {
      song_id: "queued-a",
      song_meta: { song_id: "queued-a", name: "A", artists: [] }
    };
    onEvent({ type: "QUEUE_APPEND", event_seq: 1, server_ts_ms: 1, origin_uid: "a", payload });
    onEvent({ type: "QUEUE_APPEND", event_seq: 2, server_ts_ms: 2, origin_uid: "b", payload });

    expect(player.queue.value.map((item) => item.song_id)).toEqual(["queued-a", "queued-a"]);

    onEvent({
      type: "QUEUE_REMOVE",
      event_seq: 3,
      server_ts_ms: 3,
      origin_uid: "a",
      payload: { index: 1, song_id: "queued-a" }
    });

    expect(player.queue.value.map((item) => item.song_id)).toEqual(["queued-a"]);
  });

  it("closes user resources and can initialize again after logout", async () => {
    const player = useListenPlayer();
    await player.init();
    const firstAudio = FakeAudio.instances[0];
    const firstSocket = mocks.socketHandles[0];

    player.dispose();
    expect(firstAudio.pause).toHaveBeenCalled();
    expect(firstSocket.close).toHaveBeenCalledOnce();
    expect(player.current.value.song_id).toBeNull();
    expect(player.active.value).toBe(false);

    await player.init();
    expect(mocks.socketHandles).toHaveLength(2);
    expect(FakeAudio.instances).toHaveLength(2);
  });
});
