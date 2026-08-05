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
  <article class="glass-card section-block player">
    <p v-if="!current.song_id" class="player-empty">
      {{ t("listenPlayer.empty") }}
    </p>

    <template v-else>
      <div class="player-meta">
        <img
          v-if="current.song_meta?.cover_url"
          :src="current.song_meta.cover_url"
          alt=""
          class="player-cover"
          referrerpolicy="no-referrer"
        />
        <div v-else class="player-cover player-cover--placeholder">♪</div>
        <div class="player-text">
          <h3 class="player-title">{{ current.song_meta?.name || current.song_id }}</h3>
          <p class="player-artists">
            {{ (current.song_meta?.artists || []).join(", ") || t("listenPlayer.unknownArtist") }}
          </p>
        </div>
      </div>

      <div class="player-progress">
        <span class="player-time">{{ formatMs(clampedPositionMs) }}</span>
        <input
          type="range"
          class="player-slider"
          :class="{ 'player-slider--loading': !durationMs }"
          :min="0"
          :max="durationMs || 0"
          :step="1000"
          :value="sliderValue"
          :style="sliderFillStyle"
          @change="onSeekCommit"
        />
        <span class="player-time">{{ durationMs ? formatMs(durationMs) : "--:--" }}</span>
      </div>

      <div ref="lyricsRef" class="player-lyrics">
        <p v-if="lyricLoading" class="player-lyrics-hint">{{ t("listenPlayer.lyricLoading") }}</p>
        <p v-else-if="lyricKind === 'instrumental'" class="player-lyrics-hint">
          {{ t("listenPlayer.instrumental") }}
        </p>
        <p v-else-if="!lyricLines.length" class="player-lyrics-hint">{{ t("listenPlayer.noLyrics") }}</p>
        <template v-else>
          <p
            v-for="(line, i) in lyricLines"
            :key="i"
            :data-line="i"
            class="player-lyric-line"
            :class="{ 'is-active': i === activeIndex }"
          >
            <span class="player-lyric-text">{{ line.text }}</span>
            <span v-if="line.trans" class="player-lyric-trans">{{ line.trans }}</span>
          </p>
        </template>
      </div>

      <p v-if="needsResume" class="player-resume-hint">
        {{ t("listenPlayer.resumeHint") }}
      </p>

      <div class="player-controls">
        <button type="button" class="player-btn" @click="$emit('prev')">⏮</button>
        <button
          type="button"
          class="player-btn player-btn--primary"
          @click="onPrimaryClick"
        >
          {{ needsResume || current.paused ? "▶" : "⏸" }}
        </button>
        <button type="button" class="player-btn" @click="$emit('next')">⏭</button>
      </div>
    </template>
  </article>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps({
  current: { type: Object, required: true },
  localPositionMs: { type: Number, default: 0 },
  // Real duration read off the <audio> element (loadedmetadata) — used as a
  // fallback when song_meta carries no duration_ms, so the progress bar can
  // still scale instead of being stuck at max=0.
  mediaDurationMs: { type: Number, default: 0 },
  lyricLines: { type: Array, default: () => [] },
  lyricKind: { type: String, default: "lrc" },
  lyricLoading: { type: Boolean, default: false },
  // True when our local <audio> was blocked from autoplaying (refresh) while
  // the room is still playing. The primary button then re-joins locally
  // instead of toggling shared state — see CottageListenView.
  needsResume: { type: Boolean, default: false }
});

// Track length in ms. Prefer the metadata duration (known instantly from the
// NetEase song meta) and fall back to the actual decoded media duration.
const durationMs = computed(() => {
  const metaDur = Number(props.current?.song_meta?.duration_ms || 0);
  if (metaDur > 0) return metaDur;
  return Number(props.mediaDurationMs || 0);
});

// Position clamped into [0, duration] so the thumb never overshoots the end
// (currentTime can briefly read a touch beyond duration_ms near the boundary).
const clampedPositionMs = computed(() => {
  const pos = Number(props.localPositionMs || 0);
  const dur = durationMs.value;
  if (dur > 0) return Math.min(Math.max(0, pos), dur);
  return Math.max(0, pos);
});

// The slider's bound value: the real position while we know the length, but 0
// when the length is still unknown (max=0) so the thumb never clamps to the far
// right. The left time label keeps showing the true elapsed time regardless.
const sliderValue = computed(() => (durationMs.value > 0 ? clampedPositionMs.value : 0));

// Native range inputs only render a thumb — no "played" fill. Paint the
// elapsed portion ourselves with a gradient whose hard stop sits at the
// current percentage, so it reads as a real progress bar.
const sliderFillStyle = computed(() => {
  const dur = durationMs.value;
  const pct = dur > 0 ? Math.min(100, Math.max(0, (clampedPositionMs.value / dur) * 100)) : 0;
  return {
    background: `linear-gradient(to right, #ff8ab5 0%, #8f9bff ${pct}%, rgba(148, 163, 184, 0.32) ${pct}%, rgba(148, 163, 184, 0.32) 100%)`
  };
});

