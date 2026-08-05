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

import axios from "axios";
import { t } from "../locales";

function isAbsoluteUrl(value) {
  return /^(?:[a-z]+:)?\/\//i.test(value);
}

function hasCustomScheme(value) {
  return /^[a-z][a-z\d+.-]*:/i.test(value);
}

const SAFE_REMOTE_ASSET_PROTOCOLS = new Set(["http:", "https:"]);

function isSafeInlineAssetUrl(value) {
  return /^(?:blob:|data:(?:image|audio|video)\/)/i.test(value);
}

function trimTrailingSlash(value) {
  return value.replace(/\/+$/, "");
}

function normalizeApiBaseUrl(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) {
    return "/api";
  }

  if (isAbsoluteUrl(trimmed)) {
    return trimTrailingSlash(trimmed);
  }

  const normalized = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return trimTrailingSlash(normalized) || "/";
}

const runtimeOrigin = typeof window !== "undefined" ? window.location.origin : "";
export const apiBaseURL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL || "/api");
const assetBaseOrigin = isAbsoluteUrl(apiBaseURL) ? new URL(apiBaseURL).origin : runtimeOrigin;

function normalizeAssetPath(value) {
  return `/${String(value || "").replace(/^\/+/, "")}`;
}

function isInternalAssetPath(value) {
  return /^\/uploads(?:\/|$)/i.test(normalizeAssetPath(value));
}

function isInternalAssetReference(value) {
  const rawPath = String(value || "").trim();
  if (!rawPath || rawPath.startsWith("#") || rawPath.startsWith("?")) {
    return false;
  }

  if (isAbsoluteUrl(rawPath)) {
    try {
      return isInternalAssetPath(new URL(rawPath).pathname);
    } catch {
      return false;
    }
  }

  if (hasCustomScheme(rawPath)) {
    return false;
  }

  return isInternalAssetPath(rawPath);
}

function buildAssetUrl(pathname, search = "", hash = "") {
  const suffix = `${normalizeAssetPath(pathname)}${search}${hash}`;
  if (!assetBaseOrigin || !isAbsoluteUrl(apiBaseURL)) {
    return suffix;
  }
  return new URL(suffix, assetBaseOrigin).toString();
}

export function resolveApiUrl(path = "") {
  if (!path) {
    return apiBaseURL;
  }

  if (isAbsoluteUrl(path)) {
    return path;
  }

  const normalizedPath = String(path).replace(/^\/+/, "");
  return apiBaseURL === "/" ? `/${normalizedPath}` : `${apiBaseURL}/${normalizedPath}`;
}

export function resolveAssetUrl(path = "") {
  const rawPath = String(path || "").trim();
  if (!rawPath) {
    return "";
  }

  if (isSafeInlineAssetUrl(rawPath)) {
    return rawPath;
  }

  if (rawPath.startsWith("#") || rawPath.startsWith("?")) {
    return rawPath;
  }

  if (isAbsoluteUrl(rawPath)) {
    try {
      const parsed = new URL(rawPath, runtimeOrigin || "http://localhost");
      if (!SAFE_REMOTE_ASSET_PROTOCOLS.has(parsed.protocol)) {
        return "";
      }
      if (!isInternalAssetPath(parsed.pathname)) {
          return rawPath;
      }
      return buildAssetUrl(parsed.pathname, parsed.search, parsed.hash);
    } catch {
      return rawPath;
    }
  }

  if (hasCustomScheme(rawPath)) {
    return "";
  }

  return buildAssetUrl(rawPath);
}

export function rewriteAssetUrlsInHtml(html = "") {
  const rawHtml = String(html || "");
  if (!rawHtml || typeof document === "undefined") {
    return rawHtml;
  }

  const container = document.createElement("div");
  container.innerHTML = rawHtml;

  for (const element of container.querySelectorAll("img[src], source[src], video[src], audio[src]")) {
    if (element.hasAttribute("src")) {
      element.setAttribute("src", resolveAssetUrl(element.getAttribute("src") || ""));
    }
  }

  for (const element of container.querySelectorAll("a[href]")) {
    const href = element.getAttribute("href") || "";
    if (isInternalAssetReference(href)) {
      element.setAttribute("href", resolveAssetUrl(href));
    }
    if (element.getAttribute("target") === "_blank") {
      element.setAttribute("rel", "noopener noreferrer");
    }
  }

  return container.innerHTML;
}

export const api = axios.create({
  baseURL: apiBaseURL,
  withCredentials: true
});

let unauthorizedHandler = () => {};

function shouldInvalidateSession(error) {
  if (error?.response?.status !== 401 || error?.config?.skipAuthInvalidation) {
    return false;
  }
  const url = String(error?.config?.url || "");
  return !["/v1/auth/login", "/v1/auth/bootstrap"].includes(url);
}

export function setAuthToken(token) {
  // Keeping this for compatibility with components, but we don't store token anymore
  return token || "";
}

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = typeof handler === "function" ? handler : () => {};
}

export async function fetchMe() {
  const { data } = await api.get("/v1/auth/me");
  return data;
}

