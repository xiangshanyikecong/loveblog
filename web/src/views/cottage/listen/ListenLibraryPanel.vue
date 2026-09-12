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
  <article class="glass-card section-block library">
    <div class="library-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="library-tab"
        :class="{ 'library-tab--active': activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <p v-if="errorMsg" class="library-error">{{ errorMsg }}</p>

    <!-- 我喜欢 (liked tracks) -->
    <div v-if="activeTab === 'liked'" class="library-pane">
      <p v-if="loadingLiked" class="library-empty">…</p>
      <p v-else-if="!likedTracks.length" class="library-empty">{{ t("listenLibrary.likedEmpty") }}</p>
      <ul v-else class="library-list">
        <li v-for="song in likedTracks" :key="song.song_id" class="library-item">
          <img
            v-if="song.cover_url"
            :src="song.cover_url"
            alt=""
            class="library-cover"
            referrerpolicy="no-referrer"
          />
          <span v-else class="library-cover library-cover--ph">♪</span>
          <div class="library-item-text">
            <span class="library-item-name">{{ song.name || song.song_id }}</span>
            <span class="library-item-artists">{{ subText(song) }}</span>
          </div>
          <span class="library-item-duration">{{ formatMs(song.duration_ms) }}</span>
          <div class="library-item-actions">
            <button type="button" class="action-btn" @click="onAddToPlaylist(song, $event)">{{ t("listenLibrary.addToPlaylist") }}</button>
            <button type="button" class="action-btn" @click="$emit('append-to-queue', song)">{{ t("listenSongList.addToQueue") }}</button>
            <button type="button" class="action-btn action-btn--primary" @click="$emit('play-now', song)">{{ t("listenSongList.playNow") }}</button>
            <button type="button" class="action-btn action-btn--danger" @click="onRemoveLiked(song)">{{ t("listenLibrary.remove") }}</button>
          </div>
        </li>
      </ul>
    </div>

    <!-- 我们的歌单 (couple playlists) -->
    <div v-else class="library-pane">
      <!-- grid -->
      <template v-if="!detail">
        <div class="library-playlists-head">
          <div class="library-playlists-intro">
            <h3 class="library-subtitle">{{ t("listenLibrary.playlistsTitle") }}</h3>
            <p class="library-hint">{{ t("listenLibrary.playlistsSubtitle") }}</p>
          </div>
          <button type="button" class="action-btn action-btn--primary" @click="startCreate">
            {{ t("listenLibrary.createPlaylist") }}
          </button>
        </div>

        <form v-if="creating" class="library-form" @submit.prevent="onCreatePlaylist">
          <input
            v-model="newPlaylistName"
            class="library-input"
            :placeholder="t('listenLibrary.playlistNamePlaceholder')"
            maxlength="60"
          />
          <input
            v-model="newPlaylistDesc"
            class="library-input"
            :placeholder="t('listenLibrary.playlistDescPlaceholder')"
            maxlength="200"
          />
          <div class="library-form-actions">
            <button type="button" class="action-btn" :disabled="creatingBusy" @click="creating = false">
              {{ t("listenLibrary.cancel") }}
            </button>
            <button
              type="submit"
              class="action-btn action-btn--primary"
              :disabled="creatingBusy || !newPlaylistName.trim()"
            >
              {{ t("listenLibrary.create") }}
            </button>
          </div>
        </form>

        <p v-if="loadingPlaylists" class="library-empty">…</p>
        <p v-else-if="!playlists.length" class="library-empty">{{ t("listenLibrary.emptyPlaylists") }}</p>
        <ul v-else class="playlist-grid">
          <li v-for="p in playlists" :key="p.pid" class="playlist-item" @click="openDetail(p)">
            <img
              v-if="p.cover_url"
              :src="p.cover_url"
              alt=""
              class="playlist-cover"
              referrerpolicy="no-referrer"
            />
            <div v-else class="playlist-cover playlist-cover--ph">♪</div>
            <div class="playlist-meta">
              <span class="playlist-name">{{ p.name }}</span>
              <span v-if="p.description" class="playlist-desc">{{ p.description }}</span>
              <span class="playlist-count">{{ t("listenLibrary.tracksCount", { count: p.track_count }) }}</span>
            </div>
          </li>
        </ul>
      </template>

      <!-- detail -->
      <template v-else>
        <div class="library-detail-head">
          <div class="library-detail-text">
            <h3 class="library-detail-name">{{ detail.name }}</h3>
            <p v-if="detail.description" class="library-detail-desc">{{ detail.description }}</p>
            <p class="library-detail-count">
              {{ t("listenLibrary.tracksCount", { count: trackCount }) }}
            </p>
          </div>
          <div class="library-detail-actions">
            <button type="button" class="action-btn action-btn--primary" @click="onPlayPlaylist">
              {{ t("listenLibrary.playPlaylist") }}
            </button>
            <button type="button" class="action-btn" @click="startEdit">{{ t("listenLibrary.editPlaylist") }}</button>
            <button type="button" class="action-btn action-btn--danger" @click="onDeletePlaylist">
              {{ t("listenLibrary.deletePlaylist") }}
            </button>
          </div>
        </div>

        <form v-if="editing" class="library-form" @submit.prevent="onSaveEdit">
          <input
            v-model="editName"
            class="library-input"
            :placeholder="t('listenLibrary.playlistNamePlaceholder')"
            maxlength="60"
          />
          <input
            v-model="editDesc"
            class="library-input"
            :placeholder="t('listenLibrary.playlistDescPlaceholder')"
            maxlength="200"
          />
          <div class="library-form-actions">
            <button type="button" class="action-btn" :disabled="editBusy" @click="editing = false">
              {{ t("listenLibrary.cancel") }}
            </button>
            <button
              type="submit"
              class="action-btn action-btn--primary"
              :disabled="editBusy || !editName.trim()"
            >
              {{ t("listenLibrary.save") }}
            </button>
          </div>
        </form>

        <p v-if="loadingDetail" class="library-empty">…</p>
        <p v-else-if="!detailTracks.length" class="library-empty">{{ t("listenLibrary.noTracks") }}</p>
        <ul v-else class="library-list">
          <li v-for="song in detailTracks" :key="song.song_id" class="library-item">
            <img
              v-if="song.cover_url"
              :src="song.cover_url"
              alt=""
              class="library-cover"
              referrerpolicy="no-referrer"
            />
            <span v-else class="library-cover library-cover--ph">♪</span>
            <div class="library-item-text">
              <span class="library-item-name">{{ song.name || song.song_id }}</span>
              <span class="library-item-artists">{{ subText(song) }}</span>
            </div>
            <span class="library-item-duration">{{ formatMs(song.duration_ms) }}</span>
            <div class="library-item-actions">
              <button type="button" class="action-btn" @click="$emit('append-to-queue', song)">{{ t("listenSongList.addToQueue") }}</button>
              <button type="button" class="action-btn action-btn--primary" @click="$emit('play-now', song)">{{ t("listenSongList.playNow") }}</button>
              <button type="button" class="action-btn action-btn--danger" @click="onRemoveTrack(song)">{{ t("listenLibrary.removeTrack") }}</button>
            </div>
          </li>
        </ul>

        <button type="button" class="action-btn library-back" @click="closeDetail">
          ← {{ t("listenLibrary.playlistsTitle") }}
        </button>
      </template>
    </div>

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
  </article>
