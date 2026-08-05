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
  <div class="content-section canvas-view">
    <article class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t("cottageGames.canvas.title") }}</h2>
        <span class="presence" :class="{ on: partnerOnline }">
          {{ partnerOnline ? t("cottageGames.common.partnerOnline") : t("cottageGames.common.partnerOffline") }}
        </span>
      </div>
      <p class="hint">{{ t("cottageGames.canvas.hint") }}</p>

      <div class="toolbar">
        <label class="tool">
          {{ t("cottageGames.canvas.color") }}
          <input v-model="color" type="color" :disabled="eraser" />
        </label>
        <div class="swatches">
          <button
            v-for="c in palette"
            :key="c"
            class="swatch"
            :style="{ background: c }"
            :class="{ active: color === c && !eraser }"
            @click="pickColor(c)"
          ></button>
        </div>
        <label class="tool">
          {{ t("cottageGames.canvas.thickness") }}
          <input v-model.number="size" type="range" min="1" max="40" />
          <span class="size-val">{{ size }}</span>
        </label>
        <button class="tool-btn" :class="{ active: eraser }" @click="eraser = !eraser">
          {{ eraser ? t("cottageGames.canvas.eraserOn") : t("cottageGames.canvas.eraserOff") }}
        </button>
        <button class="tool-btn" @click="onUndo">{{ t("cottageGames.canvas.undo") }}</button>
        <button class="tool-btn" @click="onClear">{{ t("cottageGames.canvas.clear") }}</button>
        <button class="tool-btn" @click="downloadPng">{{ t("cottageGames.canvas.download") }}</button>
        <button class="tool-btn primary" :disabled="saving" @click="saveToTimeline">
          {{ saving ? t("cottageGames.canvas.saving") : t("cottageGames.canvas.saveToTimeline") }}
        </button>
        <button class="tool-btn" :disabled="savingToGallery" @click="saveToArtwork">
          {{ savingToGallery ? t("cottageGames.canvas.saving") : t("cottageGames.canvas.saveToArtwork") }}
        </button>
        <router-link to="/cottage/games/canvas/gallery" class="tool-btn tool-link">
          {{ t("cottageGames.canvas.galleryLink") }}
        </router-link>
      </div>

      <SharedCanvas
        ref="canvasRef"
        :drawable="true"
        :color="color"
        :size="size"
        :eraser="eraser"
        @stroke="onLocalStroke"
        @clear="onLocalClear"
        @cursor="onLocalCursor"
        @cursorleave="onLocalCursorLeave"
      />
    </article>
  </div>
</template>

<script setup>
import { inject, onBeforeUnmount, onMounted, ref } from "vue";
import SharedCanvas from "../../../../components/SharedCanvas.vue";
import { createCottageSocket } from "../../../../lib/cottageSocket";
import { createMoment, createCanvasArtwork, fetchMe, uploadTimelineImage } from "../../../../lib/api";
import { parseError } from "../../../../utils/helpers";
import { t } from "../../../../locales";

const showMessage = inject("showMessage", () => {});

const palette = ["#1e293b", "#ef4444", "#f59e0b", "#10b981", "#3b82f6", "#a855f7", "#ec4899", "#ffffff"];
const color = ref("#1e293b");
const size = ref(4);
const eraser = ref(false);
const saving = ref(false);
const savingToGallery = ref(false);
const partnerOnline = ref(false);

const canvasRef = ref(null);
let socket = null;
let myUid = "";

// Buffer outgoing segments and flush on animation frame to cut message count.
let outBuffer = [];
let rafId = null;

function pickColor(c) {
  color.value = c;
  eraser.value = false;
}

function flush() {
  rafId = null;
  if (!outBuffer.length || !socket) return;
  socket.send({ type: "STROKE", payload: { segs: outBuffer } });
  outBuffer = [];
}

function onLocalStroke(seg) {
  outBuffer.push(seg);
  if (!rafId) rafId = requestAnimationFrame(flush);
}

function onLocalClear() {
  socket && socket.send({ type: "CLEAR", payload: {} });
}

function onClear() {
  canvasRef.value?.clear(); // emits clear → broadcast
}

