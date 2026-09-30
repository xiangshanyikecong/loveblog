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

const APP_ORIGIN = self.location.origin;
const CACHE_NAME = "love-node-v1";
// 运行时缓存（P2，见 docs/design/WEB_OFFLINE_WEAK_NETWORK_DESIGN.md §7）：
// 与应用壳缓存分开命名，登出时单独清理。
const RUNTIME_CACHE_NAME = "love-node-runtime-v1";
const RUNTIME_CACHE_MAX_ENTRIES = 300;
const APP_SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icons/icon.svg", "/icons/icon-maskable.svg"];

// 允许离线回退的只读 API（network-first）。只收录情侣双方的私有内容，
// 绝不缓存 /v1/listen/**（R8.4 永不持久化）、/v1/admin/**、/v1/auth/**、
// /v1/push/**，以及带 X-Content-Password 头的密码保护内容请求。
const API_READONLY_CACHE = [
  /^\/v1\/dashboard$/,
  /^\/v1\/timeline$/,
  /^\/v1\/timeline\/memories$/,
  /^\/v1\/articles$/,
  /^\/v1\/articles\/[^/]+$/,
  /^\/v1\/albums$/,
  /^\/v1\/albums\/[^/]+$/,
  /^\/v1\/checkins$/,
];

// axios baseURL 默认为 "/api"，请求 URL 形如 /api/v1/...；自托管自定义
// baseURL 时可能直接是 /v1/...。统一剥掉 "/api" 前缀再匹配。
function normalizeApiPath(pathname) {
  return pathname.startsWith("/api/") ? pathname.slice(4) : pathname;
}

function isCacheableApiRequest(req, url) {
  if (req.headers && req.headers.get("x-content-password")) return false;
  const path = normalizeApiPath(url.pathname);
  return API_READONLY_CACHE.some((pattern) => pattern.test(path));
}

function isImagePathResponse(res) {
  const type = res?.headers?.get("content-type") || "";
  return type.startsWith("image/");
}

async function putRuntimeCache(req, res) {
  const cache = await caches.open(RUNTIME_CACHE_NAME);
  await cache.put(req, res.clone());
  const keys = await cache.keys();
  while (keys.length > RUNTIME_CACHE_MAX_ENTRIES) {
    const oldest = keys.shift();
    await cache.delete(oldest);
  }
}

function withNotificationId(link, nid) {
  // Notification links are server-controlled, but a restored archive could
  // smuggle an absolute cross-origin URL (see _safe_notification_link on the
  // backend). Never navigate off-origin from a notification tap; default to
  // the in-app notifications page instead.
  let target;
  try {
    target = new URL(link || "/notifications", APP_ORIGIN);
  } catch {
    target = new URL("/notifications", APP_ORIGIN);
  }
  if (target.origin !== APP_ORIGIN) {
    target = new URL("/notifications", APP_ORIGIN);
  }
  if (nid) {
    target.searchParams.set("_nid", nid);
  }
  return target.toString();
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL).catch(() => {}))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME && k !== RUNTIME_CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// 登出清库联动：页面通过 postMessage 通知 SW 清空运行时缓存（图片 +
// 只读 API 快照）。应用壳是公开静态资源，无需清理。覆盖共享电脑场景。
self.addEventListener("message", (event) => {
  if (event.data?.type === "LOVE_CLEAR_OFFLINE_CACHE") {
    event.waitUntil(caches.delete(RUNTIME_CACHE_NAME));
  }
});

// ── Offline caching strategy ──────────────────────────────────────
// - Navigation requests: network-first, fall back to cached shell.
// - Same-origin static assets: stale-while-revalidate.
// - Whitelisted read-only API calls (dashboard/timeline/articles/albums/
//   checkins): network-first, fall back to the last successful JSON copy.
// - /uploads/ images: cache-first (bounded).
// - Everything else (writes, auth, listen, admin, push, cross-origin):
//   network only (never cache).
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== APP_ORIGIN) return;

  // Whitelisted read-only API: network-first with offline fallback.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/v1/")) {
    if (!isCacheableApiRequest(req, url)) return;
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.status === 200) {
            putRuntimeCache(req, res).catch(() => {});
          }
          return res;
        })
        .catch(() => caches.match(req)),
    );
    return;
  }

  // Uploads (images): cache-first, bounded, to speed up repeat views and
  // allow offline browsing of recently seen pictures.
  if (url.pathname.startsWith("/uploads/")) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((res) => {
          if (res && res.status === 200 && isImagePathResponse(res)) {
            putRuntimeCache(req, res).catch(() => {});
          }
          return res;
        });
      }),
    );
    return;
  }

  // Don't intercept WebSocket upgrades.
  if (url.pathname.startsWith("/ws/")) return;

  // Navigation requests: network-first with offline fallback.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match("/index.html"))),
    );
    return;
  }

  // Static assets: stale-while-revalidate.
  event.respondWith(
    caches.match(req).then((cached) => {
      const fetchPromise = fetch(req)
        .then((res) => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => cached);
      return cached || fetchPromise;
    }),
  );
});

// ── Push notifications ────────────────────────────────────────────
self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { title: "恋爱记", body: event.data ? event.data.text() : "" };
  }

  const title = payload.title || "恋爱记";
  const options = {
    body: payload.body || "",
    icon: "/icons/icon.svg",
    badge: "/icons/icon.svg",
    tag: payload.nid || payload.type || "love-node-notification",
    data: {
      nid: payload.nid || null,
      link: payload.link || "/notifications"
    }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const nid = event.notification?.data?.nid || null;
  const link = event.notification?.data?.link || "/notifications";
  const targetUrl = withNotificationId(link, nid);

  event.waitUntil(
    (async () => {
      const clientsList = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of clientsList) {
        try {
          const url = new URL(client.url);
          if (url.origin !== APP_ORIGIN) {
            continue;
          }
          await client.focus();
          if ("navigate" in client) {
            await client.navigate(targetUrl);
          }
          client.postMessage({ type: "notification-click", nid, link });
          return;
        } catch {
          // Fall through to opening a fresh window.
        }
      }

      const opened = await self.clients.openWindow(targetUrl);
      if (opened) {
        opened.postMessage({ type: "notification-click", nid, link });
      }
    })()
  );
});
