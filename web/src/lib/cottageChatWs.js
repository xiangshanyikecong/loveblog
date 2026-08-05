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
 * WebSocket client wrapper for the cottage realtime channel (presence + chat
 * + poke). Mirrors cottageListenWs.js: auto-reconnect with exponential
 * backoff, application-level PING/PONG keepalive, inbound events forwarded to
 * onEvent.
 *
 * Endpoint: `/v1/cottage/chat/ws` (the Vite proxy and nginx pass it through).
 */

import { apiBaseURL } from "./api";

const PING_INTERVAL_MS = 25_000;
const PONG_TIMEOUT_MS = 60_000;
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

function deriveWsUrl() {
  const path = "/v1/cottage/chat/ws";

  if (typeof window === "undefined") {
    return `ws://localhost:8000${path}`;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  if (apiBaseURL.startsWith("http://") || apiBaseURL.startsWith("https://")) {
    const u = new URL(apiBaseURL);
    return `${proto}//${u.host}${u.pathname.replace(/\/$/, "")}${path}`;
  }
  const base = apiBaseURL === "/" ? "" : apiBaseURL.replace(/\/$/, "");
  return `${proto}//${window.location.host}${base}${path}`;
}

export function createCottageSocket({ onEvent, onOpen, onClose } = {}) {
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
        schedulePongDeadline();
        return;
      }
      try {
        onEvent && onEvent(msg);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error("[cottage-ws] onEvent threw:", e);
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
      if (event.code === 4401 || event.code === 4403) return;
      const delay = Math.min(
        RECONNECT_MAX_MS,
        RECONNECT_BASE_MS * Math.pow(2, reconnectAttempts)
      );
      reconnectAttempts += 1;
      reconnectTimer = setTimeout(open, delay);
    });

    ws.addEventListener("error", () => {
      // close handler will fire next.
    });
  }

  open();

  return {
    send(msg) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify(msg));
        } catch (_) {
          /* ignore */
        }
      }
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
