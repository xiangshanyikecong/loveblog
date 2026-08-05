<!--
  Love Journal - a private journal + blog + real-time interaction platform for couples.
  Copyright (C) 2026 Love Journal Contributors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU Affero General Public License as published
  by the Free Software Foundation, version 3 of the License.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Affero General Public License for more details.

  You should have received a copy of the GNU Affero General Public License
  along with this program.  If not, see <https://www.gnu.org/licenses/>.
-->

<template>
  <div class="content-section watch">
    <header class="watch-header">
      <div class="watch-title">
        <h2>{{ t('cottageWatch.title') }}</h2>
        <span class="watch-presence">
          <span
            v-for="p in partners"
            :key="p.user_uid"
            class="presence-dot"
            :class="{ online: p.online }"
            :title="p.online ? t('cottageWatch.presenceOnline', { name: p.nickname || '' }) : t('cottageWatch.presenceOffline', { name: p.nickname || '' })"
          >{{ p.nickname }}</span>
        </span>
      </div>
      <div class="watch-actions">
        <button class="watch-btn" type="button" @click="onInvite">{{ t('cottageWatch.invite') }}</button>
        <router-link to="/cottage" class="watch-back">{{ t('cottageWatch.backToCottage') }}</router-link>
      </div>
    </header>

    <p v-if="toast" class="watch-toast">{{ toast }}</p>
    <p v-if="errorMsg" class="watch-error">{{ errorMsg }}</p>

    <!-- Player -->
    <article class="glass-card watch-player-card">
      <div v-if="current.source_url" class="watch-now">
        {{ t('cottageWatch.nowWatching') }}<strong>{{ current.source_title || t('cottageWatch.untitled') }}</strong>
        <span v-if="startedByLabel" class="watch-now-by">{{ t('cottageWatch.startedBy', { name: startedByLabel }) }}</span>
        <button
          v-if="resumePrompt"
          class="watch-resume-pill"
          type="button"
          @click="onResumeFromBookmark"
        >{{ resumePrompt }} ↪</button>
      </div>

      <div class="watch-stage">
        <video
          ref="videoRef"
          class="watch-video"
          controls
          playsinline
          preload="auto"
          @play="onLocalPlay"
          @pause="onLocalPause"
          @seeked="onLocalSeeked"
          @ratechange="onLocalRateChange"
          @timeupdate="onTimeUpdate"
          @error="onVideoError"
        ></video>

        <div v-if="!current.source_url" class="watch-empty">
          {{ t('cottageWatch.emptySource') }}
        </div>

        <button
          v-if="needsResumeGesture"
          class="watch-resume"
          type="button"
          @click="onResumeLocal"
        >{{ t('cottageWatch.resumeGesture') }}</button>
      </div>

      <p class="watch-hint">
        {{ t('cottageWatch.hint') }}
      </p>
    </article>

    <!-- Library -->
    <section class="glass-card watch-library">
      <h3 class="watch-section-title">{{ t('cottageWatch.library') }}</h3>

      <div class="watch-add">
        <input
          v-model="newTitle"
          class="watch-input"
          type="text"
          :placeholder="t('cottageWatch.titlePlaceholder')"
          maxlength="200"
        />
        <input
          v-model="newUrl"
          class="watch-input"
          type="text"
          :placeholder="t('cottageWatch.urlPlaceholder')"
          maxlength="4000"
        />
        <input
          v-model="newPoster"
          class="watch-input"
          type="text"
          :placeholder="t('cottageWatch.posterPlaceholder')"
          maxlength="4000"
        />
        <button class="watch-btn" type="button" :disabled="!newUrl.trim()" @click="onAddUrl">
          {{ t('cottageWatch.addUrl') }}
        </button>
      </div>

      <div class="watch-upload">
        <label class="watch-btn watch-upload-btn">
          {{ t('cottageWatch.uploadFile') }}
          <input
            type="file"
            accept="video/mp4,video/webm,video/quicktime,video/x-matroska"
            hidden
            @change="onPickFile"
          />
        </label>
        <span v-if="uploadProgress !== null" class="watch-progress">
          {{ t('cottageWatch.uploading', { progress: uploadProgress }) }}
        </span>
        <span class="watch-upload-hint">{{ t('cottageWatch.uploadHint') }}</span>
      </div>

      <div v-if="sources.length" class="watch-poster-grid">
        <article
          v-for="s in sources"
          :key="s.wsid"
          class="watch-poster-card"
          :class="{ active: current.source_wsid === s.wsid }"
        >
          <button
            class="watch-poster-face"
            type="button"
            :title="t('cottageWatch.playTitle', { title: s.title })"
            @click="onLoadSource(s)"
          >
            <img
              v-if="s.poster_url"
              :src="resolveAssetUrl(s.poster_url)"
              :alt="s.title"
              class="watch-poster-img"
              loading="lazy"
              @error="onPosterError($event, s.wsid)"
            />
            <span v-else class="watch-poster-fallback" :style="fallbackStyle(s.title)">
              {{ initialOf(s.title) }}
            </span>
            <span class="watch-poster-overlay">
              <span class="watch-poster-play">▶</span>
            </span>
            <span class="watch-poster-tag">{{ s.kind === "upload" ? t('cottageWatch.kindLocal') : t('cottageWatch.kindDirect') }}</span>
            <span
              v-if="resumeLabelFor(s)"
              class="watch-poster-progress"
            >{{ resumeLabelFor(s) }}</span>
          </button>
          <div class="watch-poster-meta">
            <p class="watch-poster-name" :title="s.title">{{ s.title }}</p>
            <p class="watch-poster-sub">
              <span v-if="s.size_bytes">{{ formatSize(s.size_bytes) }}</span>
              <span v-if="s.author_nickname">· {{ s.author_nickname }}</span>
            </p>
          </div>
          <div class="watch-poster-ops">
            <button class="watch-mini-btn" type="button" @click="onEditSource(s)">{{ t('cottageWatch.edit') }}</button>
            <button class="watch-mini-btn" type="button" @click="onDeleteSource(s)">{{ t('cottageWatch.delete') }}</button>
          </div>
        </article>
      </div>
      <p v-else class="watch-empty-lib">{{ t('cottageWatch.emptyLibrary') }}</p>

      <!-- Inline edit panel for title / poster -->
      <div v-if="editing" class="watch-edit-panel">
        <h4 class="watch-section-subtitle">{{ t('cottageWatch.editSource') }}</h4>
        <input
          v-model="editing.title"
          class="watch-input"
          type="text"
          :placeholder="t('cottageWatch.titleLabel')"
          maxlength="200"
        />
        <input
          v-model="editing.poster_url"
          class="watch-input"
          type="text"
          :placeholder="t('cottageWatch.posterEditPlaceholder')"
          maxlength="4000"
        />
        <div class="watch-edit-actions">
          <button class="watch-mini-btn primary" type="button" :disabled="!canSaveEdit" @click="onSaveEdit">{{ t('cottageWatch.save') }}</button>
          <button class="watch-mini-btn" type="button" @click="editing = null">{{ t('cottageWatch.cancel') }}</button>
        </div>
      </div>

      <!-- Bookmarks for the currently-loaded source (if any) -->
      <div v-if="current.source_wsid" class="watch-bookmarks">
        <div class="watch-bookmarks-head">
          <h4 class="watch-section-subtitle">{{ t('cottageWatch.bookmarksTitle', { title: current.source_title || t('cottageWatch.currentSource') }) }}</h4>
          <button
            v-if="elapsedEnoughForBookmark"
            class="watch-mini-btn primary"
            type="button"
            @click="onAddBookmark"
          >{{ t('cottageWatch.addBookmark') }}</button>
        </div>
        <p v-if="!bookmarks.length" class="watch-empty-lib">
          {{ t('cottageWatch.emptyBookmarks') }}
        </p>
        <ul v-else class="watch-bookmark-list">
          <li
            v-for="b in sortedBookmarks"
            :key="b.bid"
            class="watch-bookmark-item"
          >
            <button
              class="watch-bookmark-jump"
              type="button"
              :title="t('cottageWatch.jumpTo', { time: formatTime(b.position_ms) })"
              @click="onJumpToBookmark(b)"
            >
              <span class="watch-bookmark-time">{{ formatTime(b.position_ms) }}</span>
              <span class="watch-bookmark-label">{{ b.label || t('cottageWatch.unnamedClip') }}</span>
            </button>
            <button
              class="watch-mini-btn watch-bookmark-del"
              type="button"
              :aria-label="t('cottageWatch.deleteBookmark')"
              @click="onDeleteBookmark(b)"
            >×</button>
          </li>
        </ul>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  addWatchUrlSource,
  deleteWatchSource,
  fetchMe,
  fetchWatchSources,
  fetchWatchState,
  inviteWatchPartner,
  patchWatchSource,
  resolveAssetUrl,
  uploadWatchVideo
} from "../../../lib/api";
import { createWatchSocket } from "../../../lib/cottageWatchWs";

