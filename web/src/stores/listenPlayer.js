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
 * Cottage 一起听 (listen-together) persistent player singleton.
 *
 * The playback engine — the audio element, the sync WebSocket, the room state
 * and all the carefully-tuned sync logic — used to live inside
 * CottageListenView.vue, so leaving the page unmounted it and killed playback.
 *
 * This module hoists that engine to an app-level singleton (the same
 * module-level-refs pattern as stores/auth.js). The audio element is a plain
 * `new Audio()` that is NOT part of any component's DOM, so it keeps playing as
 * the user navigates around the site. CottageListenView renders the full UI
 * bound to this state, and ListenMiniPlayer renders a small floating control
 * everywhere else — both drive the same single engine.
 *
 * Sync behaviour is a faithful port of the original view; see the inline notes.
 */
import { computed, ref, watch } from "vue";
import { t } from "../locales";

import { fetchListenState, fetchMe } from "../lib/api";
import { clearDirectUrlCache, getDirectUrl } from "../lib/cottageListenAudio";
import { getLyric } from "../lib/cottageListenLyrics";
import { createListenSocket } from "../lib/cottageListenWs";

// ---------------------------------------------------------------------------
// Shared reactive state (module-level singleton)
// ---------------------------------------------------------------------------
function emptyCurrent() {
  return {
    song_id: null,
    song_meta: null,
    paused: true,
    position_ms: 0,
    started_by: null,
    event_seq: 0,
    server_ts_ms: 0
  };
}

const myUid = ref("");
const current = ref(emptyCurrent());
const queue = ref([]);
const partners = ref([]);
const lastAppliedEventSeq = ref(0);
const lastEventOriginUid = ref("");
const localPositionMs = ref(0);
const mediaDurationMs = ref(0);
const errorMsg = ref("");
const lyricLines = ref([]);
const lyricKind = ref("none");
const lyricLoading = ref(false);
const needsResumeGesture = ref(false);
const hasUserGesture = ref(false);
const connected = ref(false);
// True once init() has connected the socket — the mini-player only ever shows
// after the user has opened 一起听 at least once this session.
const active = ref(false);

// Non-reactive engine handles.
let audioEl = null;
let socket = null;
let heartbeatInterval = null;
let lyricReqId = 0;
let started = false;
let watchersBound = false;
let initPromise = null;
let lifecycleGeneration = 0;
let playbackRequestGeneration = 0;
let stateRequestGeneration = 0;

const meSelfLoggedIn = computed(() => {
  const me = (partners.value || []).find((p) => p.user_uid === myUid.value);
  return !!me?.netease_logged_in;
});

// ---------------------------------------------------------------------------
// Audio element (persists across navigation — never attached to the DOM)
// ---------------------------------------------------------------------------
function ensureAudio() {
  if (audioEl) return audioEl;
  audioEl = new Audio();
  audioEl.preload = "auto";
  audioEl.addEventListener("timeupdate", onTimeUpdate);
  audioEl.addEventListener("loadedmetadata", onLoadedMetadata);
  audioEl.addEventListener("ended", onEnded);
  audioEl.addEventListener("error", onAudioError);
  return audioEl;
}

function onTimeUpdate() {
  if (!audioEl) return;
  localPositionMs.value = Math.floor((audioEl.currentTime || 0) * 1000);
}

function onLoadedMetadata() {
  if (!audioEl) return;
  const dur = audioEl.duration;
  if (Number.isFinite(dur) && dur > 0) {
    mediaDurationMs.value = Math.floor(dur * 1000);
  }
}

function onAudioError() {
  errorMsg.value = t("listenPlayerStore.playFailed");
}

function onEnded() {
  const songId = current.value.song_id;
  if (songId) {
    sendCommand("NEXT", { expected_song_id: String(songId) }, { reportError: false });
  }
}

// ---------------------------------------------------------------------------
// Soft alignment & playback helpers
// ---------------------------------------------------------------------------
// 只在偏差超过容差时才 seek，避免正常播放被频繁微调打断（会造成音频卡顿）。
const SEEK_TOLERANCE_MS = 2000;

