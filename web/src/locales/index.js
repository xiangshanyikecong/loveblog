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

import { createI18n } from "vue-i18n";
import zhCN from "./zh-CN.json";

const STORAGE_KEY = "love-lang";

// zh-CN ships in the initial bundle: it is the default locale AND the
// fallbackLocale, so it must always be available synchronously. The other
// locales are code-split into separate chunks and fetched on demand.
const messages = {
  "zh-CN": zhCN,
};

export const supportedLocales = [
  { code: "zh-CN", label: "中文", flag: "🇨🇳" },
  { code: "en-US", label: "English", flag: "🇺🇸" },
  { code: "ja-JP", label: "日本語", flag: "🇯🇵" },
];

function browserStorage() {
  const storage = globalThis.localStorage;
  return storage && typeof storage.getItem === "function" && typeof storage.setItem === "function"
    ? storage
    : null;
}

export function getDefaultLocale() {
  const stored = browserStorage()?.getItem(STORAGE_KEY);
  if (stored && supportedLocales.some((l) => l.code === stored)) {
    return stored;
  }
  const browser = globalThis.navigator?.language || "zh-CN";
  if (browser.startsWith("ja")) return "ja-JP";
  if (browser.startsWith("en")) return "en-US";
  return "zh-CN";
}

const i18n = createI18n({
  legacy: false,
  locale: getDefaultLocale(),
  fallbackLocale: "zh-CN",
  messages,
});

const localeImporters = {
  "en-US": () => import("./en-US.json"),
  "ja-JP": () => import("./ja-JP.json"),
};

const loadedLocales = new Set(Object.keys(messages));
const pendingLoads = new Map();

async function ensureLocaleLoaded(code) {
  if (loadedLocales.has(code) || !localeImporters[code]) {
    return;
  }
  let pending = pendingLoads.get(code);
  if (!pending) {
    pending = localeImporters[code]()
      .then((mod) => {
        i18n.global.setLocaleMessage(code, mod.default);
        loadedLocales.add(code);
      })
      .finally(() => pendingLoads.delete(code));
    pendingLoads.set(code, pending);
  }
  await pending;
}

/**
 * Loads the locale bundle for the active locale when it is not part of the
 * initial bundle. The UI stays on zh-CN (the fallback) until the fetch
 * resolves; vue-i18n's reactive messages then re-render automatically.
 */
export async function initLocale() {
  await ensureLocaleLoaded(i18n.global.locale.value);
}

export async function setLocale(code) {
  if (!supportedLocales.some((l) => l.code === code)) {
    return;
  }
  await ensureLocaleLoaded(code);
  i18n.global.locale.value = code;
  browserStorage()?.setItem(STORAGE_KEY, code);
  if (globalThis.document?.documentElement) {
    globalThis.document.documentElement.lang = code;
  }
}

export function getLocale() {
  return i18n.global.locale.value;
}

// Expose a simple `t` function for use outside of Vue components (e.g. in
// plain JS utility modules like dialog.js, helpers.js).
export function t(key, params) {
  return i18n.global.t(key, params);
}

export default i18n;
