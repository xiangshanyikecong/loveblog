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

// 离线写入队列（outbox）——重放引擎（设计见 docs/design/WEB_OFFLINE_WEAK_NETWORK_DESIGN.md §6）。
//
// 职责：
// - 暂存断网期间失败的写操作（JSON 载荷，白名单见 QUEUEABLE）；
// - 恢复联网后按序重放：同一资源串行、跨资源并发 1（v1 串行，简单可靠）；
// - 幂等：创建类请求在发出前就带上 Idempotency-Key（api.js 请求拦截器），
//   重放复用同一个 key，服务端返回首次创建的资源，绝不重复；
// - 409 冲突（article.update 的 If-Match 过期）：先 GET 判断服务端内容是否
//   已经等于待写内容（首次请求其实已生效）——相等直接完成，不等才标记冲突
//   交由用户裁决；401 暂停整个队列等待重新登录；其余 4xx 直接死信；
// - 网络类失败按 1s/5s/15s/30s/60s/120s 退避重试，超过 8 次转死信。
//
// 隐私边界：队列只存 JSON 载荷，不存 FormData/媒体；密码保护内容的写入
// （带 X-Content-Password 头）不入队。

import { computed, ref } from "vue";
import { offlineStore } from "./db";

export const OUTBOX_MAX_ATTEMPTS = 8;
const BACKOFF_MS = [1000, 5000, 15000, 30000, 60000, 120000];

/**
 * 可离线入队的写操作白名单。`needsKey` 的创建类请求会在发出前被
 * api.js 请求拦截器附加 Idempotency-Key（重放复用）。
 */
export const QUEUEABLE = [
  { kind: "article.create", method: "POST", pattern: /^\/v1\/articles$/, needsKey: true },
  { kind: "article.update", method: ["PUT", "PATCH"], pattern: /^\/v1\/articles\/[^/]+$/, needsKey: false },
  { kind: "article.delete", method: "DELETE", pattern: /^\/v1\/articles\/[^/]+$/, needsKey: false },
  { kind: "moment.create", method: "POST", pattern: /^\/v1\/timeline$/, needsKey: true },
  { kind: "moment.delete", method: "DELETE", pattern: /^\/v1\/timeline\/[^/]+$/, needsKey: false },
  { kind: "moment.comment", method: "POST", pattern: /^\/v1\/timeline\/[^/]+\/comments$/, needsKey: true },
  { kind: "checkin.create", method: "POST", pattern: /^\/v1\/checkins$/, needsKey: true },
];

export function matchQueueable(method, url) {
  if (!method || !url) return null;
  const upper = String(method).toUpperCase();
  const path = String(url).split("?")[0];
  return (
    QUEUEABLE.find(
      (entry) =>
        (Array.isArray(entry.method) ? entry.method.includes(upper) : entry.method === upper) &&
        entry.pattern.test(path),
    ) || null
  );
}

export class OutboxQueuedError extends Error {
  constructor(kind, item) {
    super("queued-offline");
    this.name = "OutboxQueuedError";
    this.kind = kind;
    this.item = item;
  }
}

// ---- 响应式状态（模块级单例，与 stores/auth.js 同一模式） ----

const pendingCount = ref(0);
const flushing = ref(false);
const authPaused = ref(false);
const lastQueueEmptyAt = ref(null);
const enqueuedNotice = ref(0); // 自增事件：新入队一条（横幅弹提示用）

export const outboxState = {
  pendingCount,
  flushing,
  authPaused,
  lastQueueEmptyAt,
  enqueuedNotice,
};

export function useOutbox() {
  return {
    pendingCount,
    flushing,
    authPaused,
    lastQueueEmptyAt,
    enqueuedNotice,
    isOnline,
  };
}

export const isOnline = ref(typeof navigator === "undefined" ? true : navigator.onLine !== false);

if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    isOnline.value = true;
    clearBackoffs();
    flushOutbox();
  });
  window.addEventListener("offline", () => {
    isOnline.value = false;
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") flushOutbox();
  });
  // 在线时的轻量轮询：覆盖错过的 online 事件（如休眠唤醒）。
  setInterval(() => {
    if (isOnline.value) flushOutbox();
  }, 15000);
}

// ---- 存取 ----

async function store() {
  return offlineStore("outbox");
}

export async function countPending() {
  const s = await store();
  if (!s) return 0;
  return s.index("status").count("pending");
}

export async function listOutboxItems() {
  const s = await store();
  if (!s) return [];
  return s.getAll();
}