// 为什么不再做墙钟漂移补偿：早先版本会把目标位置加上 (Date.now() - server_ts_ms)
// 来补偿事件传输耗时。但这是拿「浏览器时钟」减「服务器时钟」——两台机器只要有
// 时钟偏差（后端跑在 Docker/WSL 时，其时钟落后 Windows 宿主机几秒是常见现象），
// 偏差就会被当成漂移直接灌进播放头：开播跳到 ~9 秒、每次暂停→播放又继续往前跳。
// 服务端 get_current_position_ms 已按服务器时钟算好「活的」播放头供 /state 使用，
// WS 事件也携带刚采样的位置，传输延迟是亚秒级、本就落在 SEEK_TOLERANCE_MS 内，
// 因此直接对齐上报位置既正确、又不受时钟偏差影响。
function softAlign(targetPositionMs) {
  if (!audioEl) return;
  const target = Math.max(0, Number(targetPositionMs) || 0);
  const localMs = (audioEl.currentTime || 0) * 1000;
  if (Math.abs(target - localMs) > SEEK_TOLERANCE_MS) {
    try {
      audioEl.currentTime = target / 1000;
    } catch (_) { /* ignore */ }
  }
}

async function hydrateAndPlay(songId, positionMs) {
  ensureAudio();
  if (!songId) return;

  const requestGeneration = ++playbackRequestGeneration;
  const lifecycle = lifecycleGeneration;

  const { url, error_kind } = await getDirectUrl(songId);
  if (
    lifecycle !== lifecycleGeneration ||
    requestGeneration !== playbackRequestGeneration ||
    String(current.value.song_id || "") !== String(songId) ||
    current.value.paused
  ) {
    return;
  }
  if (!url) {
    errorMsg.value = error_kind === "unavailable"
      ? t("listenPlayerStore.songUnavailable")
      : t("listenPlayerStore.directUrlFailed");
    return;
  }
  errorMsg.value = "";

  try {
    if (audioEl.src !== url) {
      audioEl.src = url;
    }
    softAlign(positionMs);
    try {
      await audioEl.play();
      if (
        lifecycle !== lifecycleGeneration ||
        requestGeneration !== playbackRequestGeneration ||
        current.value.paused
      ) {
        audioEl.pause();
        return;
      }
      needsResumeGesture.value = false;
    } catch (playError) {
      if (!hasUserGesture.value) {
        // Browser autoplay gate (no user gesture yet — almost always a refresh).
        // The room keeps playing on the partner's side; surface a one-tap resume
        // instead of broadcasting anything that would reset the shared position.
        if (!current.value.paused && current.value.song_id) {
          needsResumeGesture.value = true;
          try {
            audioEl.load();
          } catch (_) { /* ignore */ }
        } else {
          errorMsg.value = t("listenPlayerStore.clickToPlay");
        }
      } else {
        errorMsg.value = t("listenPlayerStore.playFailedReason", { reason: playError.message });
      }
    }
  } catch (error) {
    errorMsg.value = t("listenPlayerStore.playError", { reason: error.message });
  }
}

// Hard-stop the underlying audio element (updating `current` only repaints UI).
function stopPlayback() {
  playbackRequestGeneration += 1;
  if (!audioEl) return;
  try {
    audioEl.pause();
    audioEl.currentTime = 0;
  } catch (_) { /* ignore */ }
  localPositionMs.value = 0;
}

// ---------------------------------------------------------------------------
// WS event application
// ---------------------------------------------------------------------------
function patchPartnerLoggedIn(uid, logged) {
  if (!uid) return;
  partners.value = (partners.value || []).map((p) =>
    p.user_uid === uid ? { ...p, netease_logged_in: logged } : p
  );
}

