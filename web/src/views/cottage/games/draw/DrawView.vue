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
  <div class="content-section draw-view">
    <article class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t("cottageGames.draw.title") }}</h2>
        <span class="presence" :class="{ on: partnerOnline }">
          {{ partnerOnline ? t("cottageGames.common.partnerOnline") : t("cottageGames.common.partnerOffline") }}
        </span>
      </div>

      <!-- Scoreboard -->
      <div v-if="state.phase && state.phase !== 'waiting'" class="scoreboard">
        <div class="score-cell" :class="{ me: amDrawer }">
          <span class="role">{{ amDrawer ? t("cottageGames.draw.youDraw") : t("cottageGames.draw.youGuess") }}</span>
          <span class="pts">{{ myScore }}</span>
        </div>
        <div class="round-info">
          <div class="round-no">{{ t("cottageGames.draw.roundInfo", { round: state.round, total: state.total_rounds }) }}</div>
          <div v-if="state.phase === 'drawing'" class="timer">⏱ {{ remaining }}s</div>
        </div>
        <div class="score-cell">
          <span class="role">{{ t("cottageGames.draw.partnerLabel") }}</span>
          <span class="pts">{{ partnerScore }}</span>
        </div>
      </div>

      <!-- Word line -->
      <div v-if="state.phase === 'drawing'" class="word-line">
        <template v-if="amDrawer">
          {{ t("cottageGames.draw.youDrawWord") }}<strong class="word">{{ myWord || "…" }}</strong>
        </template>
        <template v-else>
          {{ t("cottageGames.draw.guessHint", { len: state.word_len }) }}<span class="mask">{{ state.word_mask }}</span>
        </template>
      </div>
      <div v-else-if="state.phase === 'round_end'" class="word-line reveal">
        {{ t("cottageGames.draw.answerIs") }} <strong class="word">{{ state.revealed_word }}</strong>
        <span v-if="state.round_winner_uid"> · {{ state.round_winner_uid === myUid ? t("cottageGames.draw.you") : t("cottageGames.draw.partnerLabel") }}{{ t("cottageGames.draw.youGuessedRight") }}</span>
        <span v-else> · {{ t("cottageGames.draw.nobodyGuessed") }}</span>
      </div>

      <SharedCanvas
        ref="canvasRef"
        :drawable="amDrawer && state.phase === 'drawing'"
        :color="color"
        :size="size"
        :eraser="eraser"
        :readonly-hint="state.phase === 'drawing' ? t('cottageGames.draw.readonlyHint') : ''"
        @stroke="onLocalStroke"
      />

      <!-- Drawer tools -->
      <div v-if="amDrawer && state.phase === 'drawing'" class="toolbar">
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
          {{ t("cottageGames.draw.thickness") }}
          <input v-model.number="size" type="range" min="1" max="40" />
        </label>
        <button class="tool-btn" :class="{ active: eraser }" @click="eraser = !eraser">🧽</button>
        <button class="tool-btn" @click="undoStroke">{{ t("cottageGames.draw.undo") }}</button>
        <button class="tool-btn" @click="clearBoard">{{ t("cottageGames.draw.clear") }}</button>
      </div>

      <!-- Guesser input -->
      <form v-if="!amDrawer && state.phase === 'drawing'" class="guess-form" @submit.prevent="sendGuess">
        <input v-model="guessText" class="input" :placeholder="t('cottageGames.draw.guessPlaceholder')" maxlength="50" />
        <button class="btn-primary" :disabled="!guessText.trim()">{{ t("cottageGames.draw.guessBtn") }}</button>
      </form>

      <!-- Controls -->
      <div class="controls">
        <button v-if="!state.phase || state.phase === 'waiting' || state.phase === 'finished'" class="btn-primary" @click="newGame">
          {{ state.phase === 'finished' ? t("cottageGames.draw.rematch") : t("cottageGames.draw.startGame") }}
        </button>
        <button v-if="state.phase === 'round_end'" class="btn-primary" @click="nextRound">{{ t("cottageGames.draw.nextRound") }}</button>
        <button v-if="state.phase === 'drawing' || state.phase === 'round_end'" class="ghost-btn" @click="endGame">{{ t("cottageGames.draw.endGame") }}</button>
        <button class="ghost-btn" @click="invite">{{ t("cottageGames.draw.invitePartner") }}</button>
      </div>

      <!-- Finished -->
      <div v-if="state.phase === 'finished'" class="finished">
        <h3>
          {{ state.winner_uid == null ? t("cottageGames.draw.drawResult") : (state.winner_uid === myUid ? t("cottageGames.draw.youWinResult") : t("cottageGames.draw.partnerWinResult")) }}
        </h3>
        <p>{{ t("cottageGames.draw.finalScore") }} {{ myScore }} : {{ partnerScore }}</p>
      </div>

      <!-- Guess feed -->
      <ul v-if="guesses.length" class="guess-feed">
        <li v-for="(g, i) in guesses" :key="i" :class="{ correct: g.correct }">
          <span class="who">{{ g.from_uid === myUid ? t("cottageGames.draw.you") : t("cottageGames.draw.partnerLabel") }}</span>
          <span class="txt">{{ g.correct ? t("cottageGames.draw.guessedCorrect") : g.text }}</span>
        </li>
      </ul>
    </article>
  </div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import SharedCanvas from "../../../../components/SharedCanvas.vue";