</template>

<script setup>
/**
 * 一起听 music library: ♥ liked tracks ("我喜欢") and the couple's shared
 * playlists ("我们的歌单"). Playback intent is delegated upward via
 * play-now / append-to-queue; only library CRUD (like, playlists, tracks)
 * happens here.
 */
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import {
  createMyPlaylist,
  deleteMyPlaylist,
  fetchLikedTracks,
  fetchMyPlaylist,
  fetchMyPlaylists,
  playMyPlaylist,
  removeLikedTrack,
  removeTrackFromMyPlaylist,
  updateMyPlaylist
} from "../../../lib/api";
import { parseError } from "../../../utils/helpers";
import PlaylistPickerPopover from "./PlaylistPickerPopover.vue";
import { usePlaylistPicker } from "./usePlaylistPicker";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

defineEmits(["append-to-queue", "play-now"]);

const tabs = computed(() => [
  { key: "liked", label: t("listenLibrary.likedTitle") },
  { key: "playlists", label: t("listenLibrary.playlistsTitle") }
]);

const activeTab = ref("liked");
const errorMsg = ref("");

// ── 我喜欢 ────────────────────────────────────────────────────────────────────
const likedTracks = ref([]);
const loadingLiked = ref(false);

async function loadLiked() {
  loadingLiked.value = true;
  errorMsg.value = "";
  try {
    const data = await fetchLikedTracks({ limit: 100, offset: 0 });
    likedTracks.value = data.items || [];
  } catch (error) {
    errorMsg.value = parseError(error);
  } finally {
    loadingLiked.value = false;
  }
}

