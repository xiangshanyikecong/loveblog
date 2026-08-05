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
    class="ttt-board"
    :viewBox="`0 0 ${boardPx} ${boardPx}`"
    :class="{ disabled }"
    @click="onClick"
  >
    <rect :width="boardPx" :height="boardPx" rx="18" class="board-bg" />

    <!-- grid lines -->
    <line
      v-for="i in 2"
      :key="`v-${i}`"
      :x1="pad + i * cell"
      :y1="pad + 6"
      :x2="pad + i * cell"
      :y2="boardPx - pad - 6"
      class="grid-line"
    />
    <line
      v-for="i in 2"
      :key="`h-${i}`"
      :x1="pad + 6"
      :y1="pad + i * cell"
      :x2="boardPx - pad - 6"
      :y2="pad + i * cell"
      class="grid-line"
    />

    <!-- winning cells highlight (drawn under the marks) -->
    <rect
      v-for="(pt, idx) in winLine"
      :key="`w-${idx}`"
      :x="pad + pt[0] * cell + 4"
      :y="pad + pt[1] * cell + 4"
      :width="cell - 8"
      :height="cell - 8"
      rx="12"
      class="win-cell"
    />

    <!-- marks -->
    <g v-for="m in marks" :key="`m-${m.x}-${m.y}`">
      <!-- X (black / 先手) -->
      <template v-if="m.color === 1">
        <line
          :x1="cx(m.x) - r" :y1="cy(m.y) - r"
          :x2="cx(m.x) + r" :y2="cy(m.y) + r"
          class="mark-x" :class="{ last: isLast(m.x, m.y) }"
        />
        <line
          :x1="cx(m.x) + r" :y1="cy(m.y) - r"
          :x2="cx(m.x) - r" :y2="cy(m.y) + r"
          class="mark-x" :class="{ last: isLast(m.x, m.y) }"
        />
      </template>
      <!-- O (white / 后手) -->
      <circle
        v-else
        :cx="cx(m.x)" :cy="cy(m.y)" :r="r"
        class="mark-o" :class="{ last: isLast(m.x, m.y) }"
      />
    </g>
  </svg>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  cells: { type: Array, default: () => [] },
  size: { type: Number, default: 3 },
  lastMove: { type: Object, default: null },
  winLine: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false }
});

const emit = defineEmits(["place"]);

const pad = 12;
const cell = 100;
const boardPx = computed(() => props.size * cell + pad * 2);
const r = cell * 0.28;

function cx(x) {
  return pad + x * cell + cell / 2;
}
function cy(y) {
  return pad + y * cell + cell / 2;
}

const marks = computed(() => {
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
.ttt-board {
  width: 100%;
  max-width: 340px;
  height: auto;
  display: block;
  margin: 0 auto;
  touch-action: manipulation;
  cursor: pointer;
}
.ttt-board.disabled {
  cursor: default;
}
.board-bg {
  fill: rgba(255, 255, 255, 0.72);
  stroke: rgba(143, 155, 255, 0.35);
  stroke-width: 2;
}
.grid-line {
  stroke: rgba(143, 155, 255, 0.55);
  stroke-width: 4;
  stroke-linecap: round;
}
.mark-x {
  stroke: #e2698f;
  stroke-width: 9;
  stroke-linecap: round;
}
.mark-o {
  fill: none;
  stroke: #6470c4;
  stroke-width: 9;
}
.mark-x.last,
.mark-o.last {
  filter: drop-shadow(0 0 6px rgba(255, 138, 181, 0.55));
}
.win-cell {
  fill: rgba(52, 211, 153, 0.22);
  stroke: rgba(22, 163, 74, 0.5);
  stroke-width: 2;
}
</style>
