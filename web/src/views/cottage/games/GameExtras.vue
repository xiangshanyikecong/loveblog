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
  <div class="game-extras">
    <div class="float-layer" aria-hidden="true">
      <span
        v-for="f in floats"
        :key="f.id"
        class="float-emote"
        :style="{ left: f.left + '%' }"
      >{{ f.emote }}</span>
    </div>

    <!-- 悔棋 (take-back) bar — board games only -->
    <div v-if="enableUndo && requestedByPartner" class="undo-bar ask">
      <span class="undo-text">{{ t("cottageGames.common.undoRequestPrompt") }}</span>
      <div class="undo-actions">
        <button class="mini-btn ok" @click="respondUndo(true)">{{ t("cottageGames.common.undoAccept") }}</button>
        <button class="mini-btn no" @click="respondUndo(false)">{{ t("cottageGames.common.undoReject") }}</button>
      </div>
    </div>
    <div v-else-if="enableUndo && requestedByMe" class="undo-bar waiting">
      <span class="undo-text">{{ t("cottageGames.common.undoWaiting") }}</span>
    </div>
    <div v-else-if="enableUndo && canRequestUndo" class="undo-bar">
      <button class="mini-btn ghost" @click="requestUndo">{{ t("cottageGames.common.undoBtn") }}</button>
    </div>

    <!-- emote bar -->
    <div class="emote-bar">
      <button
        v-for="e in EMOTES"
        :key="e"
        type="button"
        class="emote-btn"
        @click="sendEmote(e)"
      >{{ e }}</button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { t } from "../../../locales";

const props = defineProps({
  room: { type: Object, required: true },
  myUid: { type: String, default: "" },
  partnerUid: { type: String, default: "" },
  send: { type: Function, default: () => {} },
  /** Board games only; flip/pair games keep this off. */
  enableUndo: { type: Boolean, default: true }
});

// Must match the backend whitelist in cottage_games_ws.py.
const EMOTES = ["❤️", "😘", "😝", "👍", "🤝", "😭", "🎉", "🤔"];

const isPlaying = computed(() => props.room.phase === "playing");
function isBlackMove(color) {
  return color === 1 || color === "black";
}

const lastMoverUid = computed(() => {
  const lm = props.room.last_move;
  if (!lm) return null;
  return isBlackMove(lm.color) ? props.room.black_uid : props.room.white_uid;
});
const canRequestUndo = computed(
  () =>
    props.enableUndo &&
    isPlaying.value &&
    !props.room.undo_request_by &&
    lastMoverUid.value === props.myUid
);
const requestedByMe = computed(
  () => !!props.room.undo_request_by && props.room.undo_request_by === props.myUid
);
const requestedByPartner = computed(
  () => !!props.room.undo_request_by && props.room.undo_request_by !== props.myUid
);

function requestUndo() {
  props.send({ type: "UNDO_REQUEST", payload: {} });
}
function respondUndo(accept) {
  props.send({ type: "UNDO_RESPOND", payload: { accept } });
}
function sendEmote(emote) {
  props.send({ type: "EMOTE", payload: { emote } });
}

const floats = ref([]);
let floatSeq = 0;

function showFloat(emote) {
  if (!emote) return;
  const id = floatSeq += 1;
  const left = 18 + Math.random() * 64;
  floats.value.push({ id, emote, left });
  setTimeout(() => {
    floats.value = floats.value.filter((f) => f.id !== id);
  }, 1800);
}

defineExpose({ showFloat });
</script>

<style scoped>
.game-extras {
  position: relative;
  display: grid;
  gap: 0.7rem;
  justify-items: center;
}
.float-layer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 100%;
  height: 140px;
  pointer-events: none;
  overflow: visible;
}
.float-emote {
  position: absolute;
  bottom: 0;
  font-size: 1.8rem;
  animation: floatUp 1.8s ease-out forwards;
}
@keyframes floatUp {
  0% { transform: translateY(0) scale(0.6); opacity: 0; }
  20% { opacity: 1; transform: translateY(-20px) scale(1.1); }
  100% { transform: translateY(-130px) scale(1); opacity: 0; }
}

.undo-bar {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  justify-content: center;
}
.undo-bar.ask {
  background: rgba(255, 138, 181, 0.12);
  border: 1px solid rgba(255, 138, 181, 0.4);
  border-radius: 12px;
  padding: 0.4rem 0.8rem;
}
.undo-text { font-size: 0.84rem; color: var(--text-soft); }
.undo-actions { display: flex; gap: 0.4rem; }

.mini-btn {
  border: none;
  border-radius: 999px;
  padding: 0.3rem 0.9rem;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
}
.mini-btn.ghost {
  background: rgba(255, 255, 255, 0.65);
  color: #6470c4;
  border: 1px solid rgba(143, 155, 255, 0.5);
}
.mini-btn.ok { background: #34d399; color: #fff; }
.mini-btn.no { background: rgba(255, 255, 255, 0.7); color: #d6455f; border: 1px solid rgba(214, 69, 95, 0.4); }

.emote-bar {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
  justify-content: center;
}
.emote-btn {
  border: 1px solid rgba(148, 163, 184, 0.3);
  background: rgba(255, 255, 255, 0.6);
  border-radius: 12px;
  width: 38px;
  height: 38px;
  font-size: 1.15rem;
  line-height: 1;
  cursor: pointer;
  transition: transform 0.1s ease, background 0.15s ease;
}
.emote-btn:hover { transform: translateY(-2px); background: rgba(255, 255, 255, 0.9); }
.emote-btn:active { transform: scale(0.92); }
</style>