async function onRemoveLiked(song) {
  if (!song?.song_id) return;
  try {
    await removeLikedTrack(song.song_id);
    likedTracks.value = likedTracks.value.filter((s) => s.song_id !== song.song_id);
  } catch (error) {
    showMessage(parseError(error));
  }
}

// ── 我们的歌单: grid ──────────────────────────────────────────────────────────
const playlists = ref([]);
const loadingPlaylists = ref(false);
const creating = ref(false);
const creatingBusy = ref(false);
const newPlaylistName = ref("");
const newPlaylistDesc = ref("");

async function loadPlaylists() {
  loadingPlaylists.value = true;
  errorMsg.value = "";
  try {
    const data = await fetchMyPlaylists();
    playlists.value = data.items || [];
  } catch (error) {
    errorMsg.value = parseError(error);
  } finally {
    loadingPlaylists.value = false;
  }
}

function startCreate() {
  creating.value = true;
  newPlaylistName.value = "";
  newPlaylistDesc.value = "";
}

async function onCreatePlaylist() {
  const name = newPlaylistName.value.trim();
  if (!name || creatingBusy.value) return;
  creatingBusy.value = true;
  try {
    await createMyPlaylist({ name, description: newPlaylistDesc.value.trim() });
    creating.value = false;
    newPlaylistName.value = "";
    newPlaylistDesc.value = "";
    await loadPlaylists();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    creatingBusy.value = false;
  }
}

// ── 我们的歌单: detail ────────────────────────────────────────────────────────
const detail = ref(null);
const detailTracks = ref([]);
const loadingDetail = ref(false);
const editing = ref(false);
const editBusy = ref(false);
const editName = ref("");
const editDesc = ref("");

const trackCount = computed(
  () => detail.value?.track_count ?? detailTracks.value.length ?? 0
);

async function openDetail(p) {
  detail.value = p;
  detailTracks.value = [];
  editing.value = false;
  loadingDetail.value = true;
  errorMsg.value = "";
  try {
    const data = await fetchMyPlaylist(p.pid);
    detail.value = data;
    detailTracks.value = data.tracks || [];
  } catch (error) {
    detail.value = null;
    errorMsg.value = parseError(error);
  } finally {
    loadingDetail.value = false;
  }
}

function closeDetail() {
  detail.value = null;
  detailTracks.value = [];
  editing.value = false;
}

function startEdit() {
  editName.value = detail.value?.name || "";
  editDesc.value = detail.value?.description || "";
  editing.value = true;
}

async function onSaveEdit() {
  const pid = detail.value?.pid;
  const name = editName.value.trim();
  if (!pid || !name || editBusy.value) return;
  editBusy.value = true;
  try {
    const updated = await updateMyPlaylist(pid, {
      name,
      description: editDesc.value.trim()
    });
    detail.value = { ...detail.value, ...updated };
    editing.value = false;
    await loadPlaylists();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    editBusy.value = false;
  }
}

