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

/**
 * WebSocket client wrapper for cottage-listen-together.
 *
 * Features:
 * - Auto-reconnect with exponential backoff (1s, 2s, 4s, ..., capped at 30s).
 * - Application-level keepalive: send {type:"PING"} every 25s; if no PONG
 *   in 60s, treat the connection as dead and force a reconnect.
 * - Inbound PING/PONG handled internally; everything else is forwarded
 *   to onEvent (the consumer's lastAppliedEventSeq dedupe runs there).
 *
 * URL derivation: the backend's WS endpoint is exposed under the same path
 * as REST (the Vite proxy and nginx both pass `/v1/cottage/listen/ws`
 * through). We compute ws/wss + host/port from window.location.
 */

import { apiBaseURL } from "./api";

const PING_INTERVAL_MS = 25_000;
const PONG_TIMEOUT_MS = 60_000;
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

function deriveWsUrl() {
  // apiBaseURL is either "/api" (relative — same origin) or an absolute URL.
  // We want ws[s]://<host>/<apiBase>/v1/cottage/listen/ws.
  const path = "/v1/cottage/listen/ws";

  if (typeof window === "undefined") {
    return `ws://localhost:8000${path}`;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  if (apiBaseURL.startsWith("http://") || apiBaseURL.startsWith("https://")) {
    const u = new URL(apiBaseURL);
    return `${proto}//${u.host}${u.pathname.replace(/\/$/, "")}${path}`;
  }
  // Relative — use current origin.
  const base = apiBaseURL === "/" ? "" : apiBaseURL.replace(/\/$/, "");
  return `${proto}//${window.location.host}${base}${path}`;
}

export function createListenSocket({ onEvent, onOpen, onClose }) {
  let ws = null;
  let pingTimer = null;
  let pongDeadlineTimer = null;
  let reconnectTimer = null;
  let reconnectAttempts = 0;
  let closedByUser = false;

  function clearTimers() {
    if (pingTimer) {
      clearInterval(pingTimer);
      pingTimer = null;
    }
    if (pongDeadlineTimer) {
      clearTimeout(pongDeadlineTimer);
      pongDeadlineTimer = null;
    }
  }

  function schedulePongDeadline() {
    if (pongDeadlineTimer) clearTimeout(pongDeadlineTimer);
    pongDeadlineTimer = setTimeout(() => {
      // No PONG within window — force reconnect.
      try {
        ws && ws.close();
      } catch (_) {
        /* ignore */
      }
    }, PONG_TIMEOUT_MS);
  }

  function startPing() {
    if (pingTimer) clearInterval(pingTimer);
    pingTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: "PING" }));
          schedulePongDeadline();
        } catch (_) {
          /* ignore */
        }
      }
    }, PING_INTERVAL_MS);
    schedulePongDeadline();
  }

  function open() {
    if (closedByUser) return;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    const url = deriveWsUrl();
    ws = new WebSocket(url);

    ws.addEventListener("open", () => {
      reconnectAttempts = 0;
      startPing();
      try {
        onOpen && onOpen();
      } catch (_) {
        /* ignore */
      }
    });

    ws.addEventListener("message", (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch (_) {
        return;
      }
      if (!msg || typeof msg !== "object") return;
      if (msg.type === "PONG") {
        // Reset the pong deadline.
        schedulePongDeadline();
        return;
      }
      try {
        onEvent && onEvent(msg);
      } catch (e) {
        // Don't let consumer exceptions break the socket.
        // eslint-disable-next-line no-console
        console.error("[listen-ws] onEvent threw:", e);
      }
    });

    ws.addEventListener("close", (event) => {
      clearTimers();
      try {
        onClose && onClose(event);
      } catch (_) {
        /* ignore */
      }
      if (closedByUser) return;
      // Don't reconnect on auth failures (4401 / 4403).
      if (event.code === 4401 || event.code === 4403) return;
      // Backoff and retry.
      const delay = Math.min(
        RECONNECT_MAX_MS,
        RECONNECT_BASE_MS * Math.pow(2, reconnectAttempts)
      );
      reconnectAttempts += 1;
      reconnectTimer = setTimeout(open, delay);
    });

    ws.addEventListener("error", () => {
      // The close handler will fire next; don't duplicate logic here.
    });
  }

  open();

  return {
    send(msg) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify(msg));
          return true;
        } catch (_) {
          return false;
        }
      }
      return false;
    },
    close() {
      closedByUser = true;
      clearTimers();
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (ws) {
        try {
          ws.close();
        } catch (_) {
          /* ignore */
        }
      }
    },
    get isOpen() {
      return ws && ws.readyState === WebSocket.OPEN;
    }
  };
}
