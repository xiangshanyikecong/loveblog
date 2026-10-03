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

import {
  aiGenerateQuestions,
  aiMonthlyReport,
  aiPolishArticle,
  aiSearchArticles,
  api,
  fetchAiStatus,
  fetchCottageAchievements,
  fetchRecentCottageTaps,
  logoutApi,
  resolveAssetUrl,
  sendCottageTap,
  setUnauthorizedHandler
} from "./api";

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

describe("cottage achievements & taps endpoints", () => {
  it("loads the couple achievements summary", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValueOnce({ data: { badges: [] } });

    await fetchCottageAchievements();

    expect(get).toHaveBeenCalledWith("/v1/cottage/achievements");
    get.mockRestore();
  });

  it("posts a tap with the picked kind", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValueOnce({ data: { tid: "t1" } });

    await sendCottageTap("heartbeat");

    expect(post).toHaveBeenCalledWith("/v1/cottage/taps", { kind: "heartbeat" });
    post.mockRestore();
  });

  it("passes the limit to the recent taps feed", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValueOnce({ data: { items: [], total_kept: 0 } });

    await fetchRecentCottageTaps(30);

    expect(get).toHaveBeenCalledWith("/v1/cottage/taps/recent", { params: { limit: 30 } });
    get.mockRestore();
  });
});

describe("AI assist endpoints", () => {
  it("probes AI availability to drive UI gating", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValueOnce({ data: { enabled: false, features: [] } });

    await fetchAiStatus();

    expect(get).toHaveBeenCalledWith("/v1/ai/status");
    get.mockRestore();
  });

  it("sends article polish requests with content and mode", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValueOnce({ data: { text: "润色后的正文" } });

    await aiPolishArticle("原始正文", "continue");

    expect(post).toHaveBeenCalledWith("/v1/ai/article/polish", {
      content: "原始正文",
      mode: "continue"
    });
    post.mockRestore();
  });

  it("sends semantic search queries with a top_k cap", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValueOnce({ data: { results: [] } });

    await aiSearchArticles("海边的日落", 8);

    expect(post).toHaveBeenCalledWith("/v1/ai/article/search", {
      query: "海边的日落",
      top_k: 8
    });
    post.mockRestore();
  });

  it("requests the AI narrative for a specific month", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValueOnce({ data: { text: "这个月……" } });

    await aiMonthlyReport(2026, 10);

    expect(post).toHaveBeenCalledWith("/v1/ai/report/monthly", { year: 2026, month: 10 });
    post.mockRestore();
  });

  it("asks the AI for a batch of daily questions", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValueOnce({ data: { questions: [] } });

    await aiGenerateQuestions();

    expect(post).toHaveBeenCalledWith("/v1/ai/questions/generate", { count: 3 });
    post.mockRestore();
  });
});
