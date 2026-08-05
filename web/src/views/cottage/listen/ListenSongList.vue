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
  <ul class="search-list">
    <li v-for="song in songs" :key="song.song_id" class="search-item">
      <div class="search-item-text">
        <span class="search-item-name">{{ song.name }}</span>
        <span class="search-item-artists">{{ (song.artists || []).join(", ") }}</span>
      </div>
      <div class="search-item-actions">
        <button type="button" class="action-btn" @click="$emit('append-to-queue', song)">{{ t("listenSongList.addToQueue") }}</button>
        <button type="button" class="action-btn action-btn--primary" @click="$emit('play-now', song)">{{ t("listenSongList.playNow") }}</button>
      </div>
    </li>
  </ul>
</template>

<script setup>
import { useI18n } from "vue-i18n";

const { t } = useI18n();

defineProps({
  songs: { type: Array, default: () => [] }
});

defineEmits(["append-to-queue", "play-now"]);
</script>

<style scoped>
.search-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.4rem;
  max-height: 380px;
  overflow-y: auto;
}

.search-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.7rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
}

.search-item-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.search-item-name {
  color: #2f3754;
  font-size: 0.88rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.search-item-artists {
  color: #94a3b8;
  font-size: 0.76rem;
}

.search-item-actions {
  display: flex;
  gap: 0.35rem;
}

.action-btn {
  min-height: 36px;
  padding: 0.32rem 0.65rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(255, 255, 255, 0.85);
  color: #3d4665;
  font-size: 0.78rem;
  cursor: pointer;
}

.action-btn--primary {
  border-color: transparent;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
}

@media (max-width: 768px) {
  .search-item {
    flex-direction: column;
    align-items: stretch;
  }
  .search-item-actions {
    justify-content: flex-end;
  }
}
</style>
