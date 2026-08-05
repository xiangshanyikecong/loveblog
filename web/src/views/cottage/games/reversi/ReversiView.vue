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
  <div class="content-section reversi-view">
    <article class="glass-card section-block reversi-head">
      <div class="head-row">
        <router-link to="/cottage/games" class="back-link">{{ t("cottageGames.common.backToGames") }}</router-link>
        <h2>{{ t("cottageGames.reversi.title") }}</h2>
        <button class="ghost-btn" :disabled="!socketReady" @click="invite">{{ t("cottageGames.common.callPartner") }}</button>
      </div>

      <div class="players">
        <div class="player-card" :class="{ active: isPlaying && room.turn_uid === myUid }">
          <span class="seat-dot" :class="seatClass(myColor)"></span>
          <div class="player-meta">
            <p class="player-name">{{ myName || t("cottageGames.common.me") }} <span class="me-tag">{{ t("cottageGames.common.me") }}</span></p>
            <p class="player-sub">{{ colorLabel(myColor) }} · {{ t("cottageGames.reversi.pieces") }} {{ myCount }} · {{ t("cottageGames.common.winLabel") }} {{ myWins }}</p>
          </div>
        </div>
        <div class="vs">VS</div>
        <div class="player-card" :class="{ active: isPlaying && room.turn_uid === partnerUid }">
          <span class="seat-dot" :class="seatClass(partnerColor)"></span>
          <div class="player-meta">
            <p class="player-name">
              {{ partnerName || t("cottageGames.common.otherHalf") }}
              <span class="online-dot" :class="{ on: partnerOnline }"></span>
            </p>
            <p class="player-sub">{{ colorLabel(partnerColor) }} · {{ t("cottageGames.reversi.pieces") }} {{ partnerCount }} · {{ t("cottageGames.common.winLabel") }} {{ partnerWins }}</p>
          </div>
        </div>
      </div>

      <p class="status-line" :class="statusClass">{{ statusText }}</p>
    </article>

    <section class="glass-card section-block board-wrap">
      <ReversiBoard
        :cells="room.cells"
        :size="room.size"
        :last-move="room.last_move"
        :legal-moves="canPlace ? room.legal_moves : []"
        :disabled="!canPlace"
        @place="place"
      />
    </section>

    <section class="glass-card section-block extras-wrap">
      <GameExtras
        ref="gameExtras"
        :room="room"
        :my-uid="myUid"
        :partner-uid="partnerUid"
        :send="sendToSocket"
      />
    </section>

    <section class="actions">
      <button class="primary-btn" :disabled="!socketReady" @click="newGame">
        {{ isPlaying ? t("cottageGames.common.restart") : t("cottageGames.common.newGame") }}
      </button>
      <button
        class="danger-btn"
        :disabled="!socketReady || !isPlaying || !myColor"
        @click="surrender"
      >
        {{ t("cottageGames.common.surrender") }}
      </button>
    </section>
  </div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import ReversiBoard from "./ReversiBoard.vue";
import GameExtras from "../GameExtras.vue";
import { fetchGameMatches, fetchGameState, fetchMe, inviteGamePartner } from "../../../../lib/api";
import { createGamesSocket } from "../../../../lib/cottageGamesWs";
import { confirmDialog } from "../../../../lib/dialog";
import { parseError } from "../../../../utils/helpers";
import { t } from "../../../../locales";

const GAME = "reversi";
const showMessage = inject("showMessage", () => {});

const myUid = ref("");
const myName = ref("");
const socketReady = ref(false);
const nameByUid = reactive({});
const partnerOnline = ref(false);
const myWins = ref(0);
const partnerWins = ref(0);

const room = reactive({
  phase: "waiting",
  size: 8,
  cells: [],
  turn: null,
  turn_uid: null,
  winner: null,
  win_line: [],
  legal_moves: [],
  last_move: null,
  move_count: 0,
  black_uid: null,
  white_uid: null,
  undo_request_by: null,
  seq: 0
});

let socket = null;
const gameExtras = ref(null);

function sendToSocket(msg) {
  if (socket) socket.send(msg);
}

const myColor = computed(() => {
  if (myUid.value && myUid.value === room.black_uid) return "black";
  if (myUid.value && myUid.value === room.white_uid) return "white";
  return null;
});
const partnerUid = computed(() => {
  if (!myUid.value) return null;
  if (room.black_uid && room.black_uid !== myUid.value) return room.black_uid;
  if (room.white_uid && room.white_uid !== myUid.value) return room.white_uid;
  return Object.keys(nameByUid).find((u) => u !== myUid.value) || null;
});
const partnerColor = computed(() => {
  if (partnerUid.value && partnerUid.value === room.black_uid) return "black";
  if (partnerUid.value && partnerUid.value === room.white_uid) return "white";
  return null;
});
const partnerName = computed(() => nameByUid[partnerUid.value] || "");

