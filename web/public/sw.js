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
const APP_SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icons/icon.svg", "/icons/icon-maskable.svg"];

function withNotificationId(link, nid) {
  const target = new URL(link || "/notifications", APP_ORIGIN);
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
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// ── Offline caching strategy ──────────────────────────────────────
// - Navigation requests: network-first, fall back to cached shell.
// - Same-origin static assets: stale-while-revalidate.
// - API calls and cross-origin: network only (never cache).
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== APP_ORIGIN) return;
  // Don't intercept API calls or WebSocket upgrades.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/v1/")) return;

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