async function nextDispatchable() {
  const s = await store();
  if (!s) return null;
  const items = (await s.getAll()).filter((item) => item.status === "pending");
  items.sort((a, b) => a.id - b.id);
  const now = Date.now();
  return items.find((item) => (item.nextAttemptAt || 0) <= now) || null;
}

async function clearBackoffs() {
  const s = await store();
  if (!s) return;
  const items = (await s.getAll()).filter((item) => item.status === "pending");
  for (const item of items) {
    if (item.nextAttemptAt && item.nextAttemptAt > Date.now()) {
      await s.put({ ...item, nextAttemptAt: 0 });
    }
  }
}

let retryTimer = null;

function scheduleRetry() {
  if (retryTimer) clearTimeout(retryTimer);
  retryTimer = setTimeout(() => {
    retryTimer = null;
    flushOutbox();
  }, 2000);
}

// ---- 入队（由 api.js 拦截器调用） ----

export async function enqueueFailedRequest(kind, config) {
  const s = await store();
  if (!s) return null;
  // FormData/二进制载荷不入队（v1 只支持 JSON 载荷，见设计文档 §6.4）。
  if (typeof FormData !== "undefined" && config.data instanceof FormData) return null;
  const headers = config.headers || {};
  if (headers["X-Content-Password"] || headers["x-content-password"]) return null;

  const record = {
    kind: kind.kind,
    method: String(config.method || "post").toUpperCase(),
    url: config.url,
    body: typeof config.data === "string" ? config.data : config.data == null ? null : JSON.stringify(config.data),
    contentType: headers["Content-Type"] || headers["content-type"] || "application/json",
    ifMatch: headers["If-Match"] || headers["if-match"] || null,
    idempotencyKey: config.__outboxKey || null,
    createdAt: Date.now(),
    attempts: 0,
    nextAttemptAt: 0,
    lastError: null,
    status: "pending", // pending | conflict | dead
  };
  const id = await s.add(record);
  pendingCount.value = await countPending();
  enqueuedNotice.value += 1;
  scheduleFlushSoon();
  return { ...record, id };
}

// 入队后稍作等待再试一次（网络往往瞬断，多数情况能立即重放成功）。
let flushSoonTimer = null;
function scheduleFlushSoon() {
  if (flushSoonTimer) return;
  flushSoonTimer = setTimeout(() => {
    flushSoonTimer = null;
    flushOutbox();
  }, 1000);
}

// ---- 重放 ----

let flushPromise = null;

export function flushOutbox() {
  if (flushPromise) return flushPromise;
  flushPromise = drain().finally(() => {
    flushPromise = null;
  });
  return flushPromise;
}

async function drain() {
  if (authPaused.value || !isOnline.value) return;
  flushing.value = true;
  try {
    for (;;) {
      if (authPaused.value || !isOnline.value) return;
      const item = await nextDispatchable();
      if (!item) {
        lastQueueEmptyAt.value = Date.now();
        return;
      }
      try {
        await replayItem(item);
        await markDone(item);
      } catch (error) {
        const handled = await handleReplayFailure(item, error);
        if (handled === "auth") {
          authPaused.value = true;
          return;
        }
        if (handled === "retry") {
          scheduleRetry();
          return;
        }
        // "dead"/"conflict"/"done"：继续处理下一条。
      }
    }
  } finally {
    flushing.value = false;
    pendingCount.value = await countPending();
  }
}

function defaultSend(config) {
  // 延迟 import 避免循环依赖：api.js 引入本模块做入队，重放时才需要 api。
  // 动态 import 在打包后依然是同一实例。
  return import("../api").then(({ api }) => api.request(config));
}

// 测试可通过 setOutboxSender 注入假发送器；生产环境保持 defaultSend。
let sender = defaultSend;

export function setOutboxSender(fn) {
  sender = fn;
}

export function replayItem(item, send = sender) {
  const headers = { "Content-Type": item.contentType || "application/json" };
  if (item.ifMatch) headers["If-Match"] = item.ifMatch;
  if (item.idempotencyKey) headers["Idempotency-Key"] = item.idempotencyKey;
  return send({
    method: item.method,
    url: item.url,
    data: item.body == null ? undefined : item.body,
    headers,
    __outboxSkip: true, // 重放失败不再自动入队（已在队列里）
  });
}

async function markDone(item) {
  const s = await store();
  if (!s) return;
  const fresh = await s.get(item.id);
  if (fresh) await s.delete(item.id);
  pendingCount.value = await countPending();
}