import { createCottageSocket } from "../../../../lib/cottageSocket";
import { fetchDrawState, fetchMe, inviteDrawPartner } from "../../../../lib/api";
import { parseError } from "../../../../utils/helpers";
import { t } from "../../../../locales";

const showMessage = inject("showMessage", () => {});

const palette = ["#1e293b", "#ef4444", "#f59e0b", "#10b981", "#3b82f6", "#a855f7", "#ec4899", "#ffffff"];
const color = ref("#1e293b");
const size = ref(5);
const eraser = ref(false);
const guessText = ref("");
const partnerOnline = ref(false);
const remaining = ref(0);
const myWord = ref("");
const guesses = ref([]);

const state = reactive({});
const canvasRef = ref(null);
let socket = null;
let myUid = "";
let lastRound = 0;
let timeoutSent = false;
let timer = null;

let outBuffer = [];
let rafId = null;

const myUidRef = ref("");
const amDrawer = computed(() => state.phase === "drawing" && state.drawer_uid === myUidRef.value);
const myScore = computed(() => (state.scores ? state.scores[myUidRef.value] || 0 : 0));
const partnerScore = computed(() => {
  if (!state.scores) return 0;
  const other = Object.keys(state.scores).find((u) => u !== myUidRef.value);
  return other ? state.scores[other] : 0;
});

function pickColor(c) {
  color.value = c;
  eraser.value = false;
}