export async function logoutApi() {
  await api.post("/v1/auth/logout", undefined, {
    timeout: 5000,
    skipAuthInvalidation: true
  });
}

export function loadTokenFromStorage() {
  // Legacy function: previously loaded token from local storage
  return "";
}



api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (shouldInvalidateSession(error)) {
      unauthorizedHandler();
    }
    return Promise.reject(error);
  }
);

export async function fetchDashboard() {
  const { data } = await api.get("/v1/dashboard");
  return data;
}

export async function fetchEvents() {
  const { data } = await api.get("/v1/events");
  return data;
}

export async function createEvent(payload) {
  const { data } = await api.post("/v1/events", payload);
  return data;
}

export async function fetchArticles(params = {}) {
  const { data } = await api.get("/v1/articles", { params });
  return data;
}

export async function fetchArticle(aid, { password = "" } = {}) {
  const headers = password ? { "X-Content-Password": password } : undefined;
  const { data, headers: responseHeaders } = await api.get(`/v1/articles/${aid}`, {
    headers,
    skipAuthInvalidation: true
  });
  // Persist the server-issued ETag (the article's current version) so the
  // editor can pass `If-Match` on the next save and detect co-edit conflicts.
  data.__etag = parseEtagHeader(responseHeaders?.etag) ?? data.version ?? null;
  return data;
}

export async function fetchAlbum(albId, { password = "" } = {}) {
  const headers = password ? { "X-Content-Password": password } : undefined;
  const { data } = await api.get(`/v1/albums/${albId}`, {
    headers,
    skipAuthInvalidation: true
  });
  return data;
}

export async function fetchDrafts() {
  const { data } = await api.get("/v1/articles", { params: { only_published: false } });
  // only return drafts
  return { ...data, items: (data.items || []).filter(a => a.status !== "Published") };
}

export async function createArticle(payload) {
  const { data } = await api.post("/v1/articles", payload);
  return data;
}

export async function fetchAlbums() {
  const { data } = await api.get("/v1/albums");
  return data;
}

export async function createAlbum(payload) {
  const { data } = await api.post("/v1/albums", payload);
  return data;
}

export async function uploadAlbumImage(file) {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await api.post("/v1/uploads/albums", formData, {
    headers: {
      "Content-Type": "multipart/form-data"
    }
  });
  return data;
}

export async function uploadTimelineImage(file) {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await api.post("/v1/uploads/timeline", formData, {
    headers: {
      "Content-Type": "multipart/form-data"
    }
  });
  return data;
}

export async function uploadCheckinImage(file) {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await api.post("/v1/uploads/checkin", formData, {
    headers: {
      "Content-Type": "multipart/form-data"
    }
  });
  return data;
}

export async function createCheckin(payload) {
  const { data } = await api.post("/v1/checkins", payload);
  return data;
}

export async function fetchLatestCheckin() {
  const { data } = await api.get("/v1/checkins/latest");
  return data; // returns item (CheckInResponse or null)
}

export async function fetchCheckins(params = {}) {
  const { data } = await api.get("/v1/checkins", { params });
  return data; // returns items, page, page_size, total, has_next
}

// ── Cottage wishlist (心愿单) ────────────────────────────────────────────────
export async function fetchWishes(params = {}) {
  const { data } = await api.get("/v1/cottage/wishes", { params });
  return data; // returns items, total, pending, completed
}

export async function createWish(payload) {
  const { data } = await api.post("/v1/cottage/wishes", payload);
  return data;
}

export async function updateWish(wid, payload) {
  const { data } = await api.patch(`/v1/cottage/wishes/${wid}`, payload);
  return data;
}

export async function completeWish(wid) {
  const { data } = await api.post(`/v1/cottage/wishes/${wid}/complete`);
  return data;
}

export async function reopenWish(wid) {
  const { data } = await api.post(`/v1/cottage/wishes/${wid}/reopen`);
  return data;
}

export async function deleteWish(wid) {
  await api.delete(`/v1/cottage/wishes/${wid}`);
}

// ── Cottage chat / presence / poke (悄悄话·在线状态·戳一戳) ────────────────────
export async function fetchChatState() {
  const { data } = await api.get("/v1/cottage/chat/state");
  return data; // partner_uid, partner_nickname, partner_online, self_online, unread
}

export async function fetchChatMessages(params = {}) {
  const { data } = await api.get("/v1/cottage/chat/messages", { params });
  return data; // items, has_more, next_before_id
}

export async function searchChatMessages(params = {}) {
  const { data } = await api.get("/v1/cottage/chat/search", { params });
  return data; // query, items
}

export async function sendChatMessage(payload) {
  const { data } = await api.post("/v1/cottage/chat/messages", payload);
  return data;
}

export async function markChatRead() {
  const { data } = await api.post("/v1/cottage/chat/read");
  return data;
}

export async function uploadChatImage(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/v1/uploads/checkin", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return data;
}

export async function uploadChatAudio(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/v1/uploads/chat-audio", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return data;
}

