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

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetchMe: vi.fn(),
  logoutApi: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
  disposeListenPlayer: vi.fn()
}));

vi.mock("../lib/api", () => ({
  fetchMe: mocks.fetchMe,
  logoutApi: mocks.logoutApi,
  setUnauthorizedHandler: mocks.setUnauthorizedHandler
}));

vi.mock("./listenPlayer", () => ({
  disposeListenPlayer: mocks.disposeListenPlayer
}));

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: vi.fn((key) => values.get(key) ?? null),
    setItem: vi.fn((key, value) => values.set(key, String(value))),
    removeItem: vi.fn((key) => values.delete(key))
  };
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

async function loadAuth(initialStorage = {}) {
  vi.resetModules();
  vi.stubGlobal("localStorage", memoryStorage(initialStorage));
  vi.stubGlobal("window", { addEventListener: vi.fn() });
  return import("./auth.js");
}

beforeEach(() => {
  mocks.fetchMe.mockReset();
  mocks.logoutApi.mockReset();
  mocks.setUnauthorizedHandler.mockReset();
  mocks.disposeListenPlayer.mockReset();
});

describe("auth logout lifecycle", () => {
  it("keeps a tombstone after an offline logout so init cannot restore the cookie session", async () => {
    mocks.logoutApi.mockRejectedValueOnce(new Error("offline"));
    const { useAuth } = await loadAuth({ love_is_auth: "true", love_role: "PartnerA" });
    const auth = useAuth();

    await expect(auth.logout()).resolves.toBe(false);
    expect(localStorage.getItem("love_logout_pending")).toBe("true");

    mocks.fetchMe.mockResolvedValue({ role: "PartnerA" });
    mocks.logoutApi.mockRejectedValueOnce(new Error("still offline"));
    await expect(auth.initAuth()).resolves.toBe(false);
    expect(mocks.fetchMe).not.toHaveBeenCalled();
    expect(auth.token.value).toBe("");
  });

  it("clears the tombstone after a later server logout succeeds", async () => {
    mocks.logoutApi.mockResolvedValueOnce(undefined);
    const { useAuth } = await loadAuth({ love_logout_pending: "true" });
    const auth = useAuth();

    await expect(auth.initAuth()).resolves.toBe(false);
    expect(localStorage.getItem("love_logout_pending")).toBeNull();
    expect(mocks.fetchMe).not.toHaveBeenCalled();
  });

  it("allows an explicit new login to replace a pending logout", async () => {
    const { useAuth } = await loadAuth({ love_logout_pending: "true" });
    const auth = useAuth();

    auth.setAuthToken("legacy", "PartnerB", { newSession: true });
    expect(localStorage.getItem("love_logout_pending")).toBeNull();
    expect(auth.token.value).toBe("legacy");
  });

  it("does not restore auth when an older me request resolves after logout", async () => {
    const me = deferred();
    mocks.fetchMe.mockReturnValueOnce(me.promise);
    mocks.logoutApi.mockResolvedValueOnce(undefined);
    const { useAuth } = await loadAuth({ love_is_auth: "true", love_role: "PartnerA" });
    const auth = useAuth();

    const initializing = auth.initAuth();
    await auth.logout();
    me.resolve({ role: "PartnerA" });

    await expect(initializing).resolves.toBe(false);
    expect(auth.token.value).toBe("");
  });

  it("waits for an in-flight logout before allowing a new login request", async () => {
    const serverLogout = deferred();
    mocks.logoutApi.mockReturnValueOnce(serverLogout.promise);
    const { useAuth } = await loadAuth({ love_is_auth: "true", love_role: "PartnerA" });
    const auth = useAuth();

    const loggingOut = auth.logout();
    let prepared = false;
    const preparing = auth.prepareForLogin().then(() => { prepared = true; });
    await Promise.resolve();
    expect(prepared).toBe(false);

    serverLogout.resolve();
    await Promise.all([loggingOut, preparing]);
    expect(prepared).toBe(true);
  });

  it("does not allow a new login while the previous server logout is unconfirmed", async () => {
    mocks.logoutApi.mockRejectedValueOnce(new Error("timeout"));
    const { useAuth } = await loadAuth({ love_logout_pending: "true" });
    const auth = useAuth();

    await expect(auth.prepareForLogin()).resolves.toBe(false);
    expect(localStorage.getItem("love_logout_pending")).toBe("true");
  });
});