function applyEvent(e) {
  // Drop stale events. System events (LOGIN_OK / LOGOUT / COOKIE_EXPIRED)
  // come without an event_seq from the server; let those through.
  if (typeof e.event_seq === "number" && e.event_seq <= lastAppliedEventSeq.value) {
    return;
  }
  if (typeof e.event_seq === "number") {
    lastAppliedEventSeq.value = e.event_seq;
  }
  if (e.origin_uid) {
    lastEventOriginUid.value = e.origin_uid;
  }

  switch (e.type) {
    case "PLAY":
      current.value = {
        ...current.value,
        song_id: e.payload.song_id,
        song_meta: e.payload.song_meta || current.value.song_meta,
        paused: false,
        position_ms: Number(e.payload.position_ms || 0),
        started_by: e.origin_uid,
        event_seq: e.event_seq,
        server_ts_ms: e.server_ts_ms
      };
      hydrateAndPlay(e.payload.song_id, Number(e.payload.position_ms || 0));
      break;
    case "PAUSE":
      current.value = {
        ...current.value,
        paused: true,
        position_ms: Number(e.payload.position_ms || 0),
        event_seq: e.event_seq ?? current.value.event_seq,
        server_ts_ms: e.server_ts_ms
      };
      try {
        audioEl && audioEl.pause();
      } catch (_) { /* ignore */ }
      softAlign(Number(e.payload.position_ms || 0));
      break;
    case "SEEK":
      current.value = {
        ...current.value,
        position_ms: Number(e.payload.position_ms || 0),
        event_seq: e.event_seq ?? current.value.event_seq,
        server_ts_ms: e.server_ts_ms
      };
      softAlign(Number(e.payload.position_ms || 0));
      break;
    case "NEXT":
    case "PREV": {
      const advancedId = e.type === "NEXT" ? (e.payload?.song_id || null) : null;
      if (e.type === "NEXT" && advancedId) {
        const fromQueue = queue.value.find(
          (q) => String(q.song_id) === String(advancedId)
        );
        const meta = e.payload?.song_meta || fromQueue || {
          song_id: advancedId,
          name: "",
          artists: []
        };
        current.value = {
          ...current.value,
          song_id: advancedId,
          song_meta: meta,
          paused: false,
          position_ms: 0,
          started_by: e.origin_uid,
          event_seq: e.event_seq,
          server_ts_ms: e.server_ts_ms
        };
        queue.value = queue.value.slice(1);
        hydrateAndPlay(advancedId, 0);
      } else if (e.type === "NEXT") {
        current.value = {
          ...current.value,
          song_id: null,
          song_meta: null,
          paused: true,
          position_ms: 0,
          started_by: null,
          event_seq: e.event_seq,
          server_ts_ms: e.server_ts_ms
        };
        queue.value = [];
        stopPlayback();
      } else {
        // PREV — restart the current song from 0 (re-sync via state).
        reloadState();
      }
      break;
    }
    case "QUEUE_APPEND": {
      const sid = String(e.payload?.song_id || "");
      if (sid) {
        const songMeta = e.payload?.song_meta || { song_id: sid, name: "", artists: [] };
        queue.value = [...queue.value, songMeta];
      }
      break;
    }
    case "QUEUE_REMOVE": {
      const idx = e.payload?.index;
      if (Number.isInteger(idx) && idx >= 0) {
        queue.value = queue.value.filter((_, i) => i !== idx);
      } else if (e.payload?.song_id) {
        const matchIndex = queue.value.findIndex(
          (song) => String(song.song_id) === String(e.payload.song_id)
        );
        if (matchIndex !== -1) {
          queue.value = queue.value.filter((_, i) => i !== matchIndex);
        }
      }
      break;
    }
    case "QUEUE_CLEAR":
      queue.value = [];
      break;
    case "LOGIN_OK":
      patchPartnerLoggedIn(e.payload?.user_uid, true);
      break;
    case "LOGOUT":
      patchPartnerLoggedIn(e.payload?.user_uid, false);
      break;
    case "COOKIE_EXPIRED":
      patchPartnerLoggedIn(e.payload?.user_uid, false);
      if (e.payload?.user_uid === myUid.value) {
        errorMsg.value = t("listenPlayerStore.selfCookieExpired");
      } else {
        errorMsg.value = t("listenPlayerStore.partnerCookieExpired");
      }
      break;
    case "AUTO_PAUSED":
      errorMsg.value = t("listenPlayerStore.autoPaused");
      reloadState();
      break;
    default:
      break;
  }
}

// ---------------------------------------------------------------------------
// Lyric loading
// ---------------------------------------------------------------------------
async function loadLyric(songId) {
  if (!songId) {
    lyricLines.value = [];
    lyricKind.value = "none";
    lyricLoading.value = false;
    return;
  }
  const reqId = ++lyricReqId;
  lyricLoading.value = true;
  try {
    const data = await getLyric(songId);
    if (reqId !== lyricReqId) return;
    lyricLines.value = data.lines || [];
    lyricKind.value = data.kind || "none";
  } catch (_) {
    if (reqId !== lyricReqId) return;
    lyricLines.value = [];
    lyricKind.value = "none";
  } finally {
    if (reqId === lyricReqId) lyricLoading.value = false;
  }
}

// ---------------------------------------------------------------------------
// Heartbeat
// ---------------------------------------------------------------------------
function sendHeartbeat() {
  // socket.send guards on the underlying readyState internally.
  socket?.send({ type: "HEARTBEAT", payload: {} });
}

function startHeartbeat() {
  stopHeartbeat();
  sendHeartbeat();
  heartbeatInterval = setInterval(sendHeartbeat, 30000);
}