export async function uploadChatEncryptedMedia(blob, filename = "encrypted.enc") {
  const formData = new FormData();
  formData.append("file", blob, filename);
  const { data } = await api.post("/v1/uploads/chat-encrypted-media", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return data;
}

export async function sendPoke(kind = "poke") {
  const { data } = await api.post("/v1/cottage/poke", { kind });
  return data;
}

export async function recallChatMessage(mid) {
  const { data } = await api.post(`/v1/cottage/chat/messages/${mid}/recall`);
  return data;
}

export async function fetchChatFavorites() {
  const { data } = await api.get("/v1/cottage/chat/favorites");
  return data;
}

export async function favoriteChatMessage(mid) {
  const { data } = await api.post(`/v1/cottage/chat/messages/${mid}/favorite`);
  return data;
}

export async function unfavoriteChatMessage(mid) {
  const { data } = await api.delete(`/v1/cottage/chat/messages/${mid}/favorite`);
  return data;
}

export async function fetchPinnedQuote() {
  const { data } = await api.get("/v1/cottage/chat/pinned-quote");
  return data;
}

export async function setPinnedQuote(mid) {
  const { data } = await api.put("/v1/cottage/chat/pinned-quote", { mid });
  return data;
}

export async function clearPinnedQuote() {
  const { data } = await api.delete("/v1/cottage/chat/pinned-quote");
  return data;
}

export async function fetchFutureChatMessages() {
  const { data } = await api.get("/v1/cottage/chat/future");
  return data;
}

export async function fetchChatKeywords(params = {}) {
  const { data } = await api.get("/v1/cottage/chat/keywords", { params });
  return data;
}

export async function fetchChatMemoryCard(params = {}) {
  const { data } = await api.get("/v1/cottage/chat/memory-card", { params });
  return data;
}

export async function fetchChatMediaPanel(params = {}) {
  const { data } = await api.get("/v1/cottage/chat/media-panel", { params });
  return data;
}

// ── Cottage 端到端加密聊天 (E2E chat) ──────────────────────────────────
// The server is a blind store: it never sees the derived key, only the
// public KDF parameters + a verifier blob. All three helpers below
// work against /v1/cottage/chat/keys/*.
export async function fetchChatKeyMeta() {
  const { data } = await api.get("/v1/cottage/chat/keys/meta");
  return data; // { initialized, salt?, kdf?, ..., verifier_iv?, verifier_cipher? }
}

export async function setupChatKey(publicMeta) {
  const { data } = await api.post("/v1/cottage/chat/keys/setup", publicMeta);
  return data;
}

export async function verifyChatKey(proof) {
  await api.post("/v1/cottage/chat/keys/verify", {
    proof_iv: proof.iv,
    proof_cipher: proof.cipher,
  });
}

export async function rekeyChatKey(publicMeta) {
  const { data } = await api.post("/v1/cottage/chat/keys/rekey", publicMeta);
  return data;
}

// ── Cottage mood check-in (心情打卡 / 情绪日历) ───────────────────────────────
export async function upsertMood(payload) {
  const { data } = await api.post("/v1/cottage/mood", payload);
  return data;
}

export async function fetchMoodToday(on) {
  const params = on ? { on } : {};
  const { data } = await api.get("/v1/cottage/mood/today", { params });
  return data; // mine, partner
}

export async function fetchMoodCalendar(year, month) {
  const { data } = await api.get("/v1/cottage/mood/calendar", {
    params: { year, month }
  });
  return data; // year, month, items
}

export async function fetchTodayQuestion(on) {
  const params = on ? { on } : {};
  const { data } = await api.get("/v1/cottage/questions/today", { params });
  return data;
}

export async function fetchDailyQuestions(params = {}) {
  const { data } = await api.get("/v1/cottage/questions", { params });
  return data;
}

export async function createDailyQuestion(payload) {
  const { data } = await api.post("/v1/cottage/questions", payload);
  return data;
}

export async function answerDailyQuestion(qid, payload) {
  const { data } = await api.post(`/v1/cottage/questions/${qid}/answer`, payload);
  return data;
}

// ── Cottage watch-together (一起看) ───────────────────────────────────────────
export async function fetchCottagePlans(params = {}) {
  const { data } = await api.get("/v1/cottage/plans", { params });
  return data;
}

export async function createCottagePlan(payload) {
  const { data } = await api.post("/v1/cottage/plans", payload);
  return data;
}

export async function updateCottagePlan(pid, payload) {
  const { data } = await api.patch(`/v1/cottage/plans/${pid}`, payload);
  return data;
}

export async function completeCottagePlan(pid) {
  const { data } = await api.post(`/v1/cottage/plans/${pid}/complete`);
  return data;
}

export async function reopenCottagePlan(pid) {
  const { data } = await api.post(`/v1/cottage/plans/${pid}/reopen`);
  return data;
}

export async function deleteCottagePlan(pid) {
  await api.delete(`/v1/cottage/plans/${pid}`);
}

export async function fetchCottageReminders(params = {}) {
  const { data } = await api.get("/v1/cottage/reminders", { params });
  return data;
}

export async function createCottageReminder(payload) {
  const { data } = await api.post("/v1/cottage/reminders", payload);
  return data;
}

export async function updateCottageReminder(rid, payload) {
  const { data } = await api.patch(`/v1/cottage/reminders/${rid}`, payload);
  return data;
}

export async function markCottageReminderDone(rid) {
  const { data } = await api.post(`/v1/cottage/reminders/${rid}/done`);
  return data;
}

export async function reopenCottageReminder(rid) {
  const { data } = await api.post(`/v1/cottage/reminders/${rid}/reopen`);
  return data;
}

export async function deleteCottageReminder(rid) {
  await api.delete(`/v1/cottage/reminders/${rid}`);
}

export async function fetchCottageMonthlyReport(year, month) {
  const { data } = await api.get("/v1/cottage/reports/monthly", {
    params: { year, month }
  });
  return data;
}

export async function fetchWatchState() {
  const { data } = await api.get("/v1/cottage/watch/state");
  return data; // returns current, partners
}

export async function fetchWatchSources() {
  const { data } = await api.get("/v1/cottage/watch/sources");
  return data; // returns items, total
}

export async function addWatchUrlSource(payload) {
  const { data } = await api.post("/v1/cottage/watch/sources", payload);
  return data;
}

export async function uploadWatchVideo(file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/v1/cottage/watch/sources/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    }
  });
  return data;
}

