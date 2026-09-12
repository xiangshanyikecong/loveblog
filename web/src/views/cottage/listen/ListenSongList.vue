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
        <button
          type="button"
          class="like-btn"
          :class="{ 'like-btn--active': isLiked(song.song_id) }"
          @click="onToggleLike(song)"
        >{{ isLiked(song.song_id) ? "♥" : "♡" }}</button>
        <button type="button" class="action-btn" @click="onAddToPlaylist(song, $event)">{{ t("listenLibrary.addToPlaylist") }}</button>
        <button type="button" class="action-btn" @click="$emit('append-to-queue', song)">{{ t("listenSongList.addToQueue") }}</button>
        <button type="button" class="action-btn action-btn--primary" @click="$emit('play-now', song)">{{ t("listenSongList.playNow") }}</button>
      </div>
    </li>
  </ul>

  <PlaylistPickerPopover
    :open="pickerOpen"
    :playlists="pickerPlaylists"
    :loading="pickerLoading"
    :saving="pickerSaving"
    :song-name="pickerSong?.name || ''"
    :anchor="pickerAnchor"
    @select="addToPlaylist"
    @create="createPlaylistAndAdd"
    @close="closePicker"
  />
</template>

<script setup>
import { inject, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { fetchLikedStatus, toggleLikedTrack } from "../../../lib/api";
import { parseError } from "../../../utils/helpers";
import PlaylistPickerPopover from "./PlaylistPickerPopover.vue";
import { usePlaylistPicker } from "./usePlaylistPicker";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

const props = defineProps({
  songs: { type: Array, default: () => [] }
});

defineEmits(["append-to-queue", "play-now"]);

// ♥ liked ids for the currently rendered songs, batch-fetched whenever the
// list changes (search results swap, playlist opens...).
const likedIds = ref(new Set());
let likedSeq = 0;

watch(
  () => (props.songs || []).map((s) => s.song_id).filter(Boolean).join(","),
  refreshLiked,
  { immediate: true }
);

async function refreshLiked() {
  const ids = (props.songs || []).map((s) => s.song_id).filter(Boolean);
  const seq = ++likedSeq;
  if (!ids.length) {
    likedIds.value = new Set();
    return;
  }
  try {
    const data = await fetchLikedStatus(ids);
    if (seq !== likedSeq) return; // a newer list already replaced this one
    likedIds.value = new Set(data.song_ids || []);
  } catch {
    // Best-effort decoration: a failed status check just leaves the hearts
    // grey instead of nagging the user with toasts.
  }
}

function isLiked(songId) {
  return likedIds.value.has(songId);
}

async function onToggleLike(song) {
  try {
    const data = await toggleLikedTrack(song);
    const next = new Set(likedIds.value);
    if (data.liked) next.add(song.song_id);
    else next.delete(song.song_id);
    likedIds.value = next;
    showMessage(t(data.liked ? "listenLibrary.likedToastOn" : "listenLibrary.likedToastOff"));
  } catch (error) {
    showMessage(parseError(error));
  }
}

// ── "add to couple playlist" picker (shared popover) ──────────────────────────
const {
  pickerOpen,
  pickerSong,
  pickerAnchor,
  pickerPlaylists,
  pickerLoading,
  pickerSaving,
  openPicker,
  closePicker,
  addToPlaylist,
  createPlaylistAndAdd
} = usePlaylistPicker();

function onAddToPlaylist(song, evt) {
  openPicker(song, evt?.currentTarget);
}
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
  align-items: center;
  gap: 0.35rem;
}

.like-btn {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(255, 255, 255, 0.85);
  color: #94a3b8;
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  transition: color 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.like-btn--active {
  color: #ff5c8a;
  border-color: rgba(255, 92, 138, 0.45);
  background: rgba(255, 92, 138, 0.08);
}

.like-btn:active {
  transform: scale(0.92);
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
    flex-wrap: wrap;
  }
}
</style>