const blackCount = computed(() => room.cells.filter((c) => c === 1).length);
const whiteCount = computed(() => room.cells.filter((c) => c === 2).length);
const myCount = computed(() => (myColor.value === "white" ? whiteCount.value : myColor.value === "black" ? blackCount.value : 0));
const partnerCount = computed(() => (partnerColor.value === "white" ? whiteCount.value : partnerColor.value === "black" ? blackCount.value : 0));

const isPlaying = computed(() => room.phase === "playing");
const isMyTurn = computed(() => isPlaying.value && room.turn_uid === myUid.value);
const canPlace = computed(() => socketReady.value && isMyTurn.value);

const statusText = computed(() => {
  if (room.phase === "waiting") return t("cottageGames.common.waitingHint");
  if (room.phase === "finished") {
    if (room.winner === "draw") return t("cottageGames.reversi.drawStatus", { black: blackCount.value, white: whiteCount.value });
    const winnerUid = room.winner === "black" ? room.black_uid : room.white_uid;
    const mine = winnerUid === myUid.value;
    return mine
      ? t("cottageGames.reversi.winStatus", { mine: myCount.value, theirs: partnerCount.value })
      : t("cottageGames.reversi.loseStatus", { name: partnerName.value || t("cottageGames.common.partner"), theirs: partnerCount.value, mine: myCount.value });
  }
  if (isMyTurn.value) return t("cottageGames.common.yourTurn", { mark: colorLabel(myColor.value) });
  return t("cottageGames.common.waitingPartnerMove");
});
const statusClass = computed(() => {
  if (room.phase === "finished") {
    const winnerUid = room.winner === "black" ? room.black_uid : room.white_uid;
    if (room.winner !== "draw" && winnerUid === myUid.value) return "win";
  }
  if (isMyTurn.value) return "your-turn";
  return "";
});

function colorLabel(color) {
  if (color === "black") return t("cottageGames.reversi.black");
  if (color === "white") return t("cottageGames.reversi.white");
  return t("cottageGames.common.watching");
}
function seatClass(color) {
  return { black: color === "black", white: color === "white" };
}

function applyState(payload) {
  if (!payload) return;
  if (typeof payload.seq === "number" && payload.seq < room.seq) return;
  Object.assign(room, payload);
}

async function refreshStats() {
  try {
    const data = await fetchGameMatches(GAME, 1);
    const stats = data.stats || [];
    myWins.value = (stats.find((s) => s.uid === myUid.value) || {}).wins || 0;
    const partnerStat = stats.find((s) => s.uid !== myUid.value);
    partnerWins.value = partnerStat ? partnerStat.wins : 0;
  } catch (_) {
    /* ignore */
  }
}

function handleEvent(e) {
  if (!e || typeof e !== "object") return;
  if (e.type === "STATE") {
    applyState(e.payload);
  } else if (e.type === "PRESENCE") {
    if (e.payload && e.payload.uid === partnerUid.value) {
      partnerOnline.value = !!e.payload.online;
    }
  } else if (e.type === "PRESENCE_SNAPSHOT") {
    const online = (e.payload && e.payload.online) || [];
    if (partnerUid.value) partnerOnline.value = online.includes(partnerUid.value);
  } else if (e.type === "GAME_OVER") {
    applyState(e.payload);
    refreshStats();
  } else if (e.type === "INVITE") {
    const from = (e.payload && e.payload.from_nickname) || t("cottageGames.common.partner");
    showMessage(t("cottageGames.reversi.inviteToast", { name: from }));
  } else if (e.type === "EMOTE") {
    const emote = e.payload && e.payload.emote;
    if (emote && gameExtras.value) gameExtras.value.showFloat(emote);
  } else if (e.type === "UNDO_RESULT") {
    const accepted = e.payload && e.payload.accepted;
    const requester = e.payload && e.payload.requester;
    if (requester && requester === myUid.value) {
      showMessage(accepted ? t("cottageGames.common.undoAccepted") : t("cottageGames.common.undoRejected"));
    }
  } else if (e.type === "ERROR") {
    showMessage((e.payload && e.payload.message) || t("cottageGames.common.operationFailed"));
  }
}

