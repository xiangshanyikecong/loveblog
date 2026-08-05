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
  <div
    class="memory-board"
    :class="{ disabled }"
    :style="{ gridTemplateColumns: `repeat(${size}, minmax(0, 1fr))` }"
  >
    <button
      v-for="cell in cellsView"
      :key="cell.key"
      type="button"
      class="memory-cell"
      :class="cell.className"
      :disabled="disabled || cell.matched || cell.up"
      @click="$emit('flip', { x: cell.x, y: cell.y })"
    >
      <span v-if="cell.showFace" class="face">{{ cell.face }}</span>
      <span v-else class="back">?</span>
    </button>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  size: { type: Number, default: 4 },
  tiles: { type: Array, default: () => [] },
  states: { type: Array, default: () => [] },
  icons: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false }
});

defineEmits(["flip"]);

const cellsView = computed(() => {
  const out = [];
  for (let y = 0; y < props.size; y += 1) {
    for (let x = 0; x < props.size; x += 1) {
      const idx = y * props.size + x;
      const state = props.states[idx] ?? 0;
      const tile = props.tiles[idx] ?? 0;
      const matched = state === 2;
      const up = state === 1;
      const showFace = state === 1 || state === 2;
      out.push({
        key: `${x}-${y}`,
        x,
        y,
        matched,
        up,
        showFace,
        face: props.icons[tile - 1] || tile,
        className: {
          up,
          matched
        }
      });
    }
  }
  return out;
});
</script>

<style scoped>
.memory-board {
  display: grid;
  /* columns are set inline from the `size` prop */
  gap: 0.55rem;
  max-width: 360px;
  margin: 0 auto;
}
.memory-cell {
  aspect-ratio: 1 / 1;
  border: none;
  border-radius: 14px;
  background: linear-gradient(140deg, #ff8ab5, #8f9bff);
  color: #fff;
  font-size: 1.5rem;
  cursor: pointer;
  box-shadow: 0 6px 14px rgba(143, 155, 255, 0.25);
  transition: transform 0.12s ease;
}
.memory-cell:disabled { cursor: default; opacity: 0.85; }
.memory-cell.up { background: rgba(255, 255, 255, 0.92); color: #2f3754; }
.memory-cell.matched { background: rgba(52, 211, 153, 0.2); color: #166534; }
.memory-cell:not(:disabled):hover { transform: translateY(-2px); }
.back { font-weight: 700; }
.face { font-size: 1.6rem; }
.memory-board.disabled .memory-cell { opacity: 0.7; }
</style>