// Align local playback when it drifts more than this from the room's head.
const DRIFT_THRESHOLD_MS = 1500;

const { t } = useI18n();

const videoRef = ref(null);
const myUid = ref("");
const partners = ref([]);
const sources = ref([]);
const errorMsg = ref("");
const toast = ref("");
const uploadProgress = ref(null);
const needsResumeGesture = ref(false);

const newTitle = ref("");
const newUrl = ref("");
const newPoster = ref("");

// Inline edit state for title / poster_url of an existing source.
// Null when the panel is closed; an object while editing.
const editing = ref(null);

// Resume / bookmark bookkeeping (one row per source in the library).
// Indexed by wsid so the per-source chip in the list and the per-source
// bookmark panel in the player stay in sync without extra refetching.
const resumeByWsid = ref({}); // wsid -> { last_position_ms, last_viewed_at, bookmarks }

// How long a paused state must be settled before we surface a "resume" pill
// for the current source. A pure RELOAD race (paused state popped for <1s)
// would otherwise be noisy and confusing.
const RESUME_MIN_GAP_MS = 3000;
const current = ref({
  source_wsid: null,
  source_url: null,
  source_title: null,
  source_kind: null,
  paused: true,
  position_ms: 0,
  rate: 1,
  started_by: null,
  event_seq: 0,
  server_ts_ms: 0
});

let socket = null;
let heartbeatTimer = null;
let driftTimer = null;
let toastTimer = null;
let lastAppliedEventSeq = 0;
let lifecycleGeneration = 0;
let stateRequestGeneration = 0;
// While Date.now() < suppressUntil, native media events are programmatic
// (caused by applying a remote event) and must NOT be re-broadcast.
let suppressUntil = 0;
let hasUserGesture = false;

