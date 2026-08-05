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

import { t } from "../locales";

export function pad2(num) {
  return String(num).padStart(2, "0");
}

export function eventGradient(index) {
  const palettes = [
    ["#ff6b81", "#ff9aa2"],
    ["#4ecdc4", "#7ee8df"],
    ["#3b82f6", "#60a5fa"],
    ["#fb923c", "#fdba74"],
    ["#a855f7", "#c4b5fd"],
    ["#14b8a6", "#5eead4"]
  ];
  const [start, end] = palettes[index % palettes.length];
  return { background: `linear-gradient(135deg, ${start} 0%, ${end} 100%)` };
}

export function eventStatusText(item) {
  if (!item?.date) {
    return "";
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(`${item.date}T00:00:00`);
  if (Number.isNaN(target.getTime())) {
    return t("errors.dateInvalid");
  }

  const diff = Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (diff === 0) {
    return t("errors.eventToday");
  }
  if (diff > 0) {
    return t("errors.eventDaysLeft", { n: diff });
  }
  return t("errors.eventDaysPassed", { n: Math.abs(diff) });
}

export function parseError(error) {
  const url = error?.config?.url;
  const status = error?.response?.status;
  const detail = error?.response?.data?.detail;
  const errorCode = error?.code;
  const message = String(error?.message || "").toLowerCase();
  const isLoginRequest = url === "/v1/auth/login";

  function formatLoginValidationError(item) {
    const loc = Array.isArray(item?.loc) ? item.loc : [];
    const field = loc[loc.length - 1];
    const msg = String(item?.msg || "");

    if (field === "username") {
      if (msg.includes("at least")) {
        return t("errors.usernameTooShort");
      }
      if (msg.includes("at most")) {
        return t("errors.usernameTooLong");
      }
      if (msg.includes("Field required")) {
        return t("errors.usernameRequired");
      }
      return t("errors.usernameInvalid");
    }

    if (field === "password") {
      if (msg.includes("at least")) {
        return t("errors.passwordTooShort");
      }
      if (msg.includes("at most")) {
        return t("errors.passwordTooLong");
      }
      if (msg.includes("Field required")) {
        return t("errors.passwordRequired");
      }
      return t("errors.passwordInvalid");
    }

    if (msg.includes("Field required")) {
      return t("errors.loginInfoIncomplete");
    }

    return t("errors.loginInfoInvalid");
  }

  if (isLoginRequest) {
    if (status === 401 || detail === "Incorrect username or password" || detail === "Could not validate credentials") {
      return t("errors.loginWrongCredentials");
    }
    if (typeof detail === "string") {
      const frozenMatch = detail.match(/^Account is frozen\. Try again in (\d+) minutes?\.$/i);
      if (frozenMatch) {
        return t("errors.accountFrozenMinutes", { n: frozenMatch[1] });
      }
      if (/^Account is frozen\./i.test(detail)) {
        return t("errors.accountFrozen");
      }
    }
    if (status === 429) {
      return t("errors.loginTooManyAttempts");
    }
    if (errorCode === "ERR_NETWORK" || message.includes("network error") || message.includes("failed to fetch")) {
      return t("errors.loginNetworkError");
    }
    if (message.includes("timeout") || errorCode === "ECONNABORTED") {
      return t("errors.loginTimeout");
    }
    if (status >= 500) {
      return t("errors.loginServerError");
    }
  }

  if (status === 401) {
    return t("errors.authExpired");
  }

  if (status === 403) {
    return t("errors.noPermission");
  }

  if (status === 404) {
    return t("errors.notFound");
  }

  if (status >= 500) {
    return t("errors.serverError");
  }

  if (typeof detail === "string") {
    if (detail === "Could not validate credentials") {
      return t("errors.authExpired");
    }
    if (status === 429) {
      return detail || t("errors.tooFrequent");
    }
    return /[\u4e00-\u9fff]/.test(detail) ? detail : t("errors.genericRetryError");
  }

  if (Array.isArray(detail)) {
    if (isLoginRequest) {
      return detail.map(formatLoginValidationError).join("; ");
    }

    return t("errors.validationFailed");
  }

  if (status === 429) {
    return t("errors.tooFrequent");
  }

  if (errorCode === "ERR_NETWORK" || message.includes("network error") || message.includes("failed to fetch")) {
    return t("errors.networkError");
  }

  if (message.includes("timeout") || errorCode === "ECONNABORTED") {
    return t("errors.requestTimeout");
  }

  return t("errors.genericError");
}

export function parseTags(raw) {
  const seen = new Set();
  return String(raw || "")
    .split(",")
    .map((item) => item.trim().replace(/^#+/, "").trim())
    .filter((item) => {
      if (!item) return false;
      const key = item.toLocaleLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 12);
}

export function formatFileSize(size) {
  if (!size) {
    return "0 B";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
}