async function onDeletePlaylist() {
  const p = detail.value;
  if (!p) return;
  if (!window.confirm(t("listenLibrary.confirmDeletePlaylist", { name: p.name }))) return;
  try {
    await deleteMyPlaylist(p.pid);
    showMessage(t("listenLibrary.playlistDeleted"));
    closeDetail();
    await loadPlaylists();
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function onPlayPlaylist() {
  const p = detail.value;
  if (!p) return;
  try {
    await playMyPlaylist(p.pid);
    showMessage(t("listenLibrary.queuedToast", { count: trackCount.value }));
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function onRemoveTrack(song) {
  const p = detail.value;
  if (!p || !song?.song_id) return;
  try {
    await removeTrackFromMyPlaylist(p.pid, song.song_id);
    detailTracks.value = detailTracks.value.filter((s) => s.song_id !== song.song_id);
    detail.value = { ...detail.value, track_count: detailTracks.value.length };
    playlists.value = playlists.value.map((pl) =>
      pl.pid === p.pid ? { ...pl, track_count: detailTracks.value.length } : pl
    );
  } catch (error) {
    showMessage(parseError(error));
  }
}

// ── shared "add to playlist" picker ───────────────────────────────────────────
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

// ── misc ──────────────────────────────────────────────────────────────────────
function switchTab(key) {
  if (activeTab.value === key) return;
  activeTab.value = key;
  errorMsg.value = "";
  // Always reload on switch: the partner can like songs / edit playlists
  // from their side at any time.
  if (key === "liked") {
    loadLiked();
  } else {
    closeDetail();
    loadPlaylists();
  }
}

function formatMs(ms) {
  if (!ms || ms < 0) return "--:--";
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function albumText(song) {
  const a = song?.album;
  if (!a) return "";
  if (typeof a === "string") return a;
  return a.name || "";
}

function subText(song) {
  const artists = (song?.artists || []).join(", ");
  const album = albumText(song);
  if (artists && album) return `${artists} · ${album}`;
  return artists || album || "";
}

onMounted(loadLiked);
</script>

<style scoped>
.library {
  padding: 1.2rem 1.4rem;
  display: grid;
  gap: 0.85rem;
}

.library-tabs {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.library-tab {
  min-height: 36px;
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(255, 255, 255, 0.7);
  color: #3d4665;
  font-size: 0.84rem;
  cursor: pointer;
}

.library-tab--active {
  border-color: transparent;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
}

.library-pane {
  display: grid;
  gap: 0.85rem;
}

.library-empty {
  margin: 0;
  text-align: center;
  color: #94a3b8;
  font-size: 0.86rem;
  padding: 0.6rem 0;
}

.library-error {
  margin: 0;
  padding: 0.55rem 0.85rem;
  border-radius: 10px;
  background: rgba(252, 165, 165, 0.18);
  color: #b91c1c;
  font-size: 0.85rem;
  text-align: center;
}

.library-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.4rem;
  max-height: 380px;
  overflow-y: auto;
}

.library-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.7rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
}

.library-cover {
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  object-fit: cover;
  background: rgba(148, 163, 184, 0.16);
}

.library-cover--ph {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  color: rgba(148, 163, 184, 0.7);
}

.library-item-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.library-item-name {
  color: #2f3754;
  font-size: 0.88rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.library-item-artists {
  color: #94a3b8;
  font-size: 0.76rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.library-item-duration {
  flex: 0 0 auto;
  color: #94a3b8;
  font-size: 0.76rem;
  font-variant-numeric: tabular-nums;
}

.library-item-actions {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
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

.action-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.action-btn--primary {
  border-color: transparent;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
}

.action-btn--danger {
  border-color: rgba(248, 113, 113, 0.5);
  color: #dc2626;
}

.library-playlists-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.library-playlists-intro {
  display: grid;
  gap: 0.15rem;
}

.library-subtitle {
  margin: 0;
  font-size: 1.05rem;
  color: #2f3754;
}

.library-hint {
  margin: 0;
  font-size: 0.76rem;
  color: #94a3b8;
}

.library-form {
  display: grid;
  gap: 0.45rem;
  padding: 0.75rem;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.6);
}

.library-input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 10px;
  padding: 0.5rem 0.7rem;
  font-size: 0.86rem;
  background: rgba(255, 255, 255, 0.9);
  color: #2f3754;
}

.library-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.35rem;
}

.playlist-grid {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 0.7rem;
  max-height: 380px;
  overflow-y: auto;
}

.playlist-item {
  cursor: pointer;
  display: grid;
  gap: 0.4rem;
  padding: 0.4rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
  transition: transform 0.12s ease;
}

.playlist-item:hover {
  transform: translateY(-2px);
}

.playlist-cover {
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: 8px;
  object-fit: cover;
  background: rgba(148, 163, 184, 0.18);
}

.playlist-cover--ph {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.6rem;
  color: rgba(148, 163, 184, 0.7);
}

.playlist-meta {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}

.playlist-name {
  font-size: 0.84rem;
  color: #2f3754;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.playlist-desc {
  font-size: 0.72rem;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.playlist-count {
  font-size: 0.74rem;
  color: #94a3b8;
}

.library-detail-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.library-detail-text {
  display: grid;
  gap: 0.15rem;
  min-width: 0;
}

.library-detail-name {
  margin: 0;
  font-size: 1.05rem;
  color: #2f3754;
}

.library-detail-desc {
  margin: 0;
  font-size: 0.78rem;
  color: #64748b;
}

.library-detail-count {
  margin: 0;
  font-size: 0.76rem;
  color: #94a3b8;
}

.library-detail-actions {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.library-back {
  justify-self: start;
}

@media (max-width: 768px) {
  .library-item {
    flex-direction: column;
    align-items: stretch;
  }
  .library-item-actions {
    justify-content: flex-end;
  }
  .library-item-duration {
    align-self: flex-end;
  }
  .playlist-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .library-detail-head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
