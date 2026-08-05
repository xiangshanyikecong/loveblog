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
  <div class="admin-panel">
    <div class="panel-header">
      <h2>{{ t("adminTimeline.title") }}</h2>
      <button class="btn-secondary" @click="load">{{ t("adminTimeline.refresh") }}</button>
    </div>

    <div class="admin-grid">
      <div v-for="item in moments" :key="item.mid" class="admin-card">
        <div class="card-meta">
          <div class="user-info">
            <span class="user-avatar">{{ item.author_nickname[0] }}</span>
            <span class="user-name">{{ item.author_nickname }}</span>
          </div>
          <span class="timestamp">{{ new Date(item.timestamp).toLocaleString() }}</span>
        </div>
        
        <div class="card-content">
          <p class="content-text">{{ item.content }}</p>
          <div v-if="item.media_urls?.length" class="thumbnail-strip">
            <img v-for="(url, idx) in item.media_urls" :key="idx" :src="resolveAssetUrl(url)" class="thumbnail" />
          </div>
          <div v-if="item.location" class="location">
            📍 {{ item.location }}
          </div>
        </div>

        <div class="card-footer">
          <div class="stats">
            <span>{{ t("adminTimeline.comments", { n: item.comments?.length || 0 }) }}</span>
          </div>
          <button class="btn-danger-text" @click="handleDelete(item.mid)">{{ t("adminTimeline.deleteRecord") }}</button>
        </div>
      </div>

      <div v-if="!moments.length" class="empty-state">
        <p>{{ t("adminTimeline.noMoments") }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, inject } from "vue";
import { fetchTimeline, deleteMoment, resolveAssetUrl } from "../lib/api";
import { confirmDialog } from "../lib/dialog";
import { t } from "../locales";
import { parseError } from "../utils/helpers";

const showMessage = inject("showMessage");
const moments = ref([]);

async function load() {
  try {
    const data = await fetchTimeline({ page_size: 50 });
    moments.value = data.items || [];
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function handleDelete(id) {
  if (!(await confirmDialog(t("adminTimeline.confirmDelete"), { danger: true }))) return;
  try {
    await deleteMoment(id);
    showMessage(t("adminTimeline.deleted"));
    load();
  } catch (error) {
    showMessage(parseError(error));
  }
}

onMounted(load);
</script>

<style scoped>
.admin-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.5rem;
}
.admin-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.25rem;
  transition: all 0.2s;
}
.admin-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
}
.card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.user-avatar {
  width: 32px;
  height: 32px;
  background: #e2e8f0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: #64748b;
  font-size: 0.8rem;
}
.user-name {
  font-weight: 600;
  color: #1e293b;
  font-size: 0.9rem;
}
.timestamp {
  font-size: 0.8rem;
  color: #94a3b8;
}
.card-content {
  margin-bottom: 1rem;
}
.content-text {
  font-size: 0.95rem;
  line-height: 1.6;
  color: #334155;
  margin: 0 0 0.75rem;
}
.thumbnail-strip {
  display: flex;
  gap: 0.5rem;
  overflow-x: auto;
  margin-bottom: 0.75rem;
}
.thumbnail {
  width: 60px;
  height: 60px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}
.location {
  font-size: 0.8rem;
  color: #64748b;
}
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}
.stats {
  font-size: 0.85rem;
  color: #64748b;
}
.btn-danger-text {
  color: #ef4444;
  background: none;
  border: none;
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
}
.empty-state {
  text-align: center;
  padding: 3rem;
  color: #94a3b8;
}
</style>