export async function deleteWatchSource(wsid) {
  await api.delete(`/v1/cottage/watch/sources/${wsid}`);
}

/**
 * Update the resume position and/or bookmarks on a shared watch source.
 *
 * Both fields are optional; an empty payload is a no-op. The server REPLACES
 * the bookmark list in full — callers should always pass the current list
 * with their change applied.
 *
 * @param {string} wsid
 * @param {{last_position_ms?: number, bookmarks?: Array<{bid: string, position_ms: number, label: string, created_at: string, created_by_uid: string}>, title?: string, poster_url?: string}} payload
 */
export async function patchWatchSource(wsid, payload) {
  const { data } = await api.patch(`/v1/cottage/watch/sources/${wsid}`, payload);
  return data;
}

export async function inviteWatchPartner() {
  await api.post("/v1/cottage/watch/invite");
}

// ── Cottage 协作画板 (canvas) ────────────────────────────────────────────
// The drawing frames are still pure-relay over WebSocket; the gallery
// below is the *persisted* result of a "保存到作品集" click.
export async function fetchCanvasArtworks(page = 1, pageSize = 20) {
  const { data } = await api.get("/v1/cottage/canvas/artworks", {
    params: { page, page_size: pageSize },
  });
  return data; // { items, total, has_next }
}

export async function fetchCanvasArtwork(caid) {
  const { data } = await api.get(`/v1/cottage/canvas/artworks/${caid}`);
  return data;
}

export async function createCanvasArtwork(payload) {
  const { data } = await api.post("/v1/cottage/canvas/artworks", payload);
  return data;
}

export async function deleteCanvasArtwork(caid) {
  await api.delete(`/v1/cottage/canvas/artworks/${caid}`);
}

// ── Cottage 一起玩 (games · 五子棋 / 井字棋) ──────────────────────────────────
// Generic, game-keyed helpers. `game` is "gomoku" | "tictactoe".
export async function fetchGameState(game) {
  const { data } = await api.get(`/v1/cottage/games/${game}/state`);
  return data; // room snapshot + players
}

export async function fetchGameMatches(game, limit = 20) {
  const { data } = await api.get(`/v1/cottage/games/${game}/matches`, {
    params: { limit }
  });
  return data; // items, total, draws, stats
}

export async function inviteGamePartner(game) {
  await api.post(`/v1/cottage/games/${game}/invite`);
}

// Thin gomoku-named wrappers kept for existing callers.
export const fetchGomokuState = () => fetchGameState("gomoku");
export const fetchGomokuMatches = (limit = 20) => fetchGameMatches("gomoku", limit);
export const inviteGomokuPartner = () => inviteGamePartner("gomoku");

// ── Cottage 你画我猜 (draw & guess) ──────────────────────────────────────────
export async function fetchDrawState() {
  const { data } = await api.get("/v1/cottage/draw/state");
  return data; // room snapshot + players
}

export async function fetchDrawMatches(limit = 20) {
  const { data } = await api.get("/v1/cottage/draw/matches", { params: { limit } });
  return data; // items, total, draws, stats
}

export async function inviteDrawPartner() {
  await api.post("/v1/cottage/draw/invite");
}

// ── Cottage 加密保险箱 (E2EE vault) ──────────────────────────────────────────
// The server is a blind store: every payload here is opaque ciphertext / KDF
// params produced in the browser (see lib/vaultCrypto.js). No passphrase or key
// is ever sent.
export async function fetchVaultMeta() {
  const { data } = await api.get("/v1/cottage/vault/meta");
  return data; // { initialized, salt, kdf, kdf_hash, iterations, algo, verifier_iv, verifier_cipher }
}

export async function setupVault(payload) {
  const { data } = await api.post("/v1/cottage/vault/setup", payload);
  return data;
}

