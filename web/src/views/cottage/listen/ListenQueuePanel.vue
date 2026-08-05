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
  <article class="glass-card section-block queue">
    <div class="queue-header">
      <h3 class="queue-heading">{{ t("listenQueue.queueTitle", { n: queue.length }) }}</h3>
      <button
        v-if="queue.length"
        type="button"
        class="queue-clear"
        @click="$emit('clear')"
      >
        {{ t("listenQueue.clearQueue") }}
      </button>
    </div>

    <p v-if="!queue.length" class="queue-empty">{{ t("listenQueue.empty") }}</p>

    <ul v-else class="queue-list">
      <li
        v-for="(song, idx) in queue"
        :key="`${song.song_id}-${idx}`"
        class="queue-item"
      >
        <span class="queue-name">
          {{ song.name || song.song_id }}
          <span v-if="song.artists?.length" class="queue-artists">— {{ song.artists.join(", ") }}</span>
        </span>
        <button
          type="button"
          class="queue-remove"
          :aria-label="t('listenQueue.removeAria')"
          @click="$emit('remove', { index: idx, song_id: song.song_id })"
        >×</button>
      </li>
    </ul>
  </article>
</template>

<script setup>
import { useI18n } from "vue-i18n";

const { t } = useI18n();

defineProps({
  queue: { type: Array, default: () => [] }
});
defineEmits(["remove", "clear"]);
</script>

<style scoped>
.queue {
  padding: 1.2rem 1.4rem;
  display: grid;
  gap: 0.75rem;
}

.queue-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.queue-heading {
  margin: 0;
  font-size: 0.95rem;
  color: #2f3754;
}

.queue-clear {
  min-height: 32px;
  padding: 0.32rem 0.75rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.7);
  color: #3d4665;
  font-size: 0.78rem;
  cursor: pointer;
}

.queue-empty {
  margin: 0;
  color: #94a3b8;
  font-size: 0.9rem;
  padding: 0.6rem 0;
  text-align: center;
}

.queue-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.45rem;
}

.queue-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 0.75rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
  font-size: 0.86rem;
}

.queue-name {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #334155;
}

.queue-artists {
  color: #94a3b8;
  font-size: 0.78rem;
  margin-left: 0.4rem;
}

.queue-remove {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: rgba(15, 23, 42, 0.18);
  color: #fff;
  font-size: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
