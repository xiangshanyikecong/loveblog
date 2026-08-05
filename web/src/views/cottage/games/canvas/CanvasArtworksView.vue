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
  <div class="content-section canvas-gallery">
    <header class="gallery-header">
      <div>
        <h2>{{ t("cottageGames.gallery.title") }}</h2>
        <p class="hint">{{ t("cottageGames.gallery.hint") }}</p>
      </div>
      <div class="gallery-actions">
        <router-link to="/cottage/games/canvas" class="ghost-btn">{{ t("cottageGames.gallery.backToCanvas") }}</router-link>
      </div>
    </header>

    <p v-if="loading" class="state-text">{{ t("cottageGames.gallery.loading") }}</p>
    <p v-else-if="errorMsg" class="error-text">{{ errorMsg }}</p>
    <p v-else-if="!items.length" class="empty">
      {{ t("cottageGames.gallery.empty") }}
    </p>

    <ul v-else class="gallery-grid">
      <li
        v-for="art in items"
        :key="art.caid"
        class="gallery-card"
      >
        <router-link
          :to="`/cottage/games/canvas/gallery/${art.caid}`"
          class="gallery-card-link"
        >
          <img
            :src="art.thumb_data_url"
            :alt="art.title || t('cottageGames.gallery.untitled')"
            class="gallery-thumb"
          />
          <div class="gallery-meta">
            <p class="gallery-title">{{ art.title || t("cottageGames.gallery.untitled") }}</p>
            <p class="gallery-info">
              <span>{{ formatDate(art.created_at) }}</span>
              <span>·</span>
              <span>{{ art.stroke_count }} {{ t("cottageGames.gallery.strokes") }}</span>
              <span>·</span>
              <span>{{ art.collaborators.length }} {{ t("cottageGames.gallery.collaborators") }}</span>
            </p>
            <p class="gallery-collaborators">
              <span
                v-for="c in art.collaborators"
                :key="c.user_uid"
                class="collaborator-chip"
                :title="t('cottageGames.gallery.contributorTitle', { name: c.nickname, n: c.stroke_count })"
              >{{ initialOf(c.nickname) }}</span>
            </p>
          </div>
        </router-link>
        <button
          class="gallery-delete"
          type="button"
          :aria-label="t('cottageGames.gallery.deleteAria')"
          :disabled="deletingCaid === art.caid"
          @click.stop.prevent="confirmDelete(art)"
        >×</button>
      </li>
    </ul>

    <div v-if="hasNext || page > 1" class="gallery-pager">
      <button
        type="button"
        class="ghost-btn"
        :disabled="page <= 1 || loading"
        @click="goPage(page - 1)"
      >{{ t("cottageGames.gallery.prevPage") }}</button>
      <span class="pager-info">{{ t("cottageGames.gallery.pageInfo", { page: page, total: Math.max(page, totalPages) }) }}</span>
      <button
        type="button"
        class="ghost-btn"
        :disabled="!hasNext || loading"
        @click="goPage(page + 1)"
      >{{ t("cottageGames.gallery.nextPage") }}</button>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { deleteCanvasArtwork, fetchCanvasArtworks } from "../../../../lib/api";
import { parseError } from "../../../../utils/helpers";
import { t } from "../../../../locales";

const showMessage = inject("showMessage", () => {});

const items = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);
const errorMsg = ref("");
const deletingCaid = ref("");

const hasNext = computed(() => page.value * pageSize < total.value);
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

function initialOf(name) {
  const s = String(name || "").trim();
  return s ? s.charAt(0).toUpperCase() : "·";
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("zh-CN", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function load() {
  loading.value = true;
  errorMsg.value = "";
  try {
    const data = await fetchCanvasArtworks(page.value, pageSize);
    items.value = data.items || [];
    total.value = data.total || 0;
  } catch (err) {
    errorMsg.value = parseError(err);
  } finally {
    loading.value = false;
  }
}

function goPage(p) {
  if (p < 1) return;
  page.value = p;
  void load();
}

async function confirmDelete(art) {
  if (!window.confirm(t("cottageGames.gallery.confirmDelete", { title: art.title || t("cottageGames.gallery.untitled") }))) {
    return;
  }
  deletingCaid.value = art.caid;
  try {
    await deleteCanvasArtwork(art.caid);
    showMessage(t("cottageGames.gallery.deletedToast"));
    await load();
  } catch (err) {
    showMessage(parseError(err));
  } finally {
    deletingCaid.value = "";
  }
}

onMounted(load);
</script>

<style scoped>
.canvas-gallery { display: grid; gap: 1rem; }
.gallery-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}
.gallery-header h2 {
  margin: 0;
  font-size: 1.3rem;
  color: #2f3754;
}
.gallery-header .hint {
  margin: 0.4rem 0 0;
  color: var(--text-soft);
  font-size: 0.85rem;
}
.gallery-actions { display: flex; gap: 0.5rem; }
.ghost-btn {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.8);
  color: #3d4665;
  font-size: 0.82rem;
  text-decoration: none;
  cursor: pointer;
}
.ghost-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.state-text, .empty, .error-text {
  margin: 0;
  padding: 1rem;
  text-align: center;
  border-radius: 12px;
  background: rgba(148, 163, 184, 0.1);
  color: var(--text-soft);
  font-size: 0.9rem;
}
.error-text {
  background: rgba(252, 165, 165, 0.18);
  color: #b91c1c;
}
.gallery-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.85rem;
}
.gallery-card {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 6px 18px rgb(99 102 241 / 0.08);
  border: 1px solid rgba(148, 163, 184, 0.18);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.gallery-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgb(99 102, 241 / 0.16);
}
.gallery-card-link {
  display: block;
  text-decoration: none;
  color: inherit;
}
.gallery-thumb {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: contain;
  background: #fff;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}
.gallery-meta {
  padding: 0.6rem 0.75rem 0.75rem;
  display: grid;
  gap: 0.3rem;
}
.gallery-title {
  margin: 0;
  font-size: 0.92rem;
  color: #2f3754;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gallery-info {
  margin: 0;
  font-size: 0.74rem;
  color: var(--text-soft);
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}
.gallery-collaborators {
  margin: 0.15rem 0 0;
  display: flex;
  gap: 0.3rem;
}
.collaborator-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #818cf8, #ec4899);
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
}
.gallery-delete {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: rgba(15, 23, 42, 0.55);
  color: #fff;
  font-size: 1.05rem;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease, background 0.15s ease;
}
.gallery-card:hover .gallery-delete { opacity: 1; }
.gallery-delete:hover { background: rgba(220, 38, 38, 0.85); }
.gallery-delete:disabled { opacity: 0.4; cursor: not-allowed; }
.gallery-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 0.5rem 0 1rem;
}
.pager-info { color: var(--text-soft); font-size: 0.82rem; }

@media (max-width: 640px) {
  .gallery-grid { grid-template-columns: 1fr 1fr; }
}
</style>