function handleEvent(msg) {
  if (msg.type === "STROKE") {
    const segs = msg.payload?.segs || (msg.payload ? [msg.payload] : []);
    segs.forEach((s) => canvasRef.value?.applyStroke(s));
  } else if (msg.type === "CLEAR") {
    canvasRef.value?.clearLocal();
  } else if (msg.type === "UNDO") {
    canvasRef.value?.applyUndo(msg.payload?.sid);
  } else if (msg.type === "CURSOR") {
    const p = msg.payload || {};
    if (p.leave || p.x < 0) canvasRef.value?.hideRemoteCursor();
    else canvasRef.value?.setRemoteCursor(p);
  } else if (msg.type === "SYNC_REQUEST") {
    replyToSyncRequest();
  } else if (msg.type === "SYNC") {
    canvasRef.value?.loadSync(msg.payload?.strokes || []);
  } else if (msg.type === "PRESENCE_SNAPSHOT") {
    const online = msg.payload?.online || [];
    partnerOnline.value = online.some((u) => u !== myUid);
  } else if (msg.type === "PRESENCE") {
    if (msg.payload?.uid && msg.payload.uid !== myUid) {
      partnerOnline.value = !!msg.payload.online;
    }
  }
}

function onUndo() {
  const sid = canvasRef.value?.undoMine();
  if (sid && socket) socket.send({ type: "UNDO", payload: { sid } });
}

let lastCursorSent = 0;
function onLocalCursor(p) {
  const now = Date.now();
  if (now - lastCursorSent < 40) return; // throttle cursor frames
  lastCursorSent = now;
  socket && socket.send({ type: "CURSOR", payload: { x: p.x, y: p.y } });
}

function onLocalCursorLeave() {
  socket && socket.send({ type: "CURSOR", payload: { leave: true, x: -1, y: -1 } });
}

function replyToSyncRequest() {
  const strokes = canvasRef.value?.getSyncPayload() || [];
  if (strokes.length && socket) socket.send({ type: "SYNC", payload: { strokes } });
}

function dataUrlToFile(dataUrl, filename) {
  const [head, body] = dataUrl.split(",");
  const mime = /:(.*?);/.exec(head)[1];
  const bin = atob(body);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) arr[i] = bin.charCodeAt(i);
  return new File([arr], filename, { type: mime });
}

function downloadPng() {
  const url = canvasRef.value?.toDataURL();
  if (!url) return;
  const a = document.createElement("a");
  a.href = url;
  a.download = `画板-${Date.now()}.png`;
  a.click();
}

async function saveToTimeline() {
  const url = canvasRef.value?.toDataURL();
  if (!url) return;
  saving.value = true;
  try {
    const file = dataUrlToFile(url, `canvas-${Date.now()}.png`);
    const up = await uploadTimelineImage(file);
    await createMoment({ content: t("cottageGames.canvas.timelineContent"), media_urls: [up.url] });
    showMessage(t("cottageGames.canvas.savedToTimeline"));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    saving.value = false;
  }
}

async function saveToArtwork() {
  const url = canvasRef.value?.toDataURL();
  const strokes = canvasRef.value?.getStrokesJson?.();
  if (!url || !strokes) return;
  savingToGallery.value = true;
  try {
    const created = await createCanvasArtwork({
      title: "",
      strokes_json: strokes,
      thumb_data_url: url,
      width: 960,
      height: 600,
    });
    showMessage(t("cottageGames.canvas.savedToArtwork", { n: created.collaborators.length }));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    savingToGallery.value = false;
  }
}

onMounted(async () => {
  try {
    const me = await fetchMe();
    myUid = me.uid;
  } catch (_) {
    /* ignore */
  }
  socket = createCottageSocket({
    path: "/v1/cottage/canvas/ws",
    onEvent: handleEvent,
    // Ask the partner for the current board on (re)connect so a late joiner or
    // a refresh doesn't start from a blank canvas.
    onOpen: () => socket && socket.send({ type: "SYNC_REQUEST", payload: {} })
  });
});

onBeforeUnmount(() => {
  if (rafId) cancelAnimationFrame(rafId);
  if (socket) socket.close();
});
</script>

<style scoped>
.canvas-view { display: grid; gap: 1rem; }
.presence {
  font-size: 0.75rem;
  padding: 0.15rem 0.6rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.25);
  color: #64748b;
}
.presence.on { background: rgba(52, 211, 153, 0.2); color: #16a34a; }
.hint { margin: 0 0 0.75rem; color: var(--text-soft); font-size: 0.85rem; }
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem 0.9rem;
  margin-bottom: 0.9rem;
}
.tool {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: #475569;
}
.swatches { display: flex; gap: 0.25rem; }
.swatch {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid rgba(148, 163, 184, 0.4);
  cursor: pointer;
  padding: 0;
}
.swatch.active { border-color: #0f172a; transform: scale(1.12); }
.size-val { width: 1.6rem; text-align: center; }
.tool-btn {
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: #fff;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-size: 0.8rem;
  cursor: pointer;
}
.tool-btn.active { background: #fde68a; border-color: #f59e0b; }
.tool-btn.primary { background: #ec4899; color: #fff; border-color: transparent; }
.tool-btn.tool-link {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
  color: #475569;
  background: #f1f5f9;
}
</style>
