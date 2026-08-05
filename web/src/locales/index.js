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
import enUS from "./en-US.json";
import jaJP from "./ja-JP.json";

const STORAGE_KEY = "love-lang";

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
  messages: {
    "zh-CN": zhCN,
    "en-US": enUS,
    "ja-JP": jaJP,
  },
});

export function setLocale(code) {
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
