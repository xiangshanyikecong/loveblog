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
      <h2>{{ t("adminAlbums.title") }}</h2>
      <button class="btn-secondary" @click="loadAlbums">{{ t("adminAlbums.refresh") }}</button>
    </div>

    <div class="table-container">
      <table class="admin-table">
        <thead>
          <tr>
            <th>{{ t("adminAlbums.colCover") }}</th>
            <th>{{ t("adminAlbums.colTitle") }}</th>
            <th>{{ t("adminAlbums.colDescription") }}</th>
            <th>{{ t("adminAlbums.colStatus") }}</th>
            <th>{{ t("adminAlbums.colActions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in albums" :key="item.alb_id">
            <td>
              <img v-if="item.cover_url" :src="resolveAssetUrl(item.cover_url)" class="album-thumb" />
              <div v-else class="album-thumb-placeholder">{{ t("adminAlbums.noCover") }}</div>
            </td>
            <td>{{ item.title }}</td>
            <td class="td-content">{{ item.description || '-' }}</td>
            <td>
              <div class="status-stack">
                <span v-if="item.visibility === 'public'" class="status-badge status-public">{{ t("adminAlbums.visPublic") }}</span>
                <span v-else-if="item.visibility === 'guest_viewable'" class="status-badge status-guest">{{ t("adminAlbums.visGuest") }}</span>
                <span v-else-if="item.visibility === 'partners_only'" class="status-badge status-partners">{{ t("adminAlbums.visPartners") }}</span>
                <span v-else-if="item.visibility === 'private'" class="status-badge status-private">{{ t("adminAlbums.visPrivate") }}</span>
                <span v-else-if="item.visibility === 'password_protected'" class="status-badge status-password">{{ t("adminAlbums.visPassword") }}</span>
                <span v-for="tag in item.tags || []" :key="tag" class="status-badge status-tag">#{{ tag }}</span>
              </div>
            </td>
            <td>
              <div class="action-buttons">
                <button class="btn-primary-text" @click="openEditModal(item)">{{ t("adminAlbums.edit") }}</button>
                <button class="btn-danger-text" @click="handleDelete(item.alb_id)">{{ t("adminAlbums.delete") }}</button>
              </div>
            </td>
          </tr>
          <tr v-if="!albums.length">
            <td colspan="5" class="text-center text-muted">{{ t("adminAlbums.noAlbums") }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Edit Modal -->
    <div v-if="showModal" class="modal-overlay">
      <div class="modal-content">
        <h3>{{ t("adminAlbums.editAlbum") }}</h3>
        <form class="modal-form" @submit.prevent="submitEdit">
          <div class="form-group">
            <label>{{ t("adminAlbums.titleLabel") }}</label>
            <input v-model="editForm.title" required class="input" />
          </div>
          <div class="form-group">
            <label>{{ t("adminAlbums.descriptionLabel") }}</label>
            <textarea v-model="editForm.description" class="input"></textarea>
          </div>
          <div class="form-group">
            <label>{{ t("adminAlbums.coverUrlLabel") }}</label>
            <input v-model="editForm.cover_url" class="input" />
          </div>
          <div class="form-group">
            <label>{{ t("adminAlbums.tagsLabel") }}</label>
            <input v-model="editForm.tagsText" class="input" :placeholder="t('adminAlbums.tagsPlaceholder')" />
          </div>
          <div class="form-group">
            <label>{{ t("adminAlbums.visibilityLevel") }}</label>
            <select v-model="editForm.visibility" class="input">
              <option value="public">{{ t("adminAlbums.visPublicOption") }}</option>
              <option value="guest_viewable">{{ t("adminAlbums.visGuestOption") }}</option>
              <option value="partners_only">{{ t("adminAlbums.visPartnersOption") }}</option>
              <option value="private">{{ t("adminAlbums.visPrivateOption") }}</option>
              <option value="password_protected">{{ t("adminAlbums.visPasswordOption") }}</option>
            </select>
          </div>
          <div v-if="editForm.visibility === 'password_protected'" class="form-group">
            <label>{{ t("adminAlbums.accessPassword") }}</label>
            <input v-model="editForm.password" type="password" class="input" :placeholder="t('adminAlbums.passwordPlaceholder')" />
          </div>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showModal = false">{{ t("adminAlbums.cancel") }}</button>
            <button type="submit" class="btn-primary" :disabled="busy">{{ t("adminAlbums.save") }}</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive, inject } from "vue";
import { fetchAlbums, deleteAlbum, patchAlbum, fetchAlbum, resolveAssetUrl } from "../lib/api";
import { confirmDialog } from "../lib/dialog";
import { t } from "../locales";
import { parseError, parseTags } from "../utils/helpers";

const showMessage = inject("showMessage");
const albums = ref([]);

const showModal = ref(false);
const busy = ref(false);
let currentEditId = null;

const editForm = reactive({
  title: "",
  description: "",
  cover_url: "",
  tagsText: "",
  visibility: "public",
  password: ""
});

async function loadAlbums() {
  try {
    const data = await fetchAlbums();
    albums.value = data.items || [];
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function handleDelete(id) {
  if (!(await confirmDialog(t("adminAlbums.confirmDelete"), { danger: true }))) return;
  try {
    await deleteAlbum(id);
    showMessage(t("adminAlbums.deleteSuccess"));
    loadAlbums();
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function openEditModal(item) {
  busy.value = true;
  try {
    const detail = await fetchAlbum(item.alb_id);
    currentEditId = item.alb_id;
    editForm.title = detail.title || "";
    editForm.description = detail.description || "";
    editForm.cover_url = detail.cover_url || "";
    editForm.tagsText = (detail.tags || []).join(", ");
    editForm.visibility = detail.visibility || "public";
    editForm.password = ""; // 不显示现有密码
    showModal.value = true;
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function submitEdit() {
  busy.value = true;
  try {
    const payload = {};
    if (editForm.title !== undefined) payload.title = editForm.title;
    if (editForm.description !== undefined) payload.description = editForm.description || null;
    if (editForm.cover_url !== undefined) payload.cover_url = editForm.cover_url || null;
    payload.tags = parseTags(editForm.tagsText);
    payload.visibility = editForm.visibility;
    
    // 只有在密码保护模式下且输入了密码时才发送密码
    if (editForm.visibility === 'password_protected' && editForm.password) {
      payload.password = editForm.password;
    }
    
    await patchAlbum(currentEditId, payload);
    showMessage(t("adminAlbums.saveSuccess"));
    showModal.value = false;
    loadAlbums();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  loadAlbums();
});
</script>

<style scoped>
/* 共享样式可以抽取，这里为独立视图保留 */
.admin-panel {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  padding: 1.5rem;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
.panel-header h2 { margin: 0; font-size: 1.25rem; color: #1e293b; }
.table-container { overflow-x: auto; }
.admin-table { width: 100%; border-collapse: collapse; text-align: left; }
.admin-table th, .admin-table td { padding: 1rem; border-bottom: 1px solid #e2e8f0; }
.admin-table th { background-color: #f8fafc; font-weight: 600; color: #475569; font-size: 0.875rem; }
.admin-table td { color: #334155; font-size: 0.9rem; vertical-align: middle; }
.td-content { max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.btn-secondary { background-color: #f1f5f9; color: #475569; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; font-weight: 500; }
.btn-secondary:hover { background-color: #e2e8f0; }
.btn-primary { background-color: #3b82f6; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; font-weight: 500; }
.btn-primary:hover { background-color: #2563eb; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.action-buttons { display: flex; gap: 1rem; }
.btn-primary-text { color: #3b82f6; background: none; border: none; cursor: pointer; font-weight: 500; padding: 0; }
.btn-primary-text:hover { text-decoration: underline; }
.btn-danger-text { color: #ef4444; background: none; border: none; cursor: pointer; font-weight: 500; padding: 0; }
.btn-danger-text:hover { text-decoration: underline; }

.status-stack { display: flex; flex-direction: column; gap: 0.25rem; align-items: flex-start; }
.status-badge { padding: 0.25rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 500; }
.status-public { background-color: #d1fae5; color: #065f46; }
.status-guest { background-color: #dbeafe; color: #1e40af; }
.status-partners { background-color: #fce7f3; color: #9f1239; }
.status-private { background-color: #fef3c7; color: #92400e; }
.status-password { background-color: #fef3c7; color: #92400e; }
.status-encrypted { background-color: #fee2e2; color: #991b1b; }
.status-tag { background-color: #e0f2fe; color: #075985; }

.album-thumb { width: 60px; height: 60px; object-fit: cover; border-radius: 8px; border: 1px solid #e2e8f0; }
.album-thumb-placeholder { width: 60px; height: 60px; border-radius: 8px; background: #f1f5f9; color: #94a3b8; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; }

.text-center { text-align: center; }
.text-muted { color: #94a3b8; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 50; }
.modal-content { background: white; padding: 2rem; border-radius: 12px; width: 100%; max-width: 500px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
.modal-content h3 { margin-top: 0; margin-bottom: 1.5rem; color: #1e293b; }
.modal-form { display: flex; flex-direction: column; gap: 1rem; }
.form-group { display: flex; flex-direction: column; gap: 0.5rem; }
.form-group label { font-size: 0.875rem; font-weight: 500; color: #475569; }
.input { padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.9rem; outline: none; }
.input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.2); }
.check-group { display: flex; gap: 1.5rem; font-size: 0.875rem; color: #475569; }
.check-group label { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; }
.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 1rem; }
</style>
