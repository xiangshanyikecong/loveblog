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

import { describe, expect, it, vi } from "vitest";

import { api, logoutApi, resolveAssetUrl, setUnauthorizedHandler } from "./api";

function rejectingAdapter(status) {
  return async (config) => Promise.reject({ config, response: { status } });
}

describe("API authentication classification", () => {
  it("bounds logout requests so an unreachable server cannot freeze navigation", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValueOnce({ data: null });

    await logoutApi();

    expect(post).toHaveBeenCalledWith("/v1/auth/logout", undefined, {
      timeout: 5000,
      skipAuthInvalidation: true
    });
    post.mockRestore();
  });

  it("does not clear the session for a content-password challenge", async () => {
    const unauthorized = vi.fn();
    setUnauthorizedHandler(unauthorized);

    await expect(api.get("/v1/articles/protected", {
      skipAuthInvalidation: true,
      adapter: rejectingAdapter(401)
    })).rejects.toBeTruthy();

    expect(unauthorized).not.toHaveBeenCalled();
  });

  it("clears the session for an ordinary expired-session response", async () => {
    const unauthorized = vi.fn();
    setUnauthorizedHandler(unauthorized);

    await expect(api.get("/v1/cottage/listen/state", {
      adapter: rejectingAdapter(401)
    })).rejects.toBeTruthy();

    expect(unauthorized).toHaveBeenCalledOnce();
  });

  it("does not treat invalid login credentials as an expired session", async () => {
    const unauthorized = vi.fn();
    setUnauthorizedHandler(unauthorized);

    await expect(api.post("/v1/auth/login", {}, {
      adapter: rejectingAdapter(401)
    })).rejects.toBeTruthy();

    expect(unauthorized).not.toHaveBeenCalled();
  });
});

describe("asset URL allowlist", () => {
  it("rejects executable and non-media data schemes", () => {
    expect(resolveAssetUrl("javascript:alert(1)")).toBe("");
    expect(resolveAssetUrl("data:text/html,<script>alert(1)</script>")).toBe("");
  });

  it("allows expected remote and inline media schemes", () => {
    expect(resolveAssetUrl("https://cdn.example.test/photo.jpg"))
      .toBe("https://cdn.example.test/photo.jpg");
    expect(resolveAssetUrl("data:image/png;base64,AA=="))
      .toBe("data:image/png;base64,AA==");
  });
});