const startedByLabel = computed(() => {
  const uid = current.value.started_by;
  if (!uid) return "";
  if (uid === myUid.value) return t('cottageWatch.you');
  const p = (partners.value || []).find((x) => x.user_uid === uid);
  return p?.nickname || t('cottageWatch.partner');
});

/** Bookmarks attached to the source currently shown in the player. */
const bookmarks = computed(() => {
  const wsid = current.value.source_wsid;
  if (!wsid) return [];
  const entry = resumeByWsid.value[wsid];
  return entry?.bookmarks || [];
});

const sortedBookmarks = computed(() => {
  // Cloning so the sort doesn't mutate the source-of-truth list we send
  // back to the server when a bookmark is added / removed.
  return [...bookmarks.value].sort((a, b) => a.position_ms - b.position_ms);
});

/** Disable save when the title is blank or nothing actually changed. */
const canSaveEdit = computed(() => {
  const e = editing.value;
  if (!e) return false;
  const title = (e.title || "").trim();
  if (!title) return false;
  if (title !== e._origTitle) return true;
  const poster = (e.poster_url || "").trim();
  if (poster !== (e._origPoster || "")) return true;
  return false;
});

/**
 * Has the user actually played a few seconds? Prevents spamming a bookmark
 * on a brand-new LOAD that the user just opened to peek at the file.
 */
const elapsedEnoughForBookmark = computed(() => {
  const el = videoRef.value;
  if (!el) return false;
  return (el.currentTime || 0) >= 2;
});

/**
 * If the current source was previously watched (we have a last_viewed_at
 * AND a non-zero last_position_ms), show a single inline "继续观看 / 重看"
 * pill on the player header so it's impossible to miss. Returns empty
 * when there's nothing to resume.
 */
const resumePrompt = computed(() => {
  const wsid = current.value.source_wsid;
  if (!wsid) return "";
  const entry = resumeByWsid.value[wsid];
  if (!entry || !entry.last_viewed_at || !entry.last_position_ms) return "";
  // Don't surface it during the very first moments of a freshly loaded
  // source — the local `current.position_ms` will be the resume point
  // itself, which would always pass the test and look broken.
  if (current.value.paused && current.value.position_ms < 1500) return "";
  if (Date.now() - new Date(entry.last_viewed_at).getTime() < RESUME_MIN_GAP_MS) return "";
  return t('cottageWatch.resumePrompt', { time: formatTime(entry.last_position_ms) });
});

function resumeLabelFor(source) {
  const entry = resumeByWsid.value[source.wsid];
  if (!entry || !entry.last_position_ms || !entry.last_viewed_at) return "";
  const last = new Date(entry.last_viewed_at).getTime();
  if (Date.now() - last > 30 * 24 * 60 * 60 * 1000) return ""; // >30d, drop hint
  return t('cottageWatch.lastWatched', { time: formatTime(entry.last_position_ms) });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function suppress(ms = 1200) {
  suppressUntil = Date.now() + ms;
}

function isSuppressed() {
  return Date.now() < suppressUntil;
}

function expectedPositionMs(positionMs, serverTsMs, paused, rate) {
  if (paused) return positionMs;
  const elapsed = Math.max(0, Date.now() - (serverTsMs || Date.now()));
  return positionMs + elapsed * (rate || 1);
}

function alignVideo(targetMs, { force = false } = {}) {
  const el = videoRef.value;
  if (!el) return;
  const localMs = (el.currentTime || 0) * 1000;
  if (force || Math.abs(targetMs - localMs) > DRIFT_THRESHOLD_MS) {
    try {
      el.currentTime = Math.max(0, targetMs) / 1000;
    } catch (_) {
      /* ignore */
    }
  }
}

function showToast(text) {
  toast.value = text;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value = "";
  }, 5000);
}