const emit = defineEmits(["play", "pause", "seek", "prev", "next", "resume-local"]);

const lyricsRef = ref(null);

// Index of the line currently being sung: the last line whose timestamp has
// already passed. -1 before the first line (intro).
const activeIndex = computed(() => {
  const pos = props.localPositionMs;
  const lines = props.lyricLines;
  let idx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].time_ms <= pos) idx = i;
    else break;
  }
  return idx;
});

// Keep the active line vertically centered by scrolling the lyrics container
// itself (never the page). offsetTop is measured against the container because
// it is positioned (position: relative in CSS).
watch(activeIndex, async (idx) => {
  if (idx < 0) return;
  await nextTick();
  const container = lyricsRef.value;
  if (!container) return;
  const el = container.querySelector(`[data-line="${idx}"]`);
  if (!el) return;
  const top = el.offsetTop - container.clientHeight / 2 + el.clientHeight / 2;
  container.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
});

function formatMs(ms) {
  if (!ms || ms < 0) return "0:00";
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function onPlayPause() {
  if (props.current.paused) {
    emit("play");
  } else {
    emit("pause");
  }
}

// After an autoplay block (refresh), the primary button RE-JOINS the partner's
// live playback locally instead of toggling the shared timeline — broadcasting
// a play/pause here would drag the partner's progress bar to our stale time.
function onPrimaryClick() {
  if (props.needsResume) {
    emit("resume-local");
    return;
  }
  onPlayPause();
}

function onSeekCommit(evt) {
  // Length still unknown (no meta + autoplay-blocked decode): a seek would
  // resolve against a bogus max, so ignore it until we know the duration.
  if (!durationMs.value) return;
  const target = Number(evt.target.value || 0);
  emit("seek", target);
}
</script>

<style scoped>
.player {
  padding: 1.3rem 1.5rem;
  display: grid;
  gap: 1rem;
}

.player-empty {
  margin: 0;
  text-align: center;
  color: #94a3b8;
  font-size: 0.92rem;
  padding: 1.3rem 0;
}

.player-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.player-cover {
  width: 80px;
  height: 80px;
  border-radius: 12px;
  object-fit: cover;
  background: rgba(148, 163, 184, 0.16);
}

.player-cover--placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2rem;
  color: rgba(148, 163, 184, 0.7);
}

.player-text {
  flex: 1;
  min-width: 0;
}

.player-title {
  margin: 0 0 0.25rem;
  font-size: 1rem;
  color: #2f3754;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.player-artists {
  margin: 0;
  font-size: 0.84rem;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.player-progress {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  font-size: 0.78rem;
  color: #64748b;
}

.player-time {
  flex: 0 0 auto;
  font-variant-numeric: tabular-nums;
}

.player-slider {
  flex: 1;
  appearance: none;
  height: 5px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.32);
  outline: none;
}

.player-slider::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  cursor: pointer;
}

/* Duration not yet known: keep the bar visible (not the greyed `disabled`
   look that read as "broken"), just hint that it's still resolving. */
.player-slider--loading {
  cursor: progress;
  opacity: 0.65;
}

.player-lyrics {
  position: relative;
  height: 168px;
  overflow-y: auto;
  scroll-behavior: smooth;
  text-align: center;
  padding: 0.4rem 0;
  -webkit-mask-image: linear-gradient(
    to bottom,
    transparent,
    #000 18%,
    #000 82%,
    transparent
  );
  mask-image: linear-gradient(
    to bottom,
    transparent,
    #000 18%,
    #000 82%,
    transparent
  );
}

.player-lyrics::-webkit-scrollbar {
  width: 0;
}

.player-lyrics-hint {
  margin: 0;
  padding: 3.4rem 0;
  color: #94a3b8;
  font-size: 0.85rem;
}

.player-lyric-line {
  margin: 0;
  padding: 0.32rem 0.6rem;
  color: #94a3b8;
  font-size: 0.9rem;
  line-height: 1.45;
  transition: color 0.25s ease, transform 0.25s ease;
}

.player-lyric-line.is-active {
  color: #2f3754;
  font-weight: 600;
  transform: scale(1.04);
}

.player-lyric-line.is-active .player-lyric-trans {
  color: #64748b;
}

.player-lyric-text {
  display: block;
}

.player-lyric-trans {
  display: block;
  margin-top: 0.12rem;
  font-size: 0.78rem;
  font-weight: 400;
  color: #aab4c5;
}

.player-resume-hint {
  margin: 0;
  text-align: center;
  font-size: 0.8rem;
  color: #ad6800;
  background: rgba(250, 219, 20, 0.16);
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
}

.player-controls {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
}

.player-btn {
  min-width: 44px;
  min-height: 44px;
  padding: 0 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.85);
  color: #3d4665;
  font-size: 1.1rem;
  cursor: pointer;
}

.player-btn--primary {
  border-color: transparent;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
  font-size: 1.25rem;
  min-width: 56px;
  min-height: 56px;
}
</style>