export async function fetchVaultEntries() {
  const { data } = await api.get("/v1/cottage/vault/entries");
  return data; // [{ vid, iv, ciphertext, author_uid, created_at, updated_at }]
}

export async function createVaultEntry(payload) {
  const { data } = await api.post("/v1/cottage/vault/entries", payload);
  return data;
}

export async function updateVaultEntry(vid, payload) {
  const { data } = await api.put(`/v1/cottage/vault/entries/${vid}`, payload);
  return data;
}

export async function deleteVaultEntry(vid) {
  await api.delete(`/v1/cottage/vault/entries/${vid}`);
}

export async function resetVault() {
  await api.post("/v1/cottage/vault/reset");
}

export async function rekeyVault(payload) {
  const { data } = await api.post("/v1/cottage/vault/rekey", payload);
  return data; // new VaultMetaResponse
}

export async function uploadFile(file, destination = "avatars") {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await api.post(`/v1/uploads/${destination}`, formData, {
    headers: {
      "Content-Type": "multipart/form-data"
    }
  });
  return data;
}

export async function fetchAvatarFromQQ(qq) {
  const { data } = await api.post("/v1/uploads/avatars/from-qq", { qq });
  return data; // returns url, file_name, content_type, size
}

export async function fetchMessages(params = {}) {
  const { data } = await api.get("/v1/messages", { params });
  return data;
}

export async function createMessage(payload) {
  const { data } = await api.post("/v1/messages", payload);
  return data;
}

export async function updateMessage(msgId, payload) {
  const { data } = await api.patch(`/v1/messages/${msgId}`, payload);
  return data;
}

export async function fetchSettings() {
  const { data } = await api.get("/v1/settings");
  return data;
}

export async function updateSettings(payload) {
  const { data } = await api.put("/v1/settings", payload);
  return data;
}

export async function fetchStorageStats() {
  const { data } = await api.get("/v1/uploads/storage-stats");
  return data;
}

export async function updateArticle(aid, payload, { ifMatch } = {}) {
  const headers = {};
  if (ifMatch !== undefined && ifMatch !== null && ifMatch !== "") {
    headers["If-Match"] = String(ifMatch);
  }
  try {
    const { data, headers: responseHeaders } = await api.put(`/v1/articles/${aid}`, payload, { headers });
    data.__etag = parseEtagHeader(responseHeaders?.etag);
    return data;
  } catch (error) {
    throw normalizeArticleError(error);
  }
}

export async function patchArticle(aid, payload, { ifMatch } = {}) {
  const headers = {};
  if (ifMatch !== undefined && ifMatch !== null && ifMatch !== "") {
    headers["If-Match"] = String(ifMatch);
  }
  try {
    const { data, headers: responseHeaders } = await api.patch(`/v1/articles/${aid}`, payload, { headers });
    data.__etag = parseEtagHeader(responseHeaders?.etag);
    return data;
  } catch (error) {
    throw normalizeArticleError(error);
  }
}

/**
 * Parse an ETag response header (RFC 7232) into a numeric version.
 * Returns `null` when the header is missing or malformed so the caller can
 * fall back to the body's `version` field.
 */