function applyState(snap) {
  Object.assign(state, snap);
  // New round (or fresh game) → wipe the local canvas + per-round UI. The
  // drawer's secret word arrives separately via the YOUR_WORD frame.
  if (snap.round !== lastRound || snap.phase === "waiting") {
    canvasRef.value?.clearLocal();
    guesses.value = [];
    myWord.value = "";
    lastRound = snap.round;
    timeoutSent = false;
  }
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

function clearBoard() {
  canvasRef.value?.clearLocal();
  socket && socket.send({ type: "CLEAR", payload: {} });
}

function undoStroke() {
  const sid = canvasRef.value?.undoMine();
  if (sid && socket) socket.send({ type: "UNDO", payload: { sid } });
}

function replyToSyncRequest() {
  // Only the active drawer holds the authoritative in-progress drawing, so only
  // they answer a late joiner's request for the current board.
  if (!amDrawer.value || state.phase !== "drawing") return;
  const strokes = canvasRef.value?.getSyncPayload() || [];
  if (strokes.length && socket) socket.send({ type: "SYNC", payload: { strokes } });
}

function handleEvent(msg) {
  switch (msg.type) {
    case "STATE":
      applyState(msg.payload || {});
      break;
    case "YOUR_WORD":
      myWord.value = msg.payload?.word || "";
      break;
    case "STROKE": {
      const segs = msg.payload?.segs || (msg.payload ? [msg.payload] : []);
      segs.forEach((s) => canvasRef.value?.applyStroke(s));
      break;
    }
    case "CLEAR":
      canvasRef.value?.clearLocal();
      break;
    case "SYNC_REQUEST":
      replyToSyncRequest();
      break;
    case "SYNC":
      canvasRef.value?.loadSync(msg.payload?.strokes || []);
      break;
    case "UNDO":
      canvasRef.value?.applyUndo(msg.payload?.sid);
      break;
    case "GUESS":
      guesses.value.push(msg.payload || {});
      if (guesses.value.length > 30) guesses.value.shift();
      break;
    case "ROUND_END":
      applyState(msg.payload || {});
      break;
    case "GAME_OVER":
      applyState(msg.payload || {});
      break;
    case "PRESENCE_SNAPSHOT":
      partnerOnline.value = (msg.payload?.online || []).some((u) => u !== myUidRef.value);
      break;
    case "PRESENCE":
      if (msg.payload?.uid && msg.payload.uid !== myUidRef.value) partnerOnline.value = !!msg.payload.online;
      break;
    case "ERROR":
      showMessage(msg.payload?.message || t("cottageGames.common.operationFailed"));
      break;
    default:
      break;
  }
}

function newGame() {
  socket && socket.send({ type: "NEW_GAME", payload: {} });
}
function nextRound() {
  socket && socket.send({ type: "NEXT_ROUND", payload: {} });
}
function endGame() {
  socket && socket.send({ type: "END_GAME", payload: {} });
}
function sendGuess() {
  const text = guessText.value.trim();
  if (!text) return;
  socket && socket.send({ type: "GUESS", payload: { text } });
  guessText.value = "";
}
async function invite() {
  try {
    await inviteDrawPartner();
    showMessage(t("cottageGames.draw.inviteToast"));
  } catch (error) {
    showMessage(parseError(error));
  }
}

function tick() {
  if (state.phase === "drawing" && state.round_deadline_ms) {
    const rem = Math.max(0, Math.ceil((state.round_deadline_ms - Date.now()) / 1000));
    remaining.value = rem;
    if (rem <= 0 && !timeoutSent && socket) {
      timeoutSent = true;
      socket.send({ type: "ROUND_TIMEOUT", payload: {} });
    }
  }
}

onMounted(async () => {
  try {
    const me = await fetchMe();
    myUid = me.uid;
    myUidRef.value = me.uid;
  } catch (_) {
    /* ignore */
  }
  try {
    const snap = await fetchDrawState();
    applyState(snap);
    partnerOnline.value = (snap.players || []).some((p) => p.uid !== myUid && p.online);
  } catch (_) {
    /* ignore (503 = redis down) */
  }
  socket = createCottageSocket({
    path: "/v1/cottage/draw/ws",
    onEvent: handleEvent,
    // A guesser who joins mid-round asks the drawer to re-send the drawing.
    onOpen: () => socket && socket.send({ type: "SYNC_REQUEST", payload: {} })
  });
  timer = setInterval(tick, 250);
});

onBeforeUnmount(() => {
  if (rafId) cancelAnimationFrame(rafId);
  if (timer) clearInterval(timer);
  if (socket) socket.close();
});
</script>

<style scoped>
.draw-view { display: grid; gap: 1rem; }
.presence { font-size: 0.75rem; padding: 0.15rem 0.6rem; border-radius: 999px; background: rgba(148,163,184,0.25); color: #64748b; }
.presence.on { background: rgba(52,211,153,0.2); color: #16a34a; }
.scoreboard {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}
.score-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: rgba(148,163,184,0.12);
  border-radius: 12px;
  padding: 0.4rem 1rem;
  min-width: 84px;
}
.score-cell.me { background: rgba(236,72,153,0.14); }
.score-cell .role { font-size: 0.72rem; color: #64748b; }
.score-cell .pts { font-size: 1.4rem; font-weight: 700; color: #2f3754; }
.round-info { text-align: center; }
.round-no { font-size: 0.85rem; color: #475569; }
.timer { font-size: 1.1rem; font-weight: 700; color: #e2698f; }
.word-line { margin: 0.25rem 0 0.75rem; font-size: 0.95rem; color: #334155; }
.word-line .word { color: #ec4899; letter-spacing: 2px; }
.word-line .mask { letter-spacing: 4px; font-size: 1.2rem; color: #6470c4; }
.word-line.reveal { text-align: center; }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem; margin-top: 0.75rem; }
.swatches { display: flex; gap: 0.25rem; }
.swatch { width: 22px; height: 22px; border-radius: 50%; border: 2px solid rgba(148,163,184,0.4); cursor: pointer; padding: 0; }
.swatch.active { border-color: #0f172a; transform: scale(1.12); }
.tool { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.8rem; color: #475569; }
.tool-btn { border: 1px solid rgba(148,163,184,0.4); background: #fff; border-radius: 999px; padding: 0.3rem 0.7rem; font-size: 0.8rem; cursor: pointer; }
.tool-btn.active { background: #fde68a; border-color: #f59e0b; }
.guess-form { display: flex; gap: 0.5rem; margin-top: 0.75rem; }
.guess-form .input { flex: 1; }
.controls { display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: 0.9rem; }
.finished { text-align: center; margin-top: 1rem; }
.finished h3 { margin: 0 0 0.25rem; color: #2f3754; }
.guess-feed { list-style: none; margin: 1rem 0 0; padding: 0; display: grid; gap: 0.3rem; max-height: 180px; overflow-y: auto; }
.guess-feed li { display: flex; gap: 0.6rem; font-size: 0.85rem; padding: 0.25rem 0.5rem; border-radius: 8px; background: rgba(148,163,184,0.08); }
.guess-feed li.correct { background: rgba(52,211,153,0.18); color: #16a34a; font-weight: 600; }
.guess-feed .who { color: #6470c4; font-weight: 600; }
</style>
