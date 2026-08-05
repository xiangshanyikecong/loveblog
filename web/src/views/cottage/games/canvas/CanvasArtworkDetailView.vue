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
  <div class="content-section artwork-detail">
    <header class="detail-header">
      <router-link to="/cottage/games/canvas/gallery" class="ghost-btn">{{ t("cottageGames.artworkDetail.backToGallery") }}</router-link>
      <h2 v-if="artwork">{{ artwork.title || t("cottageGames.gallery.untitled") }}</h2>
    </header>

    <p v-if="loading" class="state-text">{{ t("cottageGames.artworkDetail.loading") }}</p>
    <p v-else-if="errorMsg" class="error-text">{{ errorMsg }}</p>

    <template v-else-if="artwork">
      <div class="stage-wrap">
        <SharedCanvas
          ref="canvasRef"
          :drawable="false"
          :readonly-hint="t('cottageGames.artworkDetail.readonlyHint', { name: artwork.author_nickname })"
        />
      </div>

      <section class="meta">
        <div class="meta-row">
          <span>{{ t("cottageGames.artworkDetail.author") }}</span>
          <strong>{{ artwork.author_nickname }}</strong>
        </div>
        <div class="meta-row">
          <span>{{ t("cottageGames.artworkDetail.createdAt") }}</span>
          <strong>{{ formatDate(artwork.created_at) }}</strong>
        </div>
        <div class="meta-row">
          <span>{{ t("cottageGames.artworkDetail.strokeCount") }}</span>
          <strong>{{ artwork.stroke_count }} {{ t("cottageGames.artworkDetail.strokes") }}</strong>
        </div>
        <div class="meta-row">
          <span>{{ t("cottageGames.artworkDetail.collaborators") }}</span>
          <span class="collab-list">
            <span
              v-for="c in artwork.collaborators"
              :key="c.user_uid"
              class="collaborator-chip"
              :title="t('cottageGames.gallery.contributorTitle', { name: c.nickname, n: c.stroke_count })"
            >{{ initialOf(c.nickname) }}</span>
            <span v-if="!artwork.collaborators.length" class="muted">{{ t("cottageGames.artworkDetail.none") }}</span>
          </span>
        </div>
        <div class="meta-row">
          <span>{{ t("cottageGames.artworkDetail.canvasSize") }}</span>
          <strong>{{ artwork.width }} × {{ artwork.height }}</strong>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import SharedCanvas from "../../../../components/SharedCanvas.vue";
import { fetchCanvasArtwork } from "../../../../lib/api";
import { parseError } from "../../../../utils/helpers";
import { t } from "../../../../locales";

const route = useRoute();

const artwork = ref(null);
const loading = ref(false);
const errorMsg = ref("");
const canvasRef = ref(null);

function initialOf(name) {
  const s = String(name || "").trim();
  return s ? s.charAt(0).toUpperCase() : "·";
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function load() {
  const caid = route.params.caid;
  if (!caid) {
    errorMsg.value = t("cottageGames.artworkDetail.notExist");
    return;
  }
  loading.value = true;
  errorMsg.value = "";
  try {
    const data = await fetchCanvasArtwork(caid);
    artwork.value = data;
    // Once the component is mounted, replay the strokes onto the read-only canvas.
    await new Promise(requestAnimationFrame);
    let payload = null;
    if (data.strokes_json) {
      try {
        const decoded = JSON.parse(data.strokes_json);
        payload = decoded.strokes || [];
      } catch (_) {
        payload = [];
      }
    }
    if (canvasRef.value && Array.isArray(payload)) {
      canvasRef.value.loadSync(payload);
    }
  } catch (err) {
    errorMsg.value = parseError(err);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.artwork-detail { display: grid; gap: 1rem; }
.detail-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.detail-header h2 { margin: 0; color: #2f3754; font-size: 1.3rem; }
.ghost-btn {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0.35rem 0.8rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.8);
  color: #3d4665;
  font-size: 0.8rem;
  text-decoration: none;
}
.state-text, .error-text {
  margin: 0;
  padding: 1rem;
  text-align: center;
  border-radius: 12px;
  background: rgba(148, 163, 184, 0.1);
  color: var(--text-soft);
}
.error-text { background: rgba(252, 165, 165, 0.18); color: #b91c1c; }
.stage-wrap {
  background: #fff;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  overflow: hidden;
}
.meta {
  display: grid;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: #fff;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.18);
}
.meta-row {
  display: grid;
  grid-template-columns: 96px 1fr;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.88rem;
}
.meta-row > span:first-child { color: var(--text-soft); }
.meta-row strong { color: #2f3754; font-weight: 600; }
.collab-list {
  display: inline-flex;
  gap: 0.3rem;
  flex-wrap: wrap;
  align-items: center;
}
.collaborator-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: linear-gradient(135deg, #818cf8, #ec4899);
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
}
.muted { color: var(--text-soft); font-size: 0.85rem; }
</style>
