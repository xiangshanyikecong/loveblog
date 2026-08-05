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

import { createWatchSocket } from "./cottageWatchWs";

class FakeWebSocket {
  static OPEN = 1;
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.listeners = new Map();
    this.sent = [];
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type, handler) {
    this.listeners.set(type, handler);
  }

  emit(type, event = {}) {
    this.listeners.get(type)?.(event);
  }

  send(value) {
    this.sent.push(value);
  }

  close() {
    this.readyState = 3;
    this.emit("close", { code: 1000 });
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeWebSocket.instances.length = 0;
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("watch socket transport status", () => {
  it("reports open/reconnect callbacks and whether a command was sent", () => {
    const onOpen = vi.fn();
    const client = createWatchSocket({ onOpen });
    const ws = FakeWebSocket.instances[0];

    expect(client.send({ type: "PLAY" })).toBe(false);
    ws.readyState = FakeWebSocket.OPEN;
    ws.emit("open");

    expect(onOpen).toHaveBeenCalledOnce();
    expect(client.send({ type: "PLAY" })).toBe(true);
    expect(JSON.parse(ws.sent.at(-1))).toEqual({ type: "PLAY" });

    ws.readyState = 3;
    expect(client.send({ type: "PAUSE" })).toBe(false);
    client.close();
  });
});