async function handleReplayFailure(item, error) {
  const s = await store();
  if (!s) return "dead";
  const status = error?.response?.status;

  if (status === 401) return "auth";

  if (status === 409 && (item.kind === "article.update")) {
    return handleUpdateConflict(item);
  }

  if (status === 404 && (item.kind === "article.delete" || item.kind === "moment.delete")) {
    // 重放时资源已不存在：说明删除已经生效过，按成功处理。
    await s.delete(item.id);
    return "done";
  }

  const fresh = await s.get(item.id);
  if (!fresh) return "done";

  if (status && status >= 400 && status < 500) {
    // 校验类失败重放也不会成功：转死信，交由用户在队列面板处理。
    await s.put({ ...fresh, status: "dead", lastError: `HTTP ${status}` });
    return "dead";
  }

  // 网络类 / 5xx：退避重试；累计 8 次尝试仍失败转死信。
  const attempts = (fresh.attempts || 0) + 1;
  if (attempts >= OUTBOX_MAX_ATTEMPTS) {
    await s.put({ ...fresh, attempts, status: "dead", lastError: error?.message || "network error" });
    return "dead";
  }
  const delay = BACKOFF_MS[Math.min(attempts - 1, BACKOFF_MS.length - 1)];
  await s.put({
    ...fresh,
    attempts,
    nextAttemptAt: Date.now() + delay,
    lastError: error?.message || (status ? `HTTP ${status}` : "network error"),
  });
  return "retry";
}

/**
 * article.update 重放 409 的消歧：先拉服务端当前内容。
 * - 拉取失败（仍离线）：按可重试处理，下次再试；
 * - 服务端内容已等于待写内容：首次请求其实已生效，直接完成；
 * - 否则标记 conflict，等用户在队列面板选择「覆盖服务端」或「丢弃」。
 */
async function handleUpdateConflict(item) {
  let current = null;
  try {
    const aid = item.url.split("/").pop();
    const response = await sender({ method: "GET", url: `/v1/articles/${aid}` });
    current = response?.data ?? null;
  } catch {
    return "retry";
  }

  const expected = safeParse(item.body) || {};
  const serverTitle = current?.title ?? "";
  const serverBlocks = JSON.stringify(normalizeBlocks(current?.blocks));
  const localBlocks = JSON.stringify(normalizeBlocks(expected.blocks));
  if (serverTitle === (expected.title ?? "") && serverBlocks === localBlocks) {
    await markDone(item);
    return "done";
  }

  const s = await store();
  const fresh = await s.get(item.id);
  if (fresh) await s.put({ ...fresh, status: "conflict", lastError: "version_conflict" });
  return "conflict";
}

function safeParse(text) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function normalizeBlocks(blocks) {
  if (!Array.isArray(blocks)) return [];
  return blocks
    .map((block) => ({
      block_type: block?.block_type ?? "Paragraph",
      content: block?.content ?? "",
      sort_order: block?.sort_order ?? 0,
    }))
    .sort((a, b) => a.sort_order - b.sort_order);
}

// ---- 队列面板操作 ----

/** 用户选择「覆盖服务端」：以服务端当前版本重放（不带 If-Match）。 */
export async function overwriteConflict(item) {
  const s = await store();
  if (!s) return;
  const fresh = await s.get(item.id);
  if (!fresh) return;
  try {
    const response = await sender({ method: "GET", url: item.url });
    const version = response?.data?.__etag ?? response?.data?.version ?? null;
    await s.put({
      ...fresh,
      ifMatch: version == null ? null : String(version),
      status: "pending",
      nextAttemptAt: 0,
      attempts: 0,
      lastError: null,
    });
  } catch {
    // 拉不到当前版本（离线）：保留冲突态，稍后重试。
  }
  pendingCount.value = await countPending();
  flushOutbox();
}

/** 冲突/死信项的重试（校验错误修复后）。 */
export async function retryDeadItem(item) {
  const s = await store();
  if (!s) return;
  const fresh = await s.get(item.id);
  if (!fresh) return;
  await s.put({ ...fresh, status: "pending", attempts: 0, nextAttemptAt: 0, lastError: null });
  pendingCount.value = await countPending();
  flushOutbox();
}

/** 丢弃一个队列项（内容由用户在面板里查看/复制后自行处理）。 */
export async function dropOutboxItem(item) {
  const s = await store();
  if (!s) return;
  await s.delete(item.id);
  pendingCount.value = await countPending();
}

/** 登录成功后恢复队列（401 暂停的解除）。 */
export function resumeOutboxAfterAuth() {
  authPaused.value = false;
  flushOutbox();
}

export const outboxSummary = computed(() => ({
  pending: pendingCount.value,
  flushing: flushing.value,
  paused: authPaused.value,
}));
