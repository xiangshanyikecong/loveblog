import { afterEach, describe, expect, it, vi } from "vitest";

import { getDefaultLocale } from "./index";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getDefaultLocale", () => {
  it("falls back to the browser language when storage is unavailable", () => {
    vi.stubGlobal("localStorage", {});
    vi.stubGlobal("navigator", { language: "en-US" });

    expect(getDefaultLocale()).toBe("en-US");
  });

  it("uses a supported persisted locale", () => {
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(() => "ja-JP"),
      setItem: vi.fn()
    });
    vi.stubGlobal("navigator", { language: "en-US" });

    expect(getDefaultLocale()).toBe("ja-JP");
  });
});