function place({ x, y }) {
  if (!canPlace.value || !socket) return;
  socket.send({ type: "MOVE", payload: { x, y } });
}

async function newGame() {
  if (!socket) return;
  if (isPlaying.value) {
    const ok = await confirmDialog(t("cottageGames.common.confirmRestartMsg"), { title: t("cottageGames.common.restart") });
    if (!ok) return;
  }
  socket.send({ type: "NEW_GAME", payload: {} });
}

async function surrender() {
  if (!socket || !isPlaying.value || !myColor.value) return;
  const ok = await confirmDialog("确定认输吗？这一局将判对方获胜。", { title: "认输", danger: true });
  if (!ok) return;
  socket.send({ type: "SURRENDER", payload: {} });
}

async function invite() {
  try {
    await inviteGamePartner(GAME);
    showMessage(t("cottageGames.common.inviteCalledToast"));
  } catch (error) {
    showMessage(parseError(error));
  }
}

onMounted(async () => {
  try {
    const me = await fetchMe();
    myUid.value = me.uid;
    myName.value = me.nickname;
    if (me.uid) nameByUid[me.uid] = me.nickname;
  } catch (_) {
    /* ignore */
  }
  try {
    const state = await fetchGameState(GAME);
    (state.players || []).forEach((p) => {
      nameByUid[p.uid] = p.nickname;
      if (p.uid === partnerUid.value || p.uid !== myUid.value) {
        if (p.online) partnerOnline.value = true;
      }
    });
    applyState(state);
  } catch (error) {
    showMessage(parseError(error));
  }
  await refreshStats();
  socket = createGamesSocket({
    game: GAME,
    onEvent: handleEvent,
    onOpen: () => {
      socketReady.value = true;
    },
    onClose: () => {
      socketReady.value = false;
    }
  });
});

onBeforeUnmount(() => {
  if (socket) socket.close();
});
</script>

<style scoped>
.reversi-view { display: grid; gap: 1rem; }
.reversi-head { padding: 1.1rem 1.2rem; display: grid; gap: 0.9rem; }
.head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}
.head-row h2 { margin: 0; font-size: 1.15rem; }
.back-link { color: var(--text-soft); text-decoration: none; font-size: 0.86rem; }
.ghost-btn {
  border: 1px solid rgba(143, 155, 255, 0.5);
  background: rgba(255, 255, 255, 0.6);
  color: #6470c4;
  border-radius: 999px;
  padding: 0.34rem 0.85rem;
  font-size: 0.8rem;
  cursor: pointer;
}
.ghost-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.players {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 0.6rem;
}
.player-card {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.55rem 0.7rem;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid transparent;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.player-card.active {
  border-color: rgba(255, 138, 181, 0.8);
  box-shadow: 0 6px 16px rgba(255, 138, 181, 0.25);
}
.seat-dot {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  flex: 0 0 auto;
  background: #cbd5e1;
  border: 1px solid rgba(0, 0, 0, 0.15);
}
.seat-dot.black { background: #1a1a1a; }
.seat-dot.white { background: #fafafa; }
.player-meta { min-width: 0; }
.player-name {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 700;
  color: #2f3754;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.me-tag {
  font-size: 0.62rem;
  background: #8f9bff;
  color: #fff;
  border-radius: 6px;
  padding: 0 0.3rem;
}
.online-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e1;
  display: inline-block;
}
.online-dot.on { background: #34d399; }
.player-sub { margin: 0; font-size: 0.74rem; color: var(--text-soft); }
.vs { font-weight: 700; color: var(--text-soft); font-size: 0.8rem; }

.status-line {
  margin: 0;
  text-align: center;
  font-size: 0.9rem;
  color: var(--text-soft);
}
.status-line.your-turn { color: #e2698f; font-weight: 600; }
.status-line.win { color: #16a34a; font-weight: 700; }

.board-wrap { padding: 1rem; }
.extras-wrap { padding: 0.9rem 1rem 1.1rem; }

.actions {
  display: flex;
  gap: 0.7rem;
  justify-content: center;
}
.primary-btn, .danger-btn {
  border: none;
  border-radius: 999px;
  padding: 0.55rem 1.4rem;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
}
.primary-btn {
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
  box-shadow: 0 8px 16px rgba(143, 155, 255, 0.3);
}
.danger-btn {
  background: rgba(255, 255, 255, 0.7);
  color: #d6455f;
  border: 1px solid rgba(214, 69, 95, 0.4);
}
.primary-btn:disabled, .danger-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
