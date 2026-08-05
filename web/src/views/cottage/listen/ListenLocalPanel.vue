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
  <article class="glass-card section-block local">
    <header class="local-header">
      <h3>{{ t("listenLocal.title") }}</h3>
      <span class="local-hint">{{ t("listenLocal.hint") }}</span>
    </header>

    <div class="local-upload">
      <input
        ref="fileInput"
        type="file"
        accept="audio/*"
        class="local-file"
        :disabled="uploading"
        @change="onFilePicked"
      />
      <p v-if="uploading" class="local-status">{{ t("listenLocal.uploading") }}</p>
      <p v-else-if="uploadError" class="local-status local-status--error">{{ uploadError }}</p>
    </div>

    <p v-if="loading" class="local-empty">{{ t("listenLocal.loading") }}</p>
    <p v-else-if="!tracks.length" class="local-empty">{{ t("listenLocal.empty") }}</p>
    <ul v-else class="local-list">
      <li v-for="song in tracks" :key="song.song_id" class="local-item">
        <div class="local-item-text">
          <span class="local-item-name">{{ song.name }}</span>
          <span class="local-item-artists">{{ (song.artists || []).join(", ") || t("listenLocal.localAudio") }}</span>
        </div>
        <div class="local-item-actions">
          <button type="button" class="action-btn" @click="$emit('append-to-queue', song)">{{ t("listenLocal.addToQueue") }}</button>
          <button type="button" class="action-btn action-btn--primary" @click="$emit('play-now', song)">{{ t("listenLocal.playNow") }}</button>
          <button type="button" class="action-btn action-btn--danger" @click="removeTrack(song)">{{ t("listenLocal.delete") }}</button>
        </div>
      </li>
    </ul>
  </article>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { deleteLocalTrack, listenLocalTracks, uploadLocalTrack } from "../../../lib/api";

const { t } = useI18n();

defineEmits(["append-to-queue", "play-now"]);

const tracks = ref([]);
const loading = ref(false);
const uploading = ref(false);
const uploadError = ref("");
const fileInput = ref(null);

async function loadTracks() {
  loading.value = true;
  try {
    const data = await listenLocalTracks();
    tracks.value = data.items || [];
  } catch (e) {
    uploadError.value = e?.response?.data?.detail?.message || t("listenLocal.errLoad");
  } finally {
    loading.value = false;
  }
}

function readDurationMs(file) {
  return new Promise((resolve) => {
    try {
      const url = URL.createObjectURL(file);
      const audio = new Audio();
      audio.preload = "metadata";
      audio.onloadedmetadata = () => {
        const ms = Number.isFinite(audio.duration) ? Math.round(audio.duration * 1000) : null;
        URL.revokeObjectURL(url);
        resolve(ms);
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        resolve(null);
      };
      audio.src = url;
    } catch {
      resolve(null);
    }
  });
}

async function onFilePicked(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  uploading.value = true;
  uploadError.value = "";
  try {
    const durationMs = await readDurationMs(file);
    const name = file.name.replace(/\.[^.]+$/, "");
    await uploadLocalTrack(file, { name, duration_ms: durationMs });
    await loadTracks();
  } catch (e) {
    uploadError.value = e?.response?.data?.detail?.message || t("listenLocal.errUpload");
  } finally {
    uploading.value = false;
    if (fileInput.value) fileInput.value.value = "";
  }
}

async function removeTrack(song) {
  const tid = String(song.song_id || "").replace(/^local:/, "");
  if (!tid) return;
  try {
    await deleteLocalTrack(tid);
    tracks.value = tracks.value.filter((t) => t.song_id !== song.song_id);
  } catch (e) {
    uploadError.value = e?.response?.data?.detail?.message || t("listenLocal.errDelete");
  }
}

onMounted(loadTracks);
</script>

<style scoped>
.local {
  padding: 1.2rem 1.4rem;
  display: grid;
  gap: 0.85rem;
}

.local-header {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.local-header h3 {
  margin: 0;
  font-size: 1.05rem;
  color: #2f3754;
}

.local-hint {
  font-size: 0.76rem;
  color: #94a3b8;
}

.local-file {
  width: 100%;
  font-size: 0.84rem;
  color: #3d4665;
}

.local-status {
  margin: 0.4rem 0 0;
  font-size: 0.8rem;
  color: #64748b;
}

.local-status--error {
  color: #dc2626;
}

.local-empty {
  margin: 0;
  text-align: center;
  color: #94a3b8;
  font-size: 0.86rem;
  padding: 0.6rem 0;
}

.local-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.4rem;
  max-height: 380px;
  overflow-y: auto;
}

.local-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.7rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
}

.local-item-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.local-item-name {
  color: #2f3754;
  font-size: 0.88rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.local-item-artists {
  color: #94a3b8;
  font-size: 0.76rem;
}

.local-item-actions {
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

.action-btn--primary {
  border-color: transparent;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
}

.action-btn--danger {
  border-color: rgba(248, 113, 113, 0.5);
  color: #dc2626;
}

@media (max-width: 768px) {
  .local-item {
    flex-direction: column;
    align-items: stretch;
  }
  .local-item-actions {
    justify-content: flex-end;
  }
}
</style>
