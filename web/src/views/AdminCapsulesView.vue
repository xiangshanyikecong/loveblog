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
      <h2>{{ t("adminCapsules.title") }}</h2>
      <button class="btn-secondary" @click="load">{{ t("adminCapsules.refresh") }}</button>
    </div>

    <div class="admin-grid">
      <div v-for="item in capsules" :key="item.uuid" class="capsule-item" :class="{'item-locked': !item.is_open}">
        <div class="item-icon">
          {{ item.is_open ? '🔓' : '🔒' }}
        </div>
        <div class="item-main">
          <div class="item-info">
            <span class="author">{{ t("adminCapsules.buriedBy", { name: item.author_nickname }) }}</span>
            <span :class="['status-badge', item.is_open ? 'status-public' : 'status-private']">
              {{ item.is_open ? t("adminCapsules.unlocked") : t("adminCapsules.sealed") }}
            </span>
          </div>
          <div class="item-dates">
            <div class="date-tag">
              <span class="label">{{ t("adminCapsules.openAt") }}</span>
              <span class="value">{{ new Date(item.open_at).toLocaleDateString() }}</span>
            </div>
            <div class="date-tag">
              <span class="label">{{ t("adminCapsules.createdAt") }}</span>
              <span class="value">{{ new Date(item.created_at).toLocaleDateString() }}</span>
            </div>
          </div>
        </div>
        <div class="item-actions">
          <button class="btn-danger-text" @click="handleDelete(item.uuid)">{{ t("adminCapsules.destroy") }}</button>
        </div>
      </div>

      <div v-if="!capsules.length" class="empty-state">
        <p>{{ t("adminCapsules.noCapsules") }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, inject } from "vue";
import { fetchCapsules, deleteCapsule } from "../lib/api";
import { confirmDialog } from "../lib/dialog";
import { t } from "../locales";
import { parseError } from "../utils/helpers";

const showMessage = inject("showMessage");
const capsules = ref([]);

async function load() {
  try {
    capsules.value = await fetchCapsules();
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function handleDelete(id) {
  if (!(await confirmDialog(t("adminCapsules.confirmDelete"), { danger: true }))) return;
  try {
    await deleteCapsule(id);
    showMessage(t("adminCapsules.destroyed"));
    load();
  } catch (error) {
    showMessage(parseError(error));
  }
}

onMounted(load);
</script>

<style scoped>
.admin-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.capsule-item {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 1.25rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  transition: all 0.2s;
}
.capsule-item:hover {
  border-color: #cbd5e1;
  background: #f1f5f9;
}
.item-locked {
  border-left: 4px solid #94a3b8;
}
.item-icon {
  font-size: 1.5rem;
  width: 48px;
  height: 48px;
  background: white;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.item-main {
  flex: 1;
}
.item-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.5rem;
}
.author {
  font-size: 0.95rem;
  color: #334155;
}
.item-dates {
  display: flex;
  gap: 1.5rem;
}
.date-tag {
  display: flex;
  flex-direction: column;
}
.date-tag .label {
  font-size: 0.75rem;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.date-tag .value {
  font-size: 0.85rem;
  color: #475569;
  font-weight: 500;
}
.item-actions {
  flex-shrink: 0;
}
.empty-state {
  text-align: center;
  padding: 3rem;
  color: #94a3b8;
}
</style>
