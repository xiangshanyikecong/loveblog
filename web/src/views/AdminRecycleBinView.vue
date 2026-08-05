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
  <div class="admin-panel recycle-bin-panel">
    <div class="panel-header">
      <div>
        <h2>{{ t("adminRecycleBin.title") }}</h2>
        <p class="panel-subtitle">{{ t("adminRecycleBin.subtitle") }}</p>
      </div>
      <div class="header-actions">
        <button class="btn-danger-outline" @click="confirmClearAll">{{ t("adminRecycleBin.clearAll") }}</button>
        <button class="btn-secondary" @click="loadItems">{{ t("adminRecycleBin.refresh") }}</button>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters">
      <label>
        <span>{{ t("adminRecycleBin.typeFilter") }}</span>
        <select v-model="filterType" @change="loadItems">
          <option value="">{{ t("adminRecycleBin.all") }}</option>
          <option value="article">{{ t("adminRecycleBin.typeArticle") }}</option>
          <option value="album">{{ t("adminRecycleBin.typeAlbum") }}</option>
          <option value="event">{{ t("adminRecycleBin.typeEvent") }}</option>
          <option value="moment">{{ t("adminRecycleBin.typeMoment") }}</option>
          <option value="message">{{ t("adminRecycleBin.typeMessage") }}</option>
        </select>
      </label>
    </div>

    <div v-if="loading" class="loading-state">{{ t("adminRecycleBin.loading") }}</div>

    <div v-else class="table-wrapper">
      <table class="recycle-table">
        <thead>
          <tr>
            <th>{{ t("adminRecycleBin.colType") }}</th>
            <th>{{ t("adminRecycleBin.colContent") }}</th>
            <th>{{ t("adminRecycleBin.colDeletedAt") }}</th>
            <th>{{ t("adminRecycleBin.colActions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="items.length === 0">
            <td colspan="4" class="empty-row">{{ t("adminRecycleBin.empty") }}</td>
          </tr>
          <tr v-for="item in items" :key="item.type + item.id">
            <td><span class="type-badge">{{ typeLabel(item.type) }}</span></td>
            <td>
              <div class="content-cell">
                <strong>{{ item.title }}</strong>
                <span class="id-text">{{ item.id }}</span>
              </div>
            </td>
            <td>{{ formatDate(item.deleted_at) }}</td>
            <td>
              <button class="btn-small btn-restore" @click="restoreItem(item)">{{ t("adminRecycleBin.restore") }}</button>
              <button class="btn-small btn-delete" @click="confirmDeleteItem(item)">{{ t("adminRecycleBin.permanentDelete") }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Confirm Modal -->
    <div v-if="showConfirmModal" class="modal-overlay">
      <div class="modal-content">
        <h3>{{ confirmTitle }}</h3>
        <p>{{ confirmMessage }}</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showConfirmModal = false">{{ t("adminRecycleBin.cancel") }}</button>
          <button class="btn-danger" @click="executeConfirm">{{ t("adminRecycleBin.confirm") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, inject } from "vue";
import { fetchRecycleBin, restoreRecycleBinItem, deleteRecycleBinItem, clearRecycleBin } from "../lib/api";
import { t } from "../locales";
import { parseError } from "../utils/helpers";

const showMessage = inject("showMessage");
const items = ref([]);
const loading = ref(false);
const filterType = ref("");

// Confirm modal state
const showConfirmModal = ref(false);
const confirmTitle = ref("");
const confirmMessage = ref("");
let confirmCallback = null;

function typeLabel(type) {
  const map = {
    article: t("adminRecycleBin.typeArticle"),
    album: t("adminRecycleBin.typeAlbum"),
    event: t("adminRecycleBin.typeEvent"),
    moment: t("adminRecycleBin.typeMoment"),
    message: t("adminRecycleBin.typeMessage")
  };
  return map[type] || type;
}

function formatDate(dateStr) {
  if (!dateStr) return "-";
  return new Date(dateStr).toLocaleString("zh-CN");
}

function loadItems() {
  loading.value = true;
  const params = filterType.value ? { type: filterType.value } : {};
  fetchRecycleBin(params)
    .then(data => {
      items.value = data.items || [];
    })
    .catch(err => showMessage(parseError(err)))
    .finally(() => {
      loading.value = false;
    });
}

function restoreItem(item) {
  restoreRecycleBinItem(item.type, item.id)
    .then(() => {
      showMessage(t("adminRecycleBin.restoreSuccess"));
      loadItems();
    })
    .catch(err => showMessage(parseError(err)));
}

function confirmDeleteItem(item) {
  confirmTitle.value = t("adminRecycleBin.confirmDeleteTitle");
  confirmMessage.value = t("adminRecycleBin.confirmDeleteMessage", { type: typeLabel(item.type) });
  confirmCallback = () => {
    deleteRecycleBinItem(item.type, item.id)
      .then(() => {
        showMessage(t("adminRecycleBin.deleted"));
        showConfirmModal.value = false;
        loadItems();
      })
      .catch(err => showMessage(parseError(err)));
  };
  showConfirmModal.value = true;
}

function confirmClearAll() {
  const filterVal = filterType.value;
  confirmTitle.value = t("adminRecycleBin.confirmClearTitle");
  confirmMessage.value = filterVal
    ? t("adminRecycleBin.confirmClearTyped", { type: typeLabel(filterVal) })
    : t("adminRecycleBin.confirmClearAll");

  confirmCallback = () => {
    clearRecycleBin(filterVal || null)
      .then(() => {
        showMessage(t("adminRecycleBin.cleared"));
        showConfirmModal.value = false;
        loadItems();
      })
      .catch(err => showMessage(parseError(err)));
  };
  showConfirmModal.value = true;
}

function executeConfirm() {
  if (confirmCallback) confirmCallback();
}

onMounted(() => {
  loadItems();
});
</script>

<style scoped>
.admin-panel { background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); padding: 1.5rem; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.panel-header h2 { margin: 0; font-size: 1.25rem; color: #1e293b; }
.panel-subtitle { margin: 0.25rem 0 0; font-size: 0.875rem; color: #64748b; }
.header-actions { display: flex; gap: 0.5rem; }

.filters { margin-bottom: 1.5rem; display: flex; gap: 1rem; }
.filters label { display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem; color: #475569; }
.filters select { padding: 0.4rem; border: 1px solid #cbd5e1; border-radius: 6px; }

.table-wrapper { overflow-x: auto; }
.recycle-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
.recycle-table th, .recycle-table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
.recycle-table th { background: #f8fafc; font-weight: 600; color: #475569; }

.type-badge { display: inline-block; padding: 0.15rem 0.5rem; background: #e0e7ff; color: #4338ca; border-radius: 4px; font-size: 0.75rem; }
.content-cell { display: flex; flex-direction: column; }
.content-cell strong { color: #1e293b; }
.id-text { font-size: 0.75rem; color: #94a3b8; font-family: monospace; }
.empty-row { text-align: center; padding: 2rem !important; color: #94a3b8; }

.loading-state { text-align: center; padding: 2rem; color: #64748b; }

.btn-secondary { background-color: #f1f5f9; color: #475569; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; }
.btn-secondary:hover { background-color: #e2e8f0; }
.btn-danger-outline { background: transparent; border: 1px solid #dc2626; color: #dc2626; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; }
.btn-danger-outline:hover { background: #fef2f2; }
.btn-danger { background-color: #dc2626; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; }
.btn-danger:hover { background-color: #b91c1c; }

.btn-small { padding: 0.25rem 0.5rem; border: none; border-radius: 4px; cursor: pointer; font-size: 0.75rem; margin-right: 0.25rem; }
.btn-restore { background: #dcfce7; color: #166534; }
.btn-restore:hover { background: #bbf7d0; }
.btn-delete { background: #fee2e2; color: #991b1b; }
.btn-delete:hover { background: #fecaca; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 50; }
.modal-content { background: white; padding: 2rem; border-radius: 12px; width: 100%; max-width: 400px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
.modal-content h3 { margin-top: 0; margin-bottom: 1rem; color: #1e293b; }
.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 1.5rem; }
</style>
