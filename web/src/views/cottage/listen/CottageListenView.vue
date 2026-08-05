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
  <div class="content-section listen">
    <header class="listen-header">
      <div class="listen-title">
        <h2>{{ t("cottageListen.title") }}</h2>
        <ListenLoginPanel
          :me-logged-in="meSelfLoggedIn"
          @login-success="onLoginSuccess"
          @logout="onLogoutLocal"
        />
      </div>
      <router-link to="/cottage" class="listen-back">{{ t("cottageListen.backToCottage") }}</router-link>
    </header>

    <ListenStatusBar
      :partners="partners"
      :last-event-origin-uid="lastEventOriginUid"
    />

    <ListenPlayerCard
      :current="current"
      :local-position-ms="localPositionMs"
      :media-duration-ms="mediaDurationMs"
      :lyric-lines="lyricLines"
      :lyric-kind="lyricKind"
      :lyric-loading="lyricLoading"
      :needs-resume="needsResumeGesture"
      @play="onResume"
      @pause="onPause"
      @seek="onSeek"
      @prev="onPrev"
      @next="onNext"
      @resume-local="onResumeLocalPlayback"
    />

    <ListenQueuePanel
      :queue="queue"
      @remove="onQueueRemove"
      @clear="onQueueClear"
    />

    <ListenLocalPanel
      @append-to-queue="onAppendToQueue"
      @play-now="onPlayNow"
    />

    <ListenSearchPanel
      :me-logged-in="meSelfLoggedIn"
      @append-to-queue="onAppendToQueue"
      @play-now="onPlayNow"
    />

    <p v-if="errorMsg" class="listen-error">{{ errorMsg }}</p>
  </div>
</template>

<script setup>
/**
 * 一起听 full view. The playback engine (audio element + sync socket + room
 * state) lives in the app-level stores/listenPlayer singleton so playback
 * survives navigation and powers the floating mini-player. This view is now a
 * thin consumer: it binds the shared state to the panels and kicks off the
 * engine once via init() (idempotent).
 */
import { onMounted } from "vue";
import { useI18n } from "vue-i18n";

import { useListenPlayer } from "../../../stores/listenPlayer";
import ListenLocalPanel from "./ListenLocalPanel.vue";
import ListenLoginPanel from "./ListenLoginPanel.vue";
import ListenPlayerCard from "./ListenPlayerCard.vue";
import ListenQueuePanel from "./ListenQueuePanel.vue";
import ListenSearchPanel from "./ListenSearchPanel.vue";
import ListenStatusBar from "./ListenStatusBar.vue";

const {
  current,
  queue,
  partners,
  localPositionMs,
  mediaDurationMs,
  errorMsg,
  lyricLines,
  lyricKind,
  lyricLoading,
  needsResumeGesture,
  lastEventOriginUid,
  meSelfLoggedIn,
  init,
  onResume,
  onResumeLocalPlayback,
  onPause,
  onSeek,
  onPrev,
  onNext,
  onAppendToQueue,
  onPlayNow,
  onQueueRemove,
  onQueueClear,
  onLoginSuccess,
  onLogoutLocal
} = useListenPlayer();

const { t } = useI18n();

onMounted(() => {
  // Idempotent: connects the socket + loads state on first open; a re-open just
  // re-binds to the already-running engine (playback never restarts).
  init();
});
</script>

<style scoped>
.listen {
  display: grid;
  gap: 1rem;
}

.listen-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.listen-title {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex-wrap: wrap;
}

.listen-title h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #2f3754;
}

.listen-back {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  font-size: 0.82rem;
  text-decoration: none;
}

.listen-error {
  margin: 0;
  padding: 0.55rem 0.85rem;
  border-radius: 10px;
  background: rgba(252, 165, 165, 0.18);
  color: #b91c1c;
  font-size: 0.85rem;
  text-align: center;
}

@media (max-width: 768px) {
  .listen-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
