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
  <div class="shared-canvas-wrap">
    <canvas
      ref="canvasEl"
      class="shared-canvas"
      :class="{ 'is-readonly': !drawable }"
      :width="WIDTH"
      :height="HEIGHT"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerLeave"
      @pointercancel="onPointerUp"
    ></canvas>
    <!-- Partner's live pointer ("对方正在画" ghost cursor) -->
    <div
      v-if="remoteCursor.visible"
      class="ghost-cursor"
      :style="{ left: remoteCursor.x * 100 + '%', top: remoteCursor.y * 100 + '%' }"
    ></div>
    <div v-if="!drawable" class="canvas-hint">{{ readonlyHint || t("sharedCanvas.readonlyHint") }}</div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const WIDTH = 960;
const HEIGHT = 600;

const props = defineProps({
  drawable: { type: Boolean, default: true },
  color: { type: String, default: "#1e293b" },
  size: { type: Number, default: 4 },
  eraser: { type: Boolean, default: false },
  readonlyHint: { type: String, default: "" }
});
const emit = defineEmits(["stroke", "clear", "cursor", "cursorleave"]);

const canvasEl = ref(null);
const remoteCursor = reactive({ x: 0, y: 0, visible: false });

let ctx = null;
let drawing = false;
let last = null; // { x, y } normalized 0..1
let currentSid = null;

// Ordered stroke history so we can redraw (for undo) and ship a full snapshot
// (for late-joiner SYNC). Each stroke groups the segments sharing one sid.
let strokes = []; // [{ sid, mine, segs: [seg] }]
const strokeIndex = new Map(); // sid -> stroke object

function newSid() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function getCtx() {
  if (!ctx && canvasEl.value) {
    ctx = canvasEl.value.getContext("2d");
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }
  return ctx;
}

function pointerToNorm(ev) {
  const rect = canvasEl.value.getBoundingClientRect();
  const x = (ev.clientX - rect.left) / rect.width;
  const y = (ev.clientY - rect.top) / rect.height;
  return { x: Math.min(1, Math.max(0, x)), y: Math.min(1, Math.max(0, y)) };
}

function drawSegment(seg) {
  const c = getCtx();
  if (!c) return;
  c.save();
  if (seg.eraser) {
    c.globalCompositeOperation = "destination-out";
    c.strokeStyle = "rgba(0,0,0,1)";
  } else {
    c.globalCompositeOperation = "source-over";
    c.strokeStyle = seg.color || "#1e293b";
  }
  c.lineWidth = (seg.size || 4) * (WIDTH / 960);
  c.beginPath();
  c.moveTo(seg.x0 * WIDTH, seg.y0 * HEIGHT);
  c.lineTo(seg.x1 * WIDTH, seg.y1 * HEIGHT);
  c.stroke();
  c.restore();
}

function recordSeg(seg, mine) {
  if (!seg.sid) return;
  let stroke = strokeIndex.get(seg.sid);
  if (!stroke) {
    stroke = { sid: seg.sid, mine, segs: [] };
    strokeIndex.set(seg.sid, stroke);
    strokes.push(stroke);
  }
  stroke.segs.push(seg);
}

function redrawAll() {
  const c = getCtx();
  if (c) c.clearRect(0, 0, WIDTH, HEIGHT);
  for (const stroke of strokes) {
    for (const seg of stroke.segs) drawSegment(seg);
  }
}

function onPointerDown(ev) {
  if (!props.drawable) return;
  drawing = true;
  last = pointerToNorm(ev);
  currentSid = newSid();
  const seg = {
    sid: currentSid,
    x0: last.x, y0: last.y, x1: last.x, y1: last.y,
    color: props.color, size: props.size, eraser: props.eraser
  };
  drawSegment(seg);
  recordSeg(seg, true);
  emit("stroke", seg);
  try {
    canvasEl.value.setPointerCapture(ev.pointerId);
  } catch (_) {
    /* ignore */
  }
}

function onPointerMove(ev) {
  const cur = pointerToNorm(ev);
  // Always advertise the local pointer position so the partner can see it.
  emit("cursor", cur);
  if (!props.drawable || !drawing || !last) return;
  const seg = {
    sid: currentSid,
    x0: last.x, y0: last.y, x1: cur.x, y1: cur.y,
    color: props.color, size: props.size, eraser: props.eraser
  };
  drawSegment(seg);
  recordSeg(seg, true);
  emit("stroke", seg);
  last = cur;
}