function parseEtagHeader(rawEtag) {
  if (!rawEtag) return null;
  const stripped = String(rawEtag).trim().replace(/^W\//, "").replace(/^"|"$/g, "");
  const parsed = Number.parseInt(stripped, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

/**
 * Translate the FastAPI HTTPException `detail` object (used for 409 responses)
 * into a structured error so the editor can decide between "force overwrite",
 * "reload and lose my changes", or "cancel". The original axios error is
 * preserved via the `cause` chain so existing logging still works.
 */
function normalizeArticleError(error) {
  if (error?.response?.status === 409) {
    const detail = error.response?.data?.detail;
    if (detail && typeof detail === "object" && detail.code === "article_version_conflict") {
      const wrapped = new Error(detail.message || t("api.articleVersionConflict"));
      wrapped.name = "ArticleVersionConflictError";
      wrapped.code = detail.code;
      wrapped.currentVersion = detail.current_version;
      wrapped.expectedVersion = detail.expected_version;
      wrapped.cause = error;
      return wrapped;
    }
  }
  return error;
}

export async function deleteArticle(aid) {
  const { data } = await api.delete(`/v1/articles/${aid}`);
  return data;
}

export async function updateAlbum(albId, payload) {
  const { data } = await api.put(`/v1/albums/${albId}`, payload);
  return data;
}

export async function patchAlbum(albId, payload) {
  const { data } = await api.patch(`/v1/albums/${albId}`, payload);
  return data;
}

export async function patchEvent(eid, payload) {
  const { data } = await api.patch(`/v1/events/${eid}`, payload);
  return data;
}

export async function updateEvent(eid, payload) {
  const { data } = await api.put(`/v1/events/${eid}`, payload);
  return data;
}

export async function deleteAlbum(albId) {
  const { data } = await api.delete(`/v1/albums/${albId}`);
  return data;
}

export async function deleteMessage(msgId) {
  const { data } = await api.delete(`/v1/messages/${msgId}`);
  return data;
}

export async function fetchPartners() {
  const { data } = await api.get("/v1/auth/partners");
  return data;
}

export async function updatePartner(uid, payload) {
  const { data } = await api.put(`/v1/auth/partners/${uid}`, payload);
  return data;
}

export async function registerPartner(payload) {
  const { data } = await api.post("/v1/auth/register", payload);
  return data;
}

export async function fetchVisitors(params = {}) {
  const { data } = await api.get("/v1/auth/visitors", { params });
  return data;
}

export async function fetchVisitor(uid) {
  const { data } = await api.get(`/v1/auth/visitors/${uid}`);
  return data;
}

export async function updateVisitor(uid, payload) {
  const { data } = await api.put(`/v1/auth/visitors/${uid}`, payload);
  return data;
}

export async function toggleVisitorBan(uid) {
  const { data } = await api.post(`/v1/auth/visitors/${uid}/toggle-ban`);
  return data;
}

export async function fetchTimeline(params = {}) {
  const { data } = await api.get("/v1/timeline", { params });
  return data;
}

export async function createMoment(payload) {
  const { data } = await api.post("/v1/timeline", payload);
  return data;
}

export async function deleteMoment(mid) {
  const { data } = await api.delete(`/v1/timeline/${mid}`);
  return data;
}

export async function postComment(mid, payload) {
  const { data } = await api.post(`/v1/timeline/${mid}/comments`, payload);
  return data;
}

export async function fetchMemories() {
  const { data } = await api.get("/v1/timeline/memories");
  return data;
}

export async function exportBackupArchive() {
  return api.get("/v1/export/all", {
    responseType: "blob"
  });
}

export async function fetchBackupPreflight() {
  const { data } = await api.get("/v1/export/preflight");
  return data;
}

export async function fetchBackupHistory() {
  const { data } = await api.get("/v1/export/history");
  return data;
}

export async function fetchBackupSchedule() {
  const { data } = await api.get("/v1/export/schedule");
  return data;
}

export async function updateBackupSchedule(payload) {
  const { data } = await api.put("/v1/export/schedule", payload);
  return data;
}

export async function runAutoBackupNow() {
  const { data } = await api.post("/v1/export/auto/run");
  return data;
}

export async function fetchArticleVersions(aid) {
  const { data } = await api.get(`/v1/articles/${aid}/versions`);
  return data;
}

export async function rollbackArticleVersion(aid, version) {
  const { data } = await api.post(`/v1/articles/${aid}/versions/${version}/rollback`);
  return data;
}

export async function fetchMessageVersions(msgId) {
  const { data } = await api.get(`/v1/messages/${msgId}/versions`);
  return data;
}

export async function rollbackMessageVersion(msgId, version) {
  const { data } = await api.post(`/v1/messages/${msgId}/versions/${version}/rollback`);
  return data;
}

export async function fetchPushPublicKey() {
  const { data } = await api.get("/v1/push/public-key");
  return data;
}

export async function savePushSubscription(payload) {
  const { data } = await api.put("/v1/push/subscriptions", payload);
  return data;
}

export async function deletePushSubscription(payload) {
  const { data } = await api.delete("/v1/push/subscriptions", { data: payload });
  return data;
}

export async function fetchPushSubscriptions() {
  const { data } = await api.get("/v1/push/subscriptions");
  return data;
}

export async function fetchNotifications(params = {}) {
  const { data } = await api.get("/v1/notifications", { params });
  return data;
}

export async function markNotificationRead(nid) {
  const { data } = await api.post(`/v1/notifications/${nid}/read`);
  return data;
}

export async function markAllNotificationsRead() {
  const { data } = await api.post("/v1/notifications/read-all");
  return data;
}

export async function fetchAuditLogs(params = {}) {
  const { data } = await api.get("/v1/audit-logs", { params });
  return data;
}

export async function fetchPrivacySummary() {
  const { data } = await api.get("/v1/privacy/summary");
  return data;
}

export async function recordPrivacyRecoveryEvent(scope, event) {
  const { data } = await api.post("/v1/privacy/recovery-events", { scope, event });
  return data;
}

export async function fetchSearch(params = {}) {
  const { data } = await api.get("/v1/search", { params });
  return data;
}

export async function restorePreflight(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/v1/export/restore/preflight", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return data;
}

export async function restoreBackup(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/v1/export/restore", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return data;
}

export async function fetchCapsules() {
  const { data } = await api.get("/v1/capsules");
  return data;
}

export async function createCapsule(payload) {
  const { data } = await api.post("/v1/capsules", payload);
  return data;
}

export async function uploadCapsuleMedia(file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/v1/uploads/capsule", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    }
  });
  return data;
}

export async function deleteCapsule(uuid) {
  const { data } = await api.delete(`/v1/capsules/${uuid}`);
  return data;
}

export async function fetchSystemHealth(options = {}) {
  const params = {};
  
  // 指定要检查的组件
  if (options.components) {
    params.components = Array.isArray(options.components) 
      ? options.components.join(',') 
      : options.components;
  }
  
  // 是否包含优化建议
  if (options.includeRecommendations !== undefined) {
    params.include_recommendations = options.includeRecommendations;
  }
  
  // 是否返回详细信息
  if (options.detailed !== undefined) {
    params.detailed = options.detailed;
  }
  
  const { data } = await api.get("/health/system", { params });
  return data;
}

/**
 * Historical health snapshots written by the background monitor.
 *
 * @param {{hours?: number, limit?: number}} [options]
 * @returns {Promise<{items: Array<{id: number, overall_status: string, health_score: number, remediated: boolean, remediation_note: string, created_at: string}>, total: number}>}
 */
export async function fetchHealthHistory(options = {}) {
  const params = {};
  if (options.hours) params.hours = options.hours;
  if (options.limit) params.limit = options.limit;
  const { data } = await api.get("/health/system/history", { params });
  return data;
}

/**
 * Manually trigger a remediation pass (clean orphaned temp files) and record
 * a fresh snapshot. Returns the cleanup note plus a live post-cleanup check.
 *
 * @returns {Promise<{remediated: boolean, note: string, snapshot: object}>}
 */
export async function remediateHealthNow() {
  const { data } = await api.post("/health/system/remediate");
  return data;
}

export async function fetchBootstrapStatus() {
  const { data } = await api.get("/v1/auth/bootstrap-status");
  return data;
}

export async function submitBootstrap(payload, bootstrapToken) {
  const { data } = await api.post("/v1/auth/bootstrap", payload, {
    headers: { "X-Bootstrap-Token": bootstrapToken }
  });
  return data;
}

// 安全相关 API
export async function fetchSecurityUsers() {
  const { data } = await api.get("/v1/security/users");
  return data;
}

export async function changePassword(uid, payload) {
  const { data } = await api.post(`/v1/security/users/${uid}/change-password`, payload);
  return data;
}

export async function resetUserPassword(uid, payload) {
  const { data } = await api.post(`/v1/security/users/${uid}/reset-password`, payload);
  return data;
}

export async function revokeUserSessions(uid) {
  const { data } = await api.post(`/v1/security/users/${uid}/revoke-sessions`, { confirm: true });
  return data;
}

export async function unlockUserAccount(uid) {
  const { data } = await api.post(`/v1/security/users/${uid}/unlock`, { confirm: true });
  return data;
}

export async function revokeOwnSessions(uid) {
  const { data } = await api.post(`/v1/security/users/${uid}/revoke-own-sessions`, { confirm: true });
  return data;
}

// 回收站相关 API
export async function fetchRecycleBin(params = {}) {
  const { data } = await api.get("/v1/recycle-bin", { params });
  return data;
}

export async function restoreRecycleBinItem(type, id) {
  const { data } = await api.post(`/v1/recycle-bin/${type}/${id}/restore`);
  return data;
}

export async function deleteRecycleBinItem(type, id) {
  const { data } = await api.delete(`/v1/recycle-bin/${type}/${id}`);
  return data;
}

export async function clearRecycleBin(type = null) {
  const params = type ? { type } : {};
  const { data } = await api.delete("/v1/recycle-bin", { params });
  return data;
}

// 文章评论
export async function postArticleComment(aid, payload) {
  const { data } = await api.post(`/v1/articles/${aid}/comments`, payload);
  return data;
}

// 相册评论
export async function postAlbumComment(albId, payload) {
  const { data } = await api.post(`/v1/albums/${albId}/comments`, payload);
  return data;
}

// 一起听 (Cottage Listen Together)

export async function fetchListenState() {
  const { data } = await api.get("/v1/cottage/listen/state");
  return data;
}

export async function fetchListenQrKey() {
  const { data } = await api.get("/v1/cottage/listen/auth/qr-key");
  return data; // returns unikey, qr_image_data_url
}

export async function fetchListenQrStatus(unikey) {
  const { data } = await api.get("/v1/cottage/listen/auth/qr-status", {
    params: { key: unikey }
  });
  return data; // returns status, message
}

export async function importListenCookie(cookie) {
  // Manual cookie import — sidesteps NetEase 异地登录 risk-control by letting
  // the partner log in from their own network and paste the cookie here.
  const { data } = await api.post("/v1/cottage/listen/auth/import-cookie", {
    cookie
  });
  return data; // returns status, message
}

export async function listenLogout() {
  await api.post("/v1/cottage/listen/auth/logout");
}

export async function listenSearch({ keyword, page = 1, page_size = 20 } = {}) {
  const { data } = await api.get("/v1/cottage/listen/search", {
    params: { keyword, page, page_size }
  });
  return data; // returns items, page, page_size, has_next
}

export async function listenPlaylists() {
  const { data } = await api.get("/v1/cottage/listen/playlists");
  return data; // returns items (array of PlaylistItem)
}

export async function listenPlaylistTracks(playlistId, { page = 1, page_size = 50 } = {}) {
  const { data } = await api.get(
    `/v1/cottage/listen/playlists/${playlistId}/tracks`,
    { params: { page, page_size } }
  );
  return data;
}

export async function listenSongUrl(songId) {
  const { data } = await api.get(`/v1/cottage/listen/songs/${songId}/url`);
  return data; // returns song_id, url, expires_at_ms, provider, error_kind
}

export async function listenSongLyric(songId) {
  const { data } = await api.get(`/v1/cottage/listen/songs/${songId}/lyric`);
  return data; // returns song_id, lines (time_ms, text, trans), kind
}

export async function listenDiscoverRecommendSongs() {
  const { data } = await api.get("/v1/cottage/listen/discover/recommend-songs");
  return data;
}

export async function listenDiscoverPlaylists({ limit = 12 } = {}) {
  const { data } = await api.get("/v1/cottage/listen/discover/playlists", {
    params: { limit }
  });
  return data;
}

export async function listenDiscoverPlaylistTracks(playlistId, { page = 1, page_size = 50 } = {}) {
  const { data } = await api.get(
    `/v1/cottage/listen/discover/playlists/${playlistId}/tracks`,
    { params: { page, page_size } }
  );
  return data;
}

export async function listenDiscoverToplist() {
  const { data } = await api.get("/v1/cottage/listen/discover/toplist");
  return data;
}

export async function listenDiscoverToplistTracks(toplistId, { page = 1, page_size = 50 } = {}) {
  const { data } = await api.get(
    `/v1/cottage/listen/discover/toplist/${toplistId}/tracks`,
    { params: { page, page_size } }
  );
  return data;
}

export async function listenHistory({ limit = 50 } = {}) {
  const { data } = await api.get("/v1/cottage/listen/history", { params: { limit } });
  return data;
}

export async function listenLocalTracks() {
  const { data } = await api.get("/v1/cottage/listen/local-tracks");
  return data; // { items: SongMeta[] }
}

export async function uploadLocalTrack(file, meta = {}) {
  const formData = new FormData();
  formData.append("file", file);
  if (meta.name) formData.append("name", meta.name);
  if (meta.artist) formData.append("artist", meta.artist);
  if (meta.album) formData.append("album", meta.album);
  if (meta.duration_ms != null) formData.append("duration_ms", String(meta.duration_ms));
  if (meta.cover_url) formData.append("cover_url", meta.cover_url);
  const { data } = await api.post("/v1/cottage/listen/local-tracks", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return data; // SongMeta
}

export async function deleteLocalTrack(tid) {
  await api.delete(`/v1/cottage/listen/local-tracks/${tid}`);
}

// ── Cottage love coupons (甜蜜兑换券) ─────────────────────────────────────────
export async function fetchCoupons(params = {}) {
  const { data } = await api.get("/v1/cottage/coupons", { params });
  return data; // { items, total, active, redeemed }
}

export async function createCoupon(payload) {
  const { data } = await api.post("/v1/cottage/coupons", payload);
  return data;
}

export async function updateCoupon(cpid, payload) {
  const { data } = await api.patch(`/v1/cottage/coupons/${cpid}`, payload);
  return data;
}

export async function redeemCoupon(cpid) {
  const { data } = await api.post(`/v1/cottage/coupons/${cpid}/redeem`);
  return data;
}

export async function deleteCoupon(cpid) {
  await api.delete(`/v1/cottage/coupons/${cpid}`);
}

// ── Cottage shared ledger (情侣账本 / AA 记账) ────────────────────────────────
export async function fetchLedger(params = {}) {
  const { data } = await api.get("/v1/cottage/ledger", { params });
  return data; // { items, total, page, page_size, has_next }
}

export async function fetchLedgerSummary(params = {}) {
  const { data } = await api.get("/v1/cottage/ledger/summary", { params });
  return data;
}

export async function createLedgerEntry(payload) {
  const { data } = await api.post("/v1/cottage/ledger", payload);
  return data;
}

export async function updateLedgerEntry(leid, payload) {
  const { data } = await api.patch(`/v1/cottage/ledger/${leid}`, payload);
  return data;
}

export async function deleteLedgerEntry(leid) {
  await api.delete(`/v1/cottage/ledger/${leid}`);
}

// ── Cottage period tracker (生理期记录与关怀提醒) ─────────────────────────────
export async function fetchPeriods(params = {}) {
  const { data } = await api.get("/v1/cottage/period", { params });
  return data; // { items, total }
}

export async function fetchPeriodSummary() {
  const { data } = await api.get("/v1/cottage/period/summary");
  return data;
}

export async function createPeriod(payload) {
  const { data } = await api.post("/v1/cottage/period", payload);
  return data;
}

export async function updatePeriod(pcid, payload) {
  const { data } = await api.patch(`/v1/cottage/period/${pcid}`, payload);
  return data;
}

export async function deletePeriod(pcid) {
  await api.delete(`/v1/cottage/period/${pcid}`);
}

// ── Cottage footprints map (恋爱足迹地图) ─────────────────────────────────────
export async function fetchFootprints() {
  const { data } = await api.get("/v1/cottage/footprints");
  return data; // { cities, total_cities, total_checkins, recent }
}
