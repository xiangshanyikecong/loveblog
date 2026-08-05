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
      <h2>{{ t("adminArticles.title") }}</h2>
      <button class="btn-secondary" @click="loadArticles">{{ t("adminArticles.refresh") }}</button>
    </div>

    <div class="table-container">
      <table class="admin-table">
        <thead>
          <tr>
            <th>{{ t("adminArticles.colTitle") }}</th>
            <th>{{ t("adminArticles.colStatus") }}</th>
            <th>{{ t("adminArticles.colPermission") }}</th>
            <th>{{ t("adminArticles.colVersion") }}</th>
            <th>{{ t("adminArticles.colCreatedAt") }}</th>
            <th>{{ t("adminArticles.colActions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in articles" :key="item.aid">
            <td class="font-medium">{{ item.title }}</td>
            <td>
              <span :class="['status-badge', item.status === 'Published' ? 'status-public' : 'status-private']">
                {{ item.status === "Published" ? t("adminArticles.published") : t("adminArticles.draft") }}
              </span>
            </td>
            <td>
              <div class="status-stack">
                <span v-if="item.visibility === 'public'" class="status-badge status-public">{{ t("adminArticles.visPublic") }}</span>
                <span v-else-if="item.visibility === 'guest_viewable'" class="status-badge status-guest">{{ t("adminArticles.visGuest") }}</span>
                <span v-else-if="item.visibility === 'partners_only'" class="status-badge status-partners">{{ t("adminArticles.visPartners") }}</span>
                <span v-else-if="item.visibility === 'private'" class="status-badge status-private">{{ t("adminArticles.visPrivate") }}</span>
                <span v-else-if="item.visibility === 'password_protected'" class="status-badge status-password">{{ t("adminArticles.visPassword") }}</span>
                <span v-if="item.partner_can_edit" class="status-badge status-info">{{ t("adminArticles.coEdit") }}</span>
                <span v-if="item.is_co_created" class="status-badge status-info" :title="t('adminArticles.coCreationTitle')">{{ t("adminArticles.coCreation") }}</span>
                <span v-for="tag in item.tags || []" :key="tag" class="status-badge status-tag">#{{ tag }}</span>
              </div>
            </td>
            <td>v{{ item.version || 1 }}</td>
            <td>{{ formatDate(item.created_at) }}</td>
            <td>
              <div class="action-buttons">
                <button class="btn-primary-text" @click="$router.push({ name: 'article-editor', params: { aid: item.aid } })">{{ t("adminArticles.editor") }}</button>
                <button class="btn-primary-text" @click="openEditModal(item)">{{ t("adminArticles.quickEdit") }}</button>
                <button class="btn-primary-text" @click="openHistory(item)">{{ t("adminArticles.history") }}</button>
                <button class="btn-danger-text" @click="handleDelete(item.aid)">{{ t("adminArticles.delete") }}</button>
              </div>
            </td>
          </tr>
          <tr v-if="!articles.length">
            <td colspan="6" class="text-center text-muted">{{ t("adminArticles.noArticles") }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showModal" class="modal-overlay">
      <div class="modal-content">
        <h3>{{ t("adminArticles.editArticle") }}</h3>
        <form class="modal-form" @submit.prevent="submitEdit">
          <label>
            {{ t("adminArticles.titleLabel") }}
            <input v-model="editForm.title" class="input" required />
          </label>
          <label>
            {{ t("adminArticles.excerptLabel") }}
            <textarea v-model="editForm.excerpt" class="input" rows="3"></textarea>
          </label>
          <label>
            {{ t("adminArticles.tagsLabel") }}
            <input v-model="editForm.tagsText" class="input" :placeholder="t('adminArticles.tagsPlaceholder')" />
          </label>
          <label>
            {{ t("adminArticles.statusLabel") }}
            <select v-model="editForm.status" class="input">
              <option value="Draft">{{ t("adminArticles.draft") }}</option>
              <option value="Published">{{ t("adminArticles.published") }}</option>
            </select>
          </label>
          <label>
            {{ t("adminArticles.visibilityLevel") }}
            <select v-model="editForm.visibility" class="input">
              <option value="public">{{ t("adminArticles.visPublicOption") }}</option>
              <option value="guest_viewable">{{ t("adminArticles.visGuestOption") }}</option>
              <option value="partners_only">{{ t("adminArticles.visPartnersOption") }}</option>
              <option value="private">{{ t("adminArticles.visPrivateOption") }}</option>
              <option value="password_protected">{{ t("adminArticles.visPasswordOption") }}</option>
            </select>
          </label>
          <label v-if="editForm.visibility === 'password_protected'">
            {{ t("adminArticles.accessPassword") }}
            <input v-model="editForm.password" type="password" class="input" :placeholder="t('adminArticles.passwordPlaceholder')" />
          </label>
          <label class="check-line">
            <input v-model="editForm.partner_can_edit" type="checkbox" />
            {{ t("adminArticles.allowPartnerEdit") }}
          </label>
          <div class="modal-actions">
            <button class="btn-secondary" type="button" @click="showModal = false">{{ t("adminArticles.cancel") }}</button>
            <button class="btn-primary" type="submit" :disabled="busy">{{ busy ? t("adminArticles.saving") : t("adminArticles.save") }}</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="historyModal" class="modal-overlay">
      <div class="modal-content history-modal">
        <div class="modal-title-row">
          <h3>{{ t("adminArticles.historyVersions") }}</h3>
          <button class="btn-secondary" @click="historyModal = false">{{ t("adminArticles.close") }}</button>
        </div>
        <p v-if="!versions.length" class="text-muted">{{ t("adminArticles.noVersions") }}</p>
        <div v-else class="version-list">
          <article v-for="item in versions" :key="item.vid" class="version-item">
            <div>
              <strong>v{{ item.version }} · {{ item.title || t("adminArticles.untitled") }}</strong>
              <p>{{ formatDate(item.created_at) }} · {{ item.actor_nickname || t("adminSecurity.system") }}</p>
              <p class="version-preview">{{ previewArticle(item.snapshot) }}</p>
            </div>
            <button class="btn-secondary" :disabled="busy" @click="rollbackVersion(item.version)">{{ t("adminArticles.rollback") }}</button>
          </article>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from "vue";
import {
  deleteArticle,
  fetchArticle,
  fetchArticles,
  fetchArticleVersions,
  patchArticle,
  rollbackArticleVersion,
} from "../lib/api";
import { confirmDialog } from "../lib/dialog";
import { t } from "../locales";
import { parseError, parseTags } from "../utils/helpers";

const showMessage = inject("showMessage");
const articles = ref([]);
const versions = ref([]);
const showModal = ref(false);
const historyModal = ref(false);
const busy = ref(false);
let currentEditId = null;
let currentHistoryId = null;

const editForm = reactive({
  title: "",
  excerpt: "",
  tagsText: "",
  status: "Draft",
  visibility: "public",
  password: "",
  partner_can_edit: false,
});

function formatDate(raw) {
  if (!raw) return "";
  return new Date(raw).toLocaleString("zh-CN", { hour12: false });
}

function previewArticle(snapshot) {
  const blocks = snapshot?.blocks || [];
  const firstText = blocks.find((block) => block.content)?.content || snapshot?.excerpt || "";
  return firstText.length > 120 ? `${firstText.slice(0, 120)}...` : firstText || t("adminArticles.noSnapshot");
}

async function loadArticles() {
  try {
    const data = await fetchArticles({ only_published: false });
    articles.value = data.items || [];
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

async function handleDelete(id) {
  if (!(await confirmDialog(t("adminArticles.confirmDelete"), { danger: true }))) return;
  try {
    await deleteArticle(id);
    showMessage?.(t("adminArticles.deleteSuccess"));
    await loadArticles();
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

async function openEditModal(item) {
  busy.value = true;
  try {
    const detail = await fetchArticle(item.aid);
    currentEditId = item.aid;
    editForm.title = detail.title || "";
    editForm.excerpt = detail.excerpt || "";
    editForm.tagsText = (detail.tags || []).join(", ");
    editForm.status = detail.status || "Draft";
    editForm.visibility = detail.visibility || "public";
    editForm.password = ""; // 不显示现有密码
    editForm.partner_can_edit = !!detail.partner_can_edit;
    showModal.value = true;
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function submitEdit() {
  busy.value = true;
  try {
    const payload = {
      title: editForm.title,
      excerpt: editForm.excerpt || null,
      tags: parseTags(editForm.tagsText),
      status: editForm.status,
      visibility: editForm.visibility,
      partner_can_edit: editForm.partner_can_edit,
    };
    
    // 只有在密码保护模式下且输入了密码时才发送密码
    if (editForm.visibility === 'password_protected' && editForm.password) {
      payload.password = editForm.password;
    }
    
    await patchArticle(currentEditId, payload);
    showMessage?.(t("adminArticles.saveSuccess"));
    showModal.value = false;
    await loadArticles();
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function openHistory(item) {
  currentHistoryId = item.aid;
  historyModal.value = true;
  busy.value = true;
  try {
    const data = await fetchArticleVersions(item.aid);
    versions.value = data.items || [];
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function rollbackVersion(version) {
  if (!(await confirmDialog(t("adminArticles.confirmRollback", { version })))) return;
  busy.value = true;
  try {
    await rollbackArticleVersion(currentHistoryId, version);
    showMessage?.(t("adminArticles.rollbackSuccess"));
    await Promise.all([loadArticles(), openHistory({ aid: currentHistoryId })]);
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    busy.value = false;
  }
}

onMounted(loadArticles);
</script>

<style scoped>
.admin-panel {
  background: white;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.06);
  padding: 1.5rem;
}

.panel-header,
.modal-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.panel-header h2,
.modal-content h3 {
  margin: 0;
  color: #1e293b;
  font-size: 1.2rem;
}

.table-container {
  overflow-x: auto;
}

.admin-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.admin-table th,
.admin-table td {
  padding: 0.9rem;
  border-bottom: 1px solid #e2e8f0;
  color: #334155;
  font-size: 0.9rem;
  vertical-align: middle;
}

.admin-table th {
  background: #f8fafc;
  color: #475569;
  font-weight: 700;
}

.font-medium {
  color: #1e293b;
  font-weight: 600;
}

.btn-secondary,
.btn-primary {
  border: none;
  border-radius: 7px;
  cursor: pointer;
  font-size: 0.86rem;
  font-weight: 600;
  padding: 0.52rem 0.88rem;
}

.btn-secondary {
  background: #f1f5f9;
  color: #475569;
}

.btn-primary {
  background: #2563eb;
  color: white;
}

.btn-primary:disabled,
.btn-secondary:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.action-buttons {
  display: flex;
  gap: 0.8rem;
  flex-wrap: wrap;
}

.btn-primary-text,
.btn-danger-text {
  background: none;
  border: none;
  cursor: pointer;
  font-weight: 600;
  padding: 0;
}

.btn-primary-text {
  color: #2563eb;
}

.btn-danger-text {
  color: #dc2626;
}

.status-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.status-badge {
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 700;
  padding: 0.22rem 0.55rem;
}

.status-public {
  background: #dcfce7;
  color: #166534;
}

.status-guest {
  background: #dbeafe;
  color: #1e40af;
}

.status-partners {
  background: #fce7f3;
  color: #9f1239;
}

.status-private {
  background: #f1f5f9;
  color: #475569;
}

.status-password {
  background: #fef3c7;
  color: #92400e;
}

.status-info {
  background: #dbeafe;
  color: #1d4ed8;
}

.status-encrypted {
  background: #fee2e2;
  color: #991b1b;
}

.status-tag {
  background: #e0f2fe;
  color: #075985;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.5);
  padding: 1rem;
}

.modal-content {
  width: min(560px, 100%);
  max-height: 86vh;
  overflow-y: auto;
  background: white;
  border-radius: 10px;
  padding: 1.5rem;
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.24);
}

.history-modal {
  width: min(760px, 100%);
}

.modal-form,
.version-list {
  display: grid;
  gap: 1rem;
}

.modal-form label {
  display: grid;
  gap: 0.35rem;
  color: #475569;
  font-size: 0.86rem;
}

.input {
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  padding: 0.7rem;
  font-size: 0.92rem;
}

.check-group,
.modal-actions {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.check-line {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #475569;
  font-size: 0.9rem;
  cursor: pointer;
}

.check-line input[type="checkbox"] {
  cursor: pointer;
}

.modal-actions {
  justify-content: flex-end;
}

.version-item {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.9rem;
  background: #f8fafc;
}

.version-item p {
  margin: 0.28rem 0 0;
  color: #64748b;
  font-size: 0.82rem;
}

.version-preview {
  white-space: pre-wrap;
}

.text-center {
  text-align: center;
}

.text-muted {
  color: #94a3b8;
}
</style>