function stopHeartbeat() {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }
}

// ---------------------------------------------------------------------------
// Room state
// ---------------------------------------------------------------------------
async function reloadState() {
  const requestGeneration = ++stateRequestGeneration;
  const lifecycle = lifecycleGeneration;
  try {
    const data = await fetchListenState();
    if (
      lifecycle !== lifecycleGeneration ||
      requestGeneration !== stateRequestGeneration
    ) {
      return false;
    }

    // Queue-only events do not change current.event_seq. The room-level
    // sequence is the commit marker for the complete current + queue snapshot.
    const snapshotSeq = Number(data.event_seq ?? data.current?.event_seq ?? 0);
    // A WS event may arrive while this REST request is in flight. Never let
    // that older snapshot rewind the song, queue, pause state, or position.
    if (snapshotSeq < lastAppliedEventSeq.value) {
      return false;
    }

    current.value = { ...emptyCurrent(), ...(data.current || {}) };
    queue.value = (data.queue || []).map((item) => {
      if (typeof item === "string") {
        return { song_id: item, name: "", artists: [], album: null, duration_ms: null, cover_url: null };
      }
      return {
        song_id: item.song_id || "",
        name: item.name || "",
        artists: item.artists || [],
        album: item.album || null,
        duration_ms: item.duration_ms || null,
        cover_url: item.cover_url || null
      };
    });
    partners.value = data.partners || [];
    lastAppliedEventSeq.value = Math.max(
      lastAppliedEventSeq.value,
      snapshotSeq
    );
    localPositionMs.value = Number(current.value.position_ms || 0);
    if (current.value.song_id && !current.value.paused) {
      hydrateAndPlay(
        current.value.song_id,
        current.value.position_ms || 0
      );
    } else if (!current.value.song_id) {
      stopPlayback();
    } else {
      try {
        audioEl && audioEl.pause();
      } catch (_) { /* ignore */ }
      softAlign(current.value.position_ms || 0);
    }
    return true;
  } catch (_error) {
    if (lifecycle === lifecycleGeneration && requestGeneration === stateRequestGeneration) {
      errorMsg.value = t("listenPlayerStore.loadStateFailed");
    }
    return false;
  }
}

// ---------------------------------------------------------------------------
// User intents -> WS sends
// ---------------------------------------------------------------------------
function sendCommand(type, payload = {}, { reportError = true } = {}) {
  const sent = socket?.send({ type, payload }) === true;
  if (!sent && reportError) {
    connected.value = false;
    errorMsg.value = t("listenPlayerStore.disconnected");
  }
  return sent;
}

function onResume() {
  hasUserGesture.value = true;
  if (!current.value.song_id) return false;
  return sendCommand("PLAY", {
    song_id: current.value.song_id,
    position_ms: localPositionMs.value || current.value.position_ms || 0
  });
}

// Tapped "continue" after autoplay was blocked: re-join the partner's LIVE
// playback locally and DO NOT broadcast, so the shared position isn't reset.
function onResumeLocalPlayback() {
  hasUserGesture.value = true;
  needsResumeGesture.value = false;
  if (!current.value.song_id) return;
  hydrateAndPlay(
    current.value.song_id,
    current.value.position_ms || 0
  );
}

function onPause() {
  return sendCommand("PAUSE", { position_ms: localPositionMs.value });
}

function onSeek(ms) {
  hasUserGesture.value = true;
  return sendCommand("SEEK", { position_ms: Number(ms) || 0 });
}

function onPrev() {
  hasUserGesture.value = true;
  return sendCommand("PREV");
}

function onNext() {
  hasUserGesture.value = true;
  return sendCommand("NEXT");
}

function onAppendToQueue(song) {
  return sendCommand("QUEUE_APPEND", {
    song_id: String(song.song_id),
    song_meta: {
      song_id: String(song.song_id),
      name: song.name || "",
      artists: song.artists || [],
      album: song.album || null,
      duration_ms: song.duration_ms || null,
      cover_url: song.cover_url || null
    }
  });
}

function onPlayNow(song) {
  hasUserGesture.value = true;
  return sendCommand("PLAY", {
    song_id: String(song.song_id),
    position_ms: 0,
    song_meta: {
      song_id: String(song.song_id),
      name: song.name || "",
      artists: song.artists || [],
      album: song.album || null,
      duration_ms: song.duration_ms || null,
      cover_url: song.cover_url || null
    }
  });
}