function onPointerUp() {
  drawing = false;
  last = null;
  currentSid = null;
}

function onPointerLeave() {
  onPointerUp();
  emit("cursorleave");
}

// ── methods exposed to the parent view ─────────────────────────────────────

function applyStroke(seg) {
  if (seg && typeof seg.x0 === "number") {
    drawSegment(seg);
    recordSeg(seg, false);
  }
}

function undoMine() {
  for (let i = strokes.length - 1; i >= 0; i -= 1) {
    if (strokes[i].mine) {
      const [removed] = strokes.splice(i, 1);
      strokeIndex.delete(removed.sid);
      redrawAll();
      return removed.sid;
    }
  }
  return null;
}

function applyUndo(sid) {
  if (!sid || !strokeIndex.has(sid)) return;
  strokeIndex.delete(sid);
  strokes = strokes.filter((s) => s.sid !== sid);
  redrawAll();
}

function clearLocal() {
  strokes = [];
  strokeIndex.clear();
  const c = getCtx();
  if (c) c.clearRect(0, 0, WIDTH, HEIGHT);
}

function clear(emitEvent = true) {
  clearLocal();
  if (emitEvent) emit("clear");
}

/** Snapshot of all strokes for a late joiner's SYNC. */
function getSyncPayload() {
  return strokes.map((s) => ({ sid: s.sid, segs: s.segs }));
}

/**
 * Serialised snapshot of the current board — what the gallery stores as
 * ``strokes_json`` so the artwork can be replayed later. Encodes the
 * 960x600 frame the same way the realtime WS path does, just with
 * normalised floats instead of 0..1 percentages.
 */
function getStrokesJson() {
  return JSON.stringify({
    width: WIDTH,
    height: HEIGHT,
    strokes: strokes.map((s) => ({ sid: s.sid, segs: s.segs })),
  });
}

/** Replace the board with a peer's snapshot (received via SYNC). */
function loadSync(list) {
  strokes = [];
  strokeIndex.clear();
  if (Array.isArray(list)) {
    for (const s of list) {
      if (!s || !s.sid || !Array.isArray(s.segs)) continue;
      const stroke = { sid: s.sid, mine: false, segs: s.segs };
      strokeIndex.set(s.sid, stroke);
      strokes.push(stroke);
    }
  }
  redrawAll();
}

function setRemoteCursor(point) {
  if (!point || typeof point.x !== "number") return;
  remoteCursor.x = Math.min(1, Math.max(0, point.x));
  remoteCursor.y = Math.min(1, Math.max(0, point.y));
  remoteCursor.visible = true;
}

function hideRemoteCursor() {
  remoteCursor.visible = false;
}

function toDataURL() {
  const tmp = document.createElement("canvas");
  tmp.width = WIDTH;
  tmp.height = HEIGHT;
  const tctx = tmp.getContext("2d");
  tctx.fillStyle = "#ffffff";
  tctx.fillRect(0, 0, WIDTH, HEIGHT);
  tctx.drawImage(canvasEl.value, 0, 0);
  return tmp.toDataURL("image/png");
}

onMounted(() => {
  getCtx();
});

defineExpose({
  applyStroke,
  undoMine,
  applyUndo,
  clear,
  clearLocal,
  getSyncPayload,
  getStrokesJson,
  loadSync,
  setRemoteCursor,
  hideRemoteCursor,
  toDataURL
});
</script>

<style scoped>
.shared-canvas-wrap {
  position: relative;
  width: 100%;
}
.shared-canvas {
  width: 100%;
  aspect-ratio: 960 / 600;
  height: auto;
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  touch-action: none;
  cursor: crosshair;
  display: block;
}
.shared-canvas.is-readonly {
  cursor: not-allowed;
}
.ghost-cursor {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid #ec4899;
  background: rgba(236, 72, 153, 0.25);
  transform: translate(-50%, -50%);
  pointer-events: none;
  transition: left 0.05s linear, top 0.05s linear;
  z-index: 2;
}
.canvas-hint {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(15, 23, 42, 0.65);
  color: #fff;
  font-size: 0.78rem;
  padding: 0.2rem 0.7rem;
  border-radius: 999px;
  pointer-events: none;
}
</style>
