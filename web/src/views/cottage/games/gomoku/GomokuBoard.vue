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
    class="gomoku-board"
    :viewBox="`0 0 ${boardPx} ${boardPx}`"
    :class="{ disabled }"
    @click="onClick"
  >
    <!-- wood background -->
    <rect :width="boardPx" :height="boardPx" rx="10" class="board-bg" />

    <!-- grid lines -->
    <line
      v-for="i in size"
      :key="`h-${i}`"
      :x1="margin"
      :y1="margin + (i - 1) * gap"
      :x2="margin + (size - 1) * gap"
      :y2="margin + (i - 1) * gap"
      class="grid-line"
    />
    <line
      v-for="i in size"
      :key="`v-${i}`"
      :x1="margin + (i - 1) * gap"
      :y1="margin"
      :x2="margin + (i - 1) * gap"
      :y2="margin + (size - 1) * gap"
      class="grid-line"
    />

    <!-- star points -->
    <circle
      v-for="(pt, idx) in starPoints"
      :key="`star-${idx}`"
      :cx="margin + pt[0] * gap"
      :cy="margin + pt[1] * gap"
      :r="gap * 0.08"
      class="star-point"
    />

    <!-- stones -->
    <g v-for="stone in stones" :key="`s-${stone.x}-${stone.y}`">
      <circle
        :cx="margin + stone.x * gap"
        :cy="margin + stone.y * gap"
        :r="gap * 0.42"
        :class="stone.color === 1 ? 'stone-black' : 'stone-white'"
      />
      <circle
        v-if="isLastMove(stone.x, stone.y)"
        :cx="margin + stone.x * gap"
        :cy="margin + stone.y * gap"
        :r="gap * 0.12"
        class="last-marker"
      />
    </g>

    <!-- winning line highlight -->
    <circle
      v-for="(pt, idx) in winLine"
      :key="`w-${idx}`"
      :cx="margin + pt[0] * gap"
      :cy="margin + pt[1] * gap"
      :r="gap * 0.46"
      class="win-ring"
    />
  </svg>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  cells: { type: Array, default: () => [] },
  size: { type: Number, default: 15 },
  lastMove: { type: Object, default: null },
  winLine: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false }
});

const emit = defineEmits(["place"]);

const gap = 36;
const margin = 26;
const boardPx = computed(() => (props.size - 1) * gap + margin * 2);

const stones = computed(() => {
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

const starPoints = computed(() => {
  // Standard 15x15 star points; for other sizes, just the center (天元).
  if (props.size === 15) {
    return [
      [3, 3], [11, 3], [3, 11], [11, 11], [7, 7]
    ];
  }
  const c = Math.floor(props.size / 2);
  return [[c, c]];
});

function isLastMove(x, y) {
  return props.lastMove && props.lastMove.x === x && props.lastMove.y === y;
}

function onClick(event) {
  if (props.disabled) return;
  const svg = event.currentTarget;
  const rect = svg.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const px = ((event.clientX - rect.left) / rect.width) * boardPx.value;
  const py = ((event.clientY - rect.top) / rect.height) * boardPx.value;
  const x = Math.round((px - margin) / gap);
  const y = Math.round((py - margin) / gap);
  if (x < 0 || y < 0 || x >= props.size || y >= props.size) return;
  const idx = y * props.size + x;
  if (props.cells[idx] === 1 || props.cells[idx] === 2) return; // occupied
  emit("place", { x, y });
}
</script>

<style scoped>
.gomoku-board {
  width: 100%;
  max-width: 480px;
  height: auto;
  display: block;
  margin: 0 auto;
  touch-action: manipulation;
  cursor: pointer;
}
.gomoku-board.disabled {
  cursor: default;
}
.board-bg {
  fill: #e9c08a;
  stroke: #d9ac6f;
  stroke-width: 2;
}
.grid-line {
  stroke: #8a5a2b;
  stroke-width: 1.2;
  opacity: 0.7;
}
.star-point {
  fill: #5b3a1a;
}
.stone-black {
  fill: radial-gradient(#444, #000);
  fill: #1a1a1a;
  stroke: #000;
  stroke-width: 0.5;
}
.stone-white {
  fill: #fafafa;
  stroke: #c8c8c8;
  stroke-width: 1;
}
.last-marker {
  fill: #ff5a5a;
}
.win-ring {
  fill: none;
  stroke: #ff3b3b;
  stroke-width: 2.5;
  opacity: 0.9;
}
</style>