function onQueueRemove(payload) {
  return sendCommand("QUEUE_REMOVE", payload);
}

function onQueueClear() {
  return sendCommand("QUEUE_CLEAR");
}

function onLoginSuccess() {
  if (myUid.value) patchPartnerLoggedIn(myUid.value, true);
  errorMsg.value = "";
}

function onLogoutLocal() {
  if (myUid.value) patchPartnerLoggedIn(myUid.value, false);
}

// ---------------------------------------------------------------------------
// Watchers + init
// ---------------------------------------------------------------------------
function bindWatchers() {
  if (watchersBound) return;
  watchersBound = true;
  // Every code path that changes the current song rewrites current.song_id, so
  // this single watcher refreshes the lyric and resets the decoded duration.
  watch(() => current.value.song_id, (songId) => {
    mediaDurationMs.value = 0;
    loadLyric(songId);
  });
  // Drop the resume affordance if the room stops/empties while we were waiting.
  watch(
    () => current.value.paused || !current.value.song_id,
    (stopped) => {
      if (stopped) needsResumeGesture.value = false;
    }
  );
}

async function init() {
  if (started) return initPromise;
  started = true;
  active.value = true;
  const lifecycle = ++lifecycleGeneration;

  initPromise = (async () => {
    ensureAudio();
    bindWatchers();
    try {
      const me = await fetchMe();
      if (lifecycle !== lifecycleGeneration) return;
      myUid.value = me?.uid || "";
    } catch (_) {
      if (lifecycle !== lifecycleGeneration) return;
    }

    await reloadState();
    if (lifecycle !== lifecycleGeneration) return;

    socket = createListenSocket({
      onEvent: (event) => {
        if (lifecycle === lifecycleGeneration) applyEvent(event);
      },
      onOpen: () => {
        if (lifecycle !== lifecycleGeneration) return;
        connected.value = true;
        if (errorMsg.value === t("listenPlayerStore.disconnected")) errorMsg.value = "";
        startHeartbeat();
        // Reconcile events missed while disconnected. reloadState rejects a
        // snapshot if a newer WS event arrives during the request.
        void reloadState();
      },
      onClose: () => {
        if (lifecycle !== lifecycleGeneration) return;
        connected.value = false;
        stopHeartbeat();
      }
    });
  })().finally(() => {
    if (lifecycle === lifecycleGeneration) initPromise = null;
  });

  return initPromise;
}

export function disposeListenPlayer() {
  lifecycleGeneration += 1;
  stateRequestGeneration += 1;
  playbackRequestGeneration += 1;
  lyricReqId += 1;
  stopHeartbeat();
  connected.value = false;
  started = false;
  initPromise = null;
  active.value = false;

  if (socket) {
    socket.close();
    socket = null;
  }

  if (audioEl) {
    try {
      audioEl.pause();
      audioEl.currentTime = 0;
    } catch (_) { /* ignore */ }
    audioEl.removeEventListener("timeupdate", onTimeUpdate);
    audioEl.removeEventListener("loadedmetadata", onLoadedMetadata);
    audioEl.removeEventListener("ended", onEnded);
    audioEl.removeEventListener("error", onAudioError);
    try {
      audioEl.removeAttribute("src");
      audioEl.load();
    } catch (_) { /* ignore */ }
    audioEl = null;
  }

  clearDirectUrlCache();
  myUid.value = "";
  current.value = emptyCurrent();
  queue.value = [];
  partners.value = [];
  lastAppliedEventSeq.value = 0;
  lastEventOriginUid.value = "";
  localPositionMs.value = 0;
  mediaDurationMs.value = 0;
  errorMsg.value = "";
  lyricLines.value = [];
  lyricKind.value = "none";
  lyricLoading.value = false;
  needsResumeGesture.value = false;
  hasUserGesture.value = false;
}

export function useListenPlayer() {
  return {
    // state
    myUid,
    current,
    queue,
    partners,
    localPositionMs,
    mediaDurationMs,
    errorMsg,
    lyricLines,
    lyricKind,
    lyricLoading,
    needsResumeGesture,
    lastEventOriginUid,
    meSelfLoggedIn,
    active,
    connected,
    // lifecycle + intents
    init,
    dispose: disposeListenPlayer,
    onResume,
    onResumeLocalPlayback,
    onPause,
    onSeek,
    onPrev,
    onNext,
    onAppendToQueue,
    onPlayNow,
    onQueueRemove,
    onQueueClear,
    onLoginSuccess,
    onLogoutLocal
  };
}