function formatSize(bytes) {
  if (!bytes) return "";
  const mb = bytes / (1024 * 1024);
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)}GB`;
  return `${mb.toFixed(0)}MB`;
}

/** "1:23:45" / "12:34" / "0:08" — for the resume / bookmark labels. */
function formatTime(ms) {
  if (!ms || Number.isNaN(Number(ms))) return "0:00";
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Stable per-session bookmark id (no external deps). */
function newBookmarkId() {
  return (
    Date.now().toString(36) +
    "-" +
    Math.random().toString(36).slice(2, 10)
  );
}

// ---------------------------------------------------------------------------
// Apply remote events
// ---------------------------------------------------------------------------

function applyEvent(e) {
  // System events carry no event_seq; let them through. Sync events dedupe.
  if (typeof e.event_seq === "number") {
    if (e.event_seq <= lastAppliedEventSeq) return;
    lastAppliedEventSeq = e.event_seq;
  }

  switch (e.type) {
    case "LOAD":
      applyLoad(e);
      break;
    case "PLAY":
      applyPlay(e);
      break;
    case "PAUSE":
      applyPause(e);
      break;
    case "SEEK":
      applySeek(e);
      break;
    case "RATE":
      applyRate(e);
      break;
    case "PRESENCE":
      patchPresence(e.payload?.user_uid, !!e.payload?.online);
      break;
    case "INVITE":
      if (e.payload?.from_uid && e.payload.from_uid !== myUid.value) {
        showToast(t('cottageWatch.inviteToast', { name: e.payload.from_nickname || t('cottageWatch.partner') }));
      }
      break;
    case "ROOM_CLEARED":
      clearCurrent();
      break;
  }
}

function applyLoad(e) {
  const p = e.payload || {};
  current.value = {
    ...current.value,
    source_wsid: p.source_wsid || null,
    source_url: p.source_url || null,
    source_title: p.source_title || null,
    source_kind: p.source_kind || null,
    paused: true,
    position_ms: 0,
    rate: 1,
    started_by: e.origin_uid,
    event_seq: e.event_seq || current.value.event_seq,
    server_ts_ms: e.server_ts_ms
  };
  needsResumeGesture.value = false;
  loadVideoSource(p.source_url, 0);
}

function applyPlay(e) {
  const p = e.payload || {};
  const pos = Number(p.position_ms || 0);
  current.value = {
    ...current.value,
    paused: false,
    position_ms: pos,
    started_by: e.origin_uid,
    server_ts_ms: e.server_ts_ms
  };
  const el = videoRef.value;
  if (!el || !current.value.source_url) return;
  const target = expectedPositionMs(pos, e.server_ts_ms, false, current.value.rate);
  suppress();
  alignVideo(target, { force: true });
  playVideo();
}

function applyPause(e) {
  const p = e.payload || {};
  const pos = Number(p.position_ms || 0);
  current.value = {
    ...current.value,
    paused: true,
    position_ms: pos,
    server_ts_ms: e.server_ts_ms
  };
  const el = videoRef.value;
  if (!el) return;
  suppress();
  try {
    el.pause();
  } catch (_) {
    /* ignore */
  }
  alignVideo(pos, { force: true });
}

function applySeek(e) {
  const p = e.payload || {};
  const pos = Number(p.position_ms || 0);
  current.value = { ...current.value, position_ms: pos, server_ts_ms: e.server_ts_ms };
  const target = expectedPositionMs(pos, e.server_ts_ms, current.value.paused, current.value.rate);
  suppress();
  alignVideo(target, { force: true });
}

function applyRate(e) {
  const rate = Number(e.payload?.rate || 1);
  current.value = { ...current.value, rate };
  const el = videoRef.value;
  if (!el) return;
  suppress();
  try {
    el.playbackRate = rate;
  } catch (_) {
    /* ignore */
  }
}

function patchPresence(uid, online) {
  if (!uid) return;
  partners.value = (partners.value || []).map((p) =>
    p.user_uid === uid ? { ...p, online } : p
  );
}

function clearCurrent() {
  current.value = {
    ...current.value,
    source_wsid: null,
    source_url: null,
    source_title: null,
    source_kind: null,
    paused: true,
    position_ms: 0
  };
  const el = videoRef.value;
  if (el) {
    try {
      el.pause();
      el.removeAttribute("src");
      el.load();
    } catch (_) {
      /* ignore */
    }
  }
}

// ---------------------------------------------------------------------------
// Video element control
// ---------------------------------------------------------------------------

function loadVideoSource(url, positionMs) {
  const el = videoRef.value;
  if (!el || !url) return;
  const resolved = resolveAssetUrl(url);
  suppress(1500);
  if (el.src !== resolved) {
    el.src = resolved;
    try {
      el.load();
    } catch (_) {
      /* ignore */
    }
  }
  alignVideo(positionMs || 0, { force: true });
}

async function playVideo() {
  const el = videoRef.value;
  if (!el) return;
  try {
    await el.play();
    needsResumeGesture.value = false;
  } catch (err) {
    if (!hasUserGesture) {
      needsResumeGesture.value = true;
    } else {
      errorMsg.value = t('cottageWatch.playFailed', { reason: err?.message || t('cottageWatch.unknownError') });
    }
  }
}

function onResumeLocal() {
  hasUserGesture = true;
  needsResumeGesture.value = false;
  if (!current.value.source_url) return;
  const target = expectedPositionMs(
    current.value.position_ms,
    current.value.server_ts_ms,
    current.value.paused,
    current.value.rate
  );
  suppress();
  alignVideo(target, { force: true });
  if (!current.value.paused) playVideo();
}

function sendCommand(type, payload = {}, { reconcile = true } = {}) {
  const sent = socket?.send({ type, payload }) === true;
  if (!sent) {
    errorMsg.value = t('cottageWatch.disconnected');
    if (reconcile) void reloadState();
  }
  return sent;
}

// ---------------------------------------------------------------------------
// Local (user) media events -> broadcast
// ---------------------------------------------------------------------------

function onLocalPlay() {
  hasUserGesture = true;
  if (isSuppressed()) return;
  if (!current.value.source_url) return;
  sendCommand("PLAY", { position_ms: localPositionMs() });
}

function onLocalPause() {
  if (isSuppressed()) return;
  if (!current.value.source_url) return;
  const pos = localPositionMs();
  sendCommand("PAUSE", { position_ms: pos });
  // Flush synchronously on pause so a tab close a moment later doesn't lose
  // the progress. fire-and-forget — failure is fine, the next 5s tick will
  // catch up.
  void flushProgressToServer({ force: true });
}

function onLocalSeeked() {
  if (isSuppressed()) return;
  if (!current.value.source_url) return;
  sendCommand("SEEK", { position_ms: localPositionMs() });
}

function onLocalRateChange() {
  if (isSuppressed()) return;
  const el = videoRef.value;
  if (!el || !current.value.source_url) return;
  sendCommand("RATE", { rate: el.playbackRate || 1, position_ms: localPositionMs() });
}

function onTimeUpdate() {
  // Reserved for a future progress readout; no broadcast here.
}

function onVideoError() {
  if (current.value.source_url) {
    errorMsg.value = t('cottageWatch.videoLoadFailed');
  }
}

// ---------------------------------------------------------------------------
// Resume progress + bookmarks (server-backed)
// ---------------------------------------------------------------------------

let progressFlushTimer = null;
let lastProgressSentAt = 0;
// Re-trying one stuck PATCH is fine; the server is idempotent on
// (wsid, last_position_ms). The bookmarks list is replace-only.
async function flushProgressToServer({ force = false } = {}) {
  const wsid = current.value.source_wsid;
  if (!wsid) return;
  const now = Date.now();
  if (!force && now - lastProgressSentAt < 4000) return;
  lastProgressSentAt = now;
  const posMs = localPositionMs();
  try {
    await patchWatchSource(wsid, { last_position_ms: posMs });
    const entry = resumeByWsid.value[wsid] || { bookmarks: [] };
    resumeByWsid.value = {
      ...resumeByWsid.value,
      [wsid]: {
        ...entry,
        last_position_ms: posMs,
        last_viewed_at: new Date().toISOString(),
      },
    };
  } catch (_) {
    // Network blip — try again on the next tick rather than spamming.
  }
}

function startProgressFlush() {
  if (progressFlushTimer) clearInterval(progressFlushTimer);
  // Every 5s is the sweet spot: cheap enough to keep, granular enough to
  // survive a tab close. The pause / unmount paths also flush synchronously.
  progressFlushTimer = setInterval(() => {
    if (current.value.source_wsid && videoRef.value) {
      void flushProgressToServer();
    }
  }, 5000);
}

function stopProgressFlush() {
  if (progressFlushTimer) clearInterval(progressFlushTimer);
  progressFlushTimer = null;
}

function onResumeFromBookmark() {
  const wsid = current.value.source_wsid;
  if (!wsid) return;
  const entry = resumeByWsid.value[wsid];
  if (!entry || !entry.last_position_ms) return;
  // Server SEEK broadcasts to the partner; locally this is a normal seek.
  sendCommand("SEEK", { position_ms: entry.last_position_ms });
  void flushProgressToServer({ force: true });
}

function onJumpToBookmark(bookmark) {
  if (!current.value.source_wsid) return;
  sendCommand("SEEK", { position_ms: bookmark.position_ms });
  void flushProgressToServer({ force: true });
}

async function onAddBookmark() {
  const wsid = current.value.source_wsid;
  if (!wsid) return;
  const pos = localPositionMs();
  if (pos < 0) return;
  // Default label is the timestamp; the user can rename by tapping later,
  // but for now we keep the API tight (the schema only stores one label).
  const defaultLabel = t('cottageWatch.clipLabel', { time: formatTime(pos) });
  const entry = resumeByWsid.value[wsid] || { bookmarks: [] };
  const nextList = [
    ...(entry.bookmarks || []),
    {
      bid: newBookmarkId(),
      position_ms: pos,
      label: defaultLabel,
      created_at: new Date().toISOString(),
      // created_by_uid is stamped by the server from the authenticated
      // session — never trust the client to self-report authorship.
    },
  ];
  // Optimistic update + sync. Bounded so a runaway loop never blows up the UI.
  if (nextList.length > 200) {
    showToast(t('cottageWatch.bookmarkLimit'));
    return;
  }
  resumeByWsid.value = {
    ...resumeByWsid.value,
    [wsid]: { ...entry, bookmarks: nextList },
  };
  try {
    const updated = await patchWatchSource(wsid, { bookmarks: nextList });
    if (updated?.bookmarks) {
      resumeByWsid.value = {
        ...resumeByWsid.value,
        [wsid]: { ...entry, bookmarks: updated.bookmarks },
      };
    }
  } catch (e) {
    // Roll back to the previous list so the UI matches the server.
    resumeByWsid.value = {
      ...resumeByWsid.value,
      [wsid]: { ...entry, bookmarks: entry.bookmarks || [] },
    };
    errorMsg.value = e?.response?.data?.detail || t('cottageWatch.addBookmarkFailed');
  }
}

async function onDeleteBookmark(bookmark) {
  const wsid = current.value.source_wsid;
  if (!wsid) return;
  const entry = resumeByWsid.value[wsid] || { bookmarks: [] };
  const nextList = (entry.bookmarks || []).filter((b) => b.bid !== bookmark.bid);
  if (nextList.length === (entry.bookmarks || []).length) return;
  resumeByWsid.value = {
    ...resumeByWsid.value,
    [wsid]: { ...entry, bookmarks: nextList },
  };
  try {
    const updated = await patchWatchSource(wsid, { bookmarks: nextList });
    if (updated?.bookmarks) {
      resumeByWsid.value = {
        ...resumeByWsid.value,
        [wsid]: { ...entry, bookmarks: updated.bookmarks },
      };
    }
  } catch (e) {
    resumeByWsid.value = {
      ...resumeByWsid.value,
      [wsid]: { ...entry, bookmarks: entry.bookmarks || [] },
    };
    errorMsg.value = e?.response?.data?.detail || t('cottageWatch.deleteBookmarkFailed');
  }
}

function localPositionMs() {
  const el = videoRef.value;
  return el ? Math.floor((el.currentTime || 0) * 1000) : 0;
}

// ---------------------------------------------------------------------------
// Library actions
// ---------------------------------------------------------------------------

async function onAddUrl() {
  const url = newUrl.value.trim();
  if (!url) return;
  errorMsg.value = "";
  try {
    await addWatchUrlSource({
      title: newTitle.value.trim() || url.split("/").pop() || t('cottageWatch.directVideo'),
      url,
      poster_url: newPoster.value.trim() || null
    });
    newTitle.value = "";
    newUrl.value = "";
    newPoster.value = "";
    await reloadSources();
  } catch (e) {
    errorMsg.value = e?.response?.data?.detail || t('cottageWatch.addUrlFailed');
  }
}

async function onPickFile(event) {
  const file = event.target.files && event.target.files[0];
  event.target.value = "";
  if (!file) return;
  errorMsg.value = "";
  uploadProgress.value = 0;
  try {
    await uploadWatchVideo(file, (pct) => {
      uploadProgress.value = pct;
    });
    await reloadSources();
  } catch (e) {
    errorMsg.value = e?.response?.data?.detail || t('cottageWatch.uploadFailed');
  } finally {
    uploadProgress.value = null;
  }
}

function onLoadSource(s) {
  hasUserGesture = true;
  errorMsg.value = "";
  // Seed the room head with this client's last-known position for the source
  // so the partner who joins later can resume from the right place.
  const entry = resumeByWsid.value[s.wsid];
  const resumePos = entry?.last_position_ms ? Number(entry.last_position_ms) : 0;
  sendCommand("LOAD", {
    source_wsid: s.wsid,
    source_url: s.url,
    source_title: s.title,
    source_kind: s.kind,
    position_ms: resumePos
  });
  // After LOAD, the partner will see us as `paused` at resumePos; locally
  // we honour the same starting position so we agree on the very first frame.
  if (resumePos > 0) {
    suppress(1500);
    alignVideo(resumePos, { force: true });
  }
}

async function onDeleteSource(s) {
  try {
    await deleteWatchSource(s.wsid);
    await reloadSources();
  } catch (_) {
    errorMsg.value = t('cottageWatch.deleteFailed');
  }
}

// ---------------------------------------------------------------------------
// Poster wall helpers
// ---------------------------------------------------------------------------

/** Stable gradient per title so posters without a cover still look distinct. */
function fallbackStyle(title) {
  const palettes = [
    ["#f472b6", "#fb7185"],
    ["#818cf8", "#6366f1"],
    ["#34d399", "#10b981"],
    ["#fbbf24", "#f59e0b"],
    ["#a78bfa", "#8b5cf6"],
    ["#60a5fa", "#3b82f6"]
  ];
  let hash = 0;
  for (let i = 0; i < (title || "").length; i++) {
    hash = (hash * 31 + title.charCodeAt(i)) & 0x7fffffff;
  }
  const [a, b] = palettes[hash % palettes.length];
  return { background: `linear-gradient(135deg, ${a}, ${b})` };
}

function initialOf(title) {
  const t = (title || "").trim();
  if (!t) return "🎬";
  // First code point, works for CJK + latin.
  return String.fromCodePoint(t.codePointAt(0));
}

/** Hide a broken poster image so the fallback shows instead. */
function onPosterError(event, wsid) {
  const img = event?.target;
  if (img) img.style.display = "none";
  // Drop the bad URL from local state so a re-render keeps the fallback.
  sources.value = sources.value.map((s) =>
    s.wsid === wsid ? { ...s, poster_url: null } : s
  );
}

function onEditSource(s) {
  editing.value = {
    wsid: s.wsid,
    title: s.title || "",
    poster_url: s.poster_url || "",
    _origTitle: s.title || "",
    _origPoster: s.poster_url || ""
  };
}

async function onSaveEdit() {
  const e = editing.value;
  if (!e || !canSaveEdit.value) return;
  const payload = {};
  const title = (e.title || "").trim();
  if (title && title !== e._origTitle) payload.title = title;
  const poster = (e.poster_url || "").trim();
  if (poster !== (e._origPoster || "")) payload.poster_url = poster;
  try {
    await patchWatchSource(e.wsid, payload);
    editing.value = null;
    await reloadSources();
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('cottageWatch.saveFailed');
  }
}

async function onInvite() {
  try {
    await inviteWatchPartner();
    showToast(t('cottageWatch.invited'));
  } catch (_) {
    errorMsg.value = t('cottageWatch.inviteFailed');
  }
}

async function reloadSources() {
  try {
    const data = await fetchWatchSources();
    sources.value = data.items || [];
    // Capture the resume + bookmark data so the per-source chips and the
    // bookmark panel can render without an extra round trip.
    const next = { ...resumeByWsid.value };
    for (const item of data.items || []) {
      next[item.wsid] = {
        last_position_ms: item.last_position_ms || 0,
        last_viewed_at: item.last_viewed_at || null,
        bookmarks: Array.isArray(item.bookmarks) ? item.bookmarks : [],
      };
    }
    resumeByWsid.value = next;
  } catch (_) {
    /* ignore */
  }
}

async function reloadState(lifecycle = lifecycleGeneration) {
  const requestGeneration = ++stateRequestGeneration;
  try {
    const data = await fetchWatchState();
    if (
      lifecycle !== lifecycleGeneration ||
      requestGeneration !== stateRequestGeneration
    ) {
      return false;
    }
    const snapshotSeq = Number(data.event_seq ?? data.current?.event_seq ?? 0);
    if (snapshotSeq < lastAppliedEventSeq) {
      return false;
    }
    current.value = { ...current.value, ...data.current };
    partners.value = data.partners || [];
    lastAppliedEventSeq = Math.max(lastAppliedEventSeq, snapshotSeq);
    if (current.value.source_url) {
      const target = expectedPositionMs(
        current.value.position_ms,
        current.value.server_ts_ms,
        current.value.paused,
        current.value.rate
      );
      loadVideoSource(current.value.source_url, target);
      if (!current.value.paused) playVideo();
    }
    return true;
  } catch (_) {
    if (
      lifecycle === lifecycleGeneration &&
      requestGeneration === stateRequestGeneration
    ) {
      errorMsg.value = t('cottageWatch.loadStateFailed');
    }
    return false;
  }
}

// ---------------------------------------------------------------------------
// Drift correction & heartbeat
// ---------------------------------------------------------------------------

function startDriftCorrection() {
  driftTimer = setInterval(() => {
    const el = videoRef.value;
    if (!el || !current.value.source_url || current.value.paused) return;
    if (isSuppressed()) return;
    if (typeof document !== "undefined" && document.hidden) return;
    const target = expectedPositionMs(
      current.value.position_ms,
      current.value.server_ts_ms,
      false,
      current.value.rate
    );
    alignVideo(target);
  }, 4000);
}

function startHeartbeat() {
  sendHeartbeat();
  heartbeatTimer = setInterval(sendHeartbeat, 30000);
}

function sendHeartbeat() {
  socket?.send({ type: "HEARTBEAT", payload: {} });
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

onMounted(async () => {
  const lifecycle = ++lifecycleGeneration;
  try {
    const me = await fetchMe();
    if (lifecycle !== lifecycleGeneration) return;
    myUid.value = me?.uid || "";
  } catch (_) {
    if (lifecycle !== lifecycleGeneration) return;
  }

  socket = createWatchSocket({
    onEvent: (e) => {
      if (lifecycle === lifecycleGeneration) applyEvent(e);
    },
    onOpen: () => {
      if (lifecycle !== lifecycleGeneration) return;
      if (errorMsg.value === t('cottageWatch.disconnected')) errorMsg.value = "";
      void reloadState(lifecycle);
    },
    onClose: () => {}
  });

  await Promise.all([reloadSources(), reloadState(lifecycle)]);
  if (lifecycle !== lifecycleGeneration) return;
  startHeartbeat();
  startDriftCorrection();
  startProgressFlush();
});

onBeforeUnmount(() => {
  lifecycleGeneration += 1;
  stateRequestGeneration += 1;
  if (heartbeatTimer) clearInterval(heartbeatTimer);
  if (driftTimer) clearInterval(driftTimer);
  if (toastTimer) clearTimeout(toastTimer);
  // Final flush of the resume position. Best-effort; a network failure
  // here just means the partner picks up from the last 5s tick.
  void flushProgressToServer({ force: true });
  stopProgressFlush();
  if (socket) {
    try {
      socket.close();
    } catch (_) {
      /* ignore */
    }
    socket = null;
  }
});
</script>

<style scoped>
.watch {
  display: grid;
  gap: 1rem;
}

.watch-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.watch-title {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex-wrap: wrap;
}

.watch-title h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #2f3754;
}

.watch-presence {
  display: inline-flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.presence-dot {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
  color: var(--text-soft);
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
}

.presence-dot::before {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e1;
}

.presence-dot.online {
  color: #15803d;
  background: rgba(34, 197, 94, 0.14);
}

.presence-dot.online::before {
  background: #22c55e;
}

.watch-actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.watch-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0.45rem 0.95rem;
  border-radius: 999px;
  border: none;
  background: linear-gradient(135deg, #f472b6, #fb7185);
  color: #fff;
  font-size: 0.85rem;
  cursor: pointer;
}

.watch-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.watch-back {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  font-size: 0.82rem;
  text-decoration: none;
}

.watch-toast {
  margin: 0;
  padding: 0.55rem 0.85rem;
  border-radius: 10px;
  background: rgba(236, 72, 153, 0.12);
  color: #be185d;
  font-size: 0.85rem;
  text-align: center;
}

.watch-error {
  margin: 0;
  padding: 0.55rem 0.85rem;
  border-radius: 10px;
  background: rgba(252, 165, 165, 0.18);
  color: #b91c1c;
  font-size: 0.85rem;
  text-align: center;
}

.watch-player-card {
  padding: 1rem 1.1rem;
  display: grid;
  gap: 0.7rem;
}

.watch-now {
  font-size: 0.9rem;
  color: #2f3754;
}

.watch-now-by {
  color: var(--text-soft);
  font-size: 0.82rem;
}

.watch-stage {
  position: relative;
  background: #000;
  border-radius: 14px;
  overflow: hidden;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.watch-video {
  width: 100%;
  max-height: 70vh;
  display: block;
  background: #000;
}

.watch-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 1.5rem;
  color: rgba(255, 255, 255, 0.78);
  font-size: 0.9rem;
  line-height: 1.6;
}

.watch-resume {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  padding: 0.5rem 1.1rem;
  border-radius: 999px;
  border: none;
  background: rgba(236, 72, 153, 0.92);
  color: #fff;
  font-size: 0.85rem;
  cursor: pointer;
}

.watch-resume-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  margin-left: 0.5rem;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  border: 1px solid rgba(236, 72, 153, 0.4);
  background: rgba(236, 72, 153, 0.1);
  color: #be185d;
  font-size: 0.76rem;
  cursor: pointer;
  transition: background 0.12s ease;
}

.watch-resume-pill:hover {
  background: rgba(236, 72, 153, 0.2);
}

.watch-source-progress {
  font-size: 0.72rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.14);
  color: #15803d;
}

.watch-section-subtitle {
  margin: 0;
  font-size: 0.92rem;
  color: #2f3754;
}

.watch-bookmarks {
  display: grid;
  gap: 0.55rem;
  border-top: 1px dashed rgba(148, 163, 184, 0.45);
  padding-top: 0.75rem;
  margin-top: 0.35rem;
}

.watch-bookmarks-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.watch-bookmark-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.4rem;
  max-height: 220px;
  overflow-y: auto;
}

.watch-bookmark-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.6rem;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.08);
}

.watch-bookmark-jump {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  min-width: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  padding: 0;
}

.watch-bookmark-time {
  font-size: 0.78rem;
  font-weight: 700;
  color: #4f46e5;
  font-variant-numeric: tabular-nums;
}

.watch-bookmark-label {
  font-size: 0.84rem;
  color: #2f3754;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.watch-bookmark-del {
  min-width: 32px;
  padding: 0.2rem 0.5rem;
  font-size: 1rem;
  line-height: 1;
}

.watch-hint {
  margin: 0;
  font-size: 0.78rem;
  color: var(--text-soft);
  line-height: 1.6;
}

.watch-library {
  padding: 1rem 1.1rem;
  display: grid;
  gap: 0.85rem;
}

.watch-section-title {
  margin: 0;
  font-size: 1rem;
  color: #2f3754;
}

.watch-add {
  display: grid;
  gap: 0.5rem;
}

.watch-input {
  width: 100%;
  min-height: 38px;
  padding: 0.45rem 0.7rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.9);
  font-size: 0.85rem;
  box-sizing: border-box;
}

.watch-upload {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  flex-wrap: wrap;
}

.watch-upload-btn {
  cursor: pointer;
}

.watch-progress {
  font-size: 0.82rem;
  color: #be185d;
}

.watch-upload-hint {
  font-size: 0.76rem;
  color: var(--text-soft);
}

.watch-poster-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 0.9rem;
}

.watch-poster-card {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.45rem;
  border-radius: 14px;
  background: rgba(148, 163, 184, 0.1);
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}
.watch-poster-card.active {
  box-shadow: 0 0 0 2px rgba(236, 72, 153, 0.5);
}
.watch-poster-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.12);
}

.watch-poster-face {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 2 / 3;
  border: none;
  padding: 0;
  border-radius: 10px;
  overflow: hidden;
  background: #0f172a;
  cursor: pointer;
}
.watch-poster-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.watch-poster-fallback {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.4rem;
  color: rgba(255, 255, 255, 0.92);
  font-weight: 700;
}
.watch-poster-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.28);
  opacity: 0;
  transition: opacity 0.15s ease;
}
.watch-poster-face:hover .watch-poster-overlay,
.watch-poster-face:focus-visible .watch-poster-overlay {
  opacity: 1;
}
.watch-poster-play {
  font-size: 1.6rem;
  color: #fff;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
}
.watch-poster-tag {
  position: absolute;
  top: 6px;
  left: 6px;
  font-size: 0.66rem;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.85);
  color: #fff;
}
.watch-poster-progress {
  position: absolute;
  bottom: 6px;
  right: 6px;
  font-size: 0.66rem;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.88);
  color: #fff;
}

.watch-poster-meta {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}
.watch-poster-name {
  margin: 0;
  font-size: 0.84rem;
  color: #2f3754;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.watch-poster-sub {
  margin: 0;
  font-size: 0.72rem;
  color: var(--text-soft);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.watch-poster-ops {
  display: flex;
  gap: 0.35rem;
}
.watch-poster-ops .watch-mini-btn {
  flex: 1;
}

.watch-edit-panel {
  display: grid;
  gap: 0.5rem;
  padding: 0.85rem 0.95rem;
  border-radius: 12px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
}
.watch-edit-actions {
  display: flex;
  gap: 0.4rem;
  justify-content: flex-end;
}

.watch-mini-btn {
  min-height: 32px;
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.85);
  color: #3d4665;
  font-size: 0.78rem;
  cursor: pointer;
}

.watch-mini-btn.primary {
  border: none;
  background: linear-gradient(135deg, #818cf8, #6366f1);
  color: #fff;
}

.watch-empty-lib {
  margin: 0;
  font-size: 0.84rem;
  color: var(--text-soft);
}

@media (max-width: 768px) {
  .watch-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
