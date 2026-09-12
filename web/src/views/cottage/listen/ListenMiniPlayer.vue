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
  <transition name="listen-mini-pop">
    <div v-if="visible" class="listen-mini">
      <button class="listen-mini-main" type="button" :aria-label="t('listenMiniPlayer.ariaOpen')" @click="open">
        <img
          v-if="current.song_meta?.cover_url"
          :src="current.song_meta.cover_url"
          alt=""
          class="listen-mini-cover"
          referrerpolicy="no-referrer"
        />
        <span v-else class="listen-mini-cover listen-mini-cover--ph">♪</span>
        <span class="listen-mini-text">
          <span class="listen-mini-title-row">
            <span class="listen-mini-title">{{ current.song_meta?.name || current.song_id }}</span>
            <button
              v-if="current.song_meta"
              type="button"
              class="listen-mini-like"
              :class="{ 'listen-mini-like--active': liked }"
              @click.stop="onToggleLike"
            >{{ liked ? "♥" : "♡" }}</button>
          </span>
          <span class="listen-mini-sub">
            {{ (current.song_meta?.artists || []).join(", ") || t("listenMiniPlayer.defaultSub") }}
          </span>
        </span>
      </button>

      <div class="listen-mini-controls">
        <button
          type="button"
          class="listen-mini-btn listen-mini-btn--primary"
          :aria-label="isPaused ? t('listenMiniPlayer.ariaPlay') : t('listenMiniPlayer.ariaPause')"
          @click="togglePlay"
        >
          {{ isPaused ? "▶" : "⏸" }}
        </button>
        <button type="button" class="listen-mini-btn" :aria-label="t('listenMiniPlayer.ariaNext')" @click="onNext">⏭</button>
        <button type="button" class="listen-mini-close" :aria-label="t('listenMiniPlayer.ariaClose')" @click="hide">✕</button>
      </div>
    </div>
  </transition>
</template>

<script setup>
/**
 * Floating mini-player shown app-wide while 一起听 is playing and the user is
 * somewhere other than the full 一起听 page. It drives the same persistent
 * stores/listenPlayer engine, so audio keeps playing across navigation and the
 * controls here stay in sync with the partner.
 */
import { computed, inject, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { useListenPlayer } from "../../../stores/listenPlayer";
import { fetchLikedStatus, toggleLikedTrack } from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});
const route = useRoute();
const router = useRouter();

const {
  current,
  needsResumeGesture,
  onResume,
  onPause,
  onNext,
  onResumeLocalPlayback
} = useListenPlayer();

// User can dismiss the window for the current song; a new song re-shows it.
const dismissed = ref(false);
watch(
  () => current.value.song_id,
  () => {
    dismissed.value = false;
  }
);

// ♥ liked-tracks state for the current song, mirroring the full player card.
// Re-checked whenever the room switches songs.
const liked = ref(false);
watch(
  () => current.value.song_id,
  async (songId) => {
    liked.value = false;
    if (!songId) return;
    try {
      const data = await fetchLikedStatus([songId]);
      liked.value = (data.song_ids || []).includes(songId);
    } catch {
      liked.value = false;
    }
  },
  { immediate: true }
);

async function onToggleLike() {
  const song = current.value?.song_meta;
  if (!song) return;
  try {
    const data = await toggleLikedTrack(song);
    liked.value = !!data.liked;
    showMessage(t(data.liked ? "listenLibrary.likedToastOn" : "listenLibrary.likedToastOff"));
  } catch (error) {
    showMessage(parseError(error));
  }
}

const isPaused = computed(() => needsResumeGesture.value || current.value.paused);

const visible = computed(
  () => !dismissed.value && !!current.value.song_id && route.path !== "/cottage/listen"
);

function open() {
  router.push("/cottage/listen");
}

function hide() {
  dismissed.value = true;
}

function togglePlay() {
  if (needsResumeGesture.value) {
    onResumeLocalPlayback();
    return;
  }
  if (current.value.paused) {
    onResume();
  } else {
    onPause();
  }
}
</script>

<style scoped>
.listen-mini {
  position: fixed;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  z-index: 75;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: min(94vw, 420px);
  padding: 0.5rem 0.6rem;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.22);
  border: 1px solid rgba(148, 163, 184, 0.28);
}

.listen-mini-main {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
  text-align: left;
}

.listen-mini-cover {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  object-fit: cover;
  flex: 0 0 auto;
  background: rgba(148, 163, 184, 0.18);
}
.listen-mini-cover--ph {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.3rem;
  color: rgba(148, 163, 184, 0.8);
}

.listen-mini-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.listen-mini-title-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  min-width: 0;
}

.listen-mini-title {
  min-width: 0;
  font-size: 0.86rem;
  font-weight: 600;
  color: #2f3754;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.listen-mini-like {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.38);
  background: rgba(255, 255, 255, 0.9);
  color: #94a3b8;
  font-size: 0.85rem;
  line-height: 1;
  padding: 0;
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.listen-mini-like--active {
  color: #ff5c8a;
  border-color: rgba(255, 92, 138, 0.45);
  background: rgba(255, 92, 138, 0.08);
}

.listen-mini-like:active {
  transform: scale(0.92);
}
.listen-mini-sub {
  font-size: 0.74rem;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.listen-mini-controls {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  flex: 0 0 auto;
}
.listen-mini-btn {
  width: 38px;
  height: 38px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  color: #3d4665;
  border: 1px solid rgba(148, 163, 184, 0.42);
  font-size: 1rem;
  cursor: pointer;
}
.listen-mini-btn--primary {
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
  border: none;
}
.listen-mini-close {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 0.85rem;
  cursor: pointer;
}

.listen-mini-pop-enter-active,
.listen-mini-pop-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.listen-mini-pop-enter-from,
.listen-mini-pop-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(16px);
}
</style>
