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
    class="link-board"
    :class="{ disabled }"
    :style="{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }"
  >
    <button
      v-for="cell in cellsView"
      :key="cell.key"
      type="button"
      class="link-cell"
      :class="{ empty: cell.empty, pending: cell.pending }"
      :disabled="disabled || cell.empty"
      @click="$emit('pick', { x: cell.x, y: cell.y })"
    >
      <span v-if="!cell.empty">{{ cell.label }}</span>
    </button>
  </div>
</template>

<script setup>
import { computed } from "vue";

// Must cover all PAIR_COUNT (=24) tile ids the backend uses; with only 12
// labels, ids 1 and 13 rendered the same icon while the server treated them as
// different pairs — visually misleading. Keep this list unique and >= 24.
const TILE_LABELS = [
  "🍓", "🍇", "🍉", "🍑", "🥝", "🍒", "🍋", "🫐",
  "🍍", "🥥", "🍈", "🍊", "🍎", "🍐", "🍌", "🥭",
  "🍅", "🍆", "🌽", "🥕", "🥑", "🥦", "🧄", "🧅"
];

const props = defineProps({
  cols: { type: Number, default: 8 },
  rows: { type: Number, default: 6 },
  cells: { type: Array, default: () => [] },
  pending: { type: Array, default: null },
  disabled: { type: Boolean, default: false }
});

defineEmits(["pick"]);

const cellsView = computed(() => {
  const out = [];
  for (let y = 0; y < props.rows; y += 1) {
    for (let x = 0; x < props.cols; x += 1) {
      const idx = y * props.cols + x;
      const value = props.cells[idx] ?? 0;
      const empty = value === 0;
      const pending =
        Array.isArray(props.pending) && props.pending[0] === x && props.pending[1] === y;
      out.push({
        key: `${x}-${y}`,
        x,
        y,
        empty,
        pending,
        label: TILE_LABELS[(value - 1) % TILE_LABELS.length] || value
      });
    }
  }
  return out;
});
</script>

<style scoped>
.link-board {
  display: grid;
  gap: 0.35rem;
  max-width: 640px;
  margin: 0 auto;
}
.link-cell {
  aspect-ratio: 1 / 1;
  border: none;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.85);
  font-size: 1.15rem;
  cursor: pointer;
  box-shadow: inset 0 0 0 1px rgba(143, 155, 255, 0.25);
}
.link-cell.empty {
  background: rgba(148, 163, 184, 0.12);
  box-shadow: none;
  cursor: default;
}
.link-cell.pending {
  box-shadow: 0 0 0 2px rgba(255, 138, 181, 0.8);
}
.link-board.disabled .link-cell:not(.empty) { opacity: 0.75; }
</style>
