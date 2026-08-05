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
  <svg
    class="reversi-board"
    :viewBox="`0 0 ${boardPx} ${boardPx}`"
    :class="{ disabled }"
    @click="onClick"
  >
    <rect :width="boardPx" :height="boardPx" rx="14" class="board-bg" />

    <!-- grid -->
    <line
      v-for="i in size + 1"
      :key="`v-${i}`"
      :x1="pad + (i - 1) * cell"
      :y1="pad"
      :x2="pad + (i - 1) * cell"
      :y2="boardPx - pad"
      class="grid-line"
    />
    <line
      v-for="i in size + 1"
      :key="`h-${i}`"
      :x1="pad"
      :y1="pad + (i - 1) * cell"
      :x2="boardPx - pad"
      :y2="pad + (i - 1) * cell"
      class="grid-line"
    />

    <!-- legal move hints -->
    <circle
      v-for="(pt, idx) in (disabled ? [] : legalMoves)"
      :key="`hint-${idx}`"
      :cx="cx(pt[0])"
      :cy="cy(pt[1])"
      :r="cell * 0.13"
      class="hint"
    />

    <!-- discs -->
    <g v-for="d in discs" :key="`d-${d.x}-${d.y}`">
      <circle
        :cx="cx(d.x)"
        :cy="cy(d.y)"
        :r="cell * 0.4"
        :class="d.color === 1 ? 'disc-black' : 'disc-white'"
      />
      <circle
        v-if="isLast(d.x, d.y)"
        :cx="cx(d.x)"
        :cy="cy(d.y)"
        :r="cell * 0.1"
        class="last-marker"
      />
    </g>
  </svg>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  cells: { type: Array, default: () => [] },
  size: { type: Number, default: 8 },
  lastMove: { type: Object, default: null },
  legalMoves: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false }
});

const emit = defineEmits(["place"]);

const pad = 6;
const cell = 44;
const boardPx = computed(() => props.size * cell + pad * 2);

function cx(x) {
  return pad + x * cell + cell / 2;
}
function cy(y) {
  return pad + y * cell + cell / 2;
}

const discs = computed(() => {
  const out = [];
  const n = props.size;
  for (let i = 0; i < props.cells.length; i += 1) {
    const v = props.cells[i];
    if (v === 1 || v === 2) {
      out.push({ x: i % n, y: Math.floor(i / n), color: v });
    }
  }
  return out;
});

function isLast(x, y) {
  return props.lastMove && props.lastMove.x === x && props.lastMove.y === y;
}

function onClick(event) {
  if (props.disabled) return;
  const svg = event.currentTarget;
  const rect = svg.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const px = ((event.clientX - rect.left) / rect.width) * boardPx.value;
  const py = ((event.clientY - rect.top) / rect.height) * boardPx.value;
  const x = Math.floor((px - pad) / cell);
  const y = Math.floor((py - pad) / cell);
  if (x < 0 || y < 0 || x >= props.size || y >= props.size) return;
  const idx = y * props.size + x;
  if (props.cells[idx] === 1 || props.cells[idx] === 2) return; // occupied
  emit("place", { x, y });
}
</script>

<style scoped>
.reversi-board {
  width: 100%;
  max-width: 420px;
  height: auto;
  display: block;
  margin: 0 auto;
  touch-action: manipulation;
  cursor: pointer;
}
.reversi-board.disabled {
  cursor: default;
}
.board-bg {
  fill: #2f9e6b;
  stroke: #248055;
  stroke-width: 2;
}
.grid-line {
  stroke: rgba(0, 0, 0, 0.28);
  stroke-width: 1;
}
.hint {
  fill: rgba(255, 255, 255, 0.55);
}
.disc-black {
  fill: #1a1a1a;
  stroke: #000;
  stroke-width: 0.5;
}
.disc-white {
  fill: #fafafa;
  stroke: #c8c8c8;
  stroke-width: 1;
}
.last-marker {
  fill: #ff5a5a;
}
</style>
