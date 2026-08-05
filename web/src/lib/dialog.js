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

import { reactive } from "vue";
import { t } from "../locales";

// Shared, app-wide dialog state. A single <AppDialog /> host (mounted in
// App.vue) renders whatever is described here. This replaces the native
// window.confirm / window.alert calls (CodeCheck G.AOD.04) with an in-app,
// promise-based dialog that matches the site styling.
const state = reactive({
  visible: false,
  mode: "alert", // "alert" | "confirm" | "choice"
  title: "",
  message: "",
  confirmText: "",
  cancelText: "",
  danger: false,
  // For "choice" mode only: an array of `{ label, value, danger? }` that
  // resolves the dialog promise to the chosen value. Cancel button still
  // resolves to null.
  choices: [],
});

let resolver = null;

function open(opts) {
  // Resolve any dialog that is somehow still pending before opening a new one.
  if (resolver) {
    const prev = resolver;
    resolver = null;
    prev(null);
  }
  const next = { ...opts, visible: true };
  if (next.mode !== "choice") {
    next.choices = [];
  }
  Object.assign(state, next);
  return new Promise((resolve) => {
    resolver = resolve;
  });
}

function normalize(message, opts) {
  return typeof message === "object" && message !== null
    ? message
    : { ...opts, message };
}

/**
 * Show a confirm dialog. Returns a Promise that resolves to true (confirmed)
 * or false (cancelled / dismissed).
 * Usage: if (!(await confirmDialog("确定删除？"))) return;
 */
export function confirmDialog(message, opts = {}) {
  const o = normalize(message, opts);
  return open({
    mode: "confirm",
    title: o.title || t("dialog.pleaseConfirm"),
    message: o.message || "",
    confirmText: o.confirmText || t("common.confirm"),
    cancelText: o.cancelText || t("common.cancel"),
    danger: o.danger ?? false,
  });
}

/**
 * Show an alert dialog with a single button. Returns a Promise that resolves
 * once the user dismisses it.
 */
export function alertDialog(message, opts = {}) {
  const o = normalize(message, opts);
  return open({
    mode: "alert",
    title: o.title || t("dialog.notice"),
    message: o.message || "",
    confirmText: o.confirmText || t("common.ok"),
    cancelText: "",
    danger: o.danger ?? false,
  });
}

/**
 * Show a 3-way choice dialog. Resolves to the `value` of the picked option
 * (string or any comparable), or `null` when the user cancels. The Cancel
 * button is always present so the user can back out without committing.
 *
 * @param {string} message
 * @param {Array<{label:string, value:string, danger?:boolean}>} choices
 * @param {{title?:string, cancelText?:string}} [opts]
 */
export function choiceDialog(message, choices, opts = {}) {
  if (!Array.isArray(choices) || choices.length < 2) {
    return Promise.reject(new Error(t("dialog.needAtLeast2Choices")));
  }
  return open({
    mode: "choice",
    title: opts.title || t("dialog.pleaseChoose"),
    message,
    choices,
    cancelText: opts.cancelText || t("common.cancel"),
  });
}

// Called by the AppDialog host when a button is pressed or the backdrop is
// dismissed. Not intended for direct use by feature code.
export function resolveDialog(result) {
  state.visible = false;
  const r = resolver;
  resolver = null;
  if (r) r(result);
}

export const dialogState = state;
