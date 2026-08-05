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
      <h2>{{ t("adminMessages.title") }}</h2>
      <button class="btn-secondary" @click="loadMessages">{{ t("adminMessages.refresh") }}</button>
    </div>

    <div class="table-container">
      <table class="admin-table">
        <thead>
          <tr>
            <th>{{ t("adminMessages.colContent") }}</th>
            <th>{{ t("adminMessages.colAuthor") }}</th>
            <th>{{ t("adminMessages.colVisibility") }}</th>
            <th>{{ t("adminMessages.colVersion") }}</th>
            <th>{{ t("adminMessages.colTime") }}</th>
            <th>{{ t("adminMessages.colActions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in messages" :key="item.msg_id">
            <td class="td-content">{{ item.content }}</td>
            <td>{{ item.author_nickname || item.visitor_name || t("adminMessages.anonymous") }}</td>
            <td>
              <span :class="['status-badge', item.is_public ? 'status-public' : 'status-private']">
                {{ item.is_public ? t("adminMessages.public") : t("adminMessages.private") }}
              </span>
            </td>
            <td>v{{ item.version || 1 }}</td>
            <td>{{ formatDate(item.created_at) }}</td>
            <td>
              <div class="action-buttons">
                <button class="btn-primary-text" @click="openEdit(item)">{{ t("adminMessages.edit") }}</button>
                <button class="btn-primary-text" @click="openHistory(item)">{{ t("adminMessages.history") }}</button>
                <button class="btn-danger-text" @click="handleDelete(item.msg_id)">{{ t("adminMessages.delete") }}</button>
              </div>
            </td>
          </tr>
          <tr v-if="!messages.length">
            <td colspan="6" class="text-center text-muted">{{ t("adminMessages.noMessages") }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="editModal" class="modal-overlay">
      <div class="modal-content">
        <h3>{{ t("adminMessages.editMessage") }}</h3>
        <form class="modal-form" @submit.prevent="submitEdit">
          <label>
            {{ t("adminMessages.contentLabel") }}
            <textarea v-model="editForm.content" class="input" rows="5" required></textarea>
          </label>
          <label>
            {{ t("adminMessages.tagsLabel") }}
            <input v-model="editForm.tagsText" class="input" :placeholder="t('adminMessages.tagsPlaceholder')" />
          </label>
          <label class="check-line">
            <input v-model="editForm.is_public" type="checkbox" />
            {{ t("adminMessages.publicMessage") }}
          </label>
          <div class="modal-actions">
            <button class="btn-secondary" type="button" @click="editModal = false">{{ t("adminMessages.cancel") }}</button>
            <button class="btn-primary" type="submit" :disabled="busy">{{ busy ? t("adminMessages.saving") : t("adminMessages.save") }}</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="historyModal" class="modal-overlay">
      <div class="modal-content history-modal">
        <div class="modal-title-row">
          <h3>{{ t("adminMessages.messageHistory") }}</h3>
          <button class="btn-secondary" @click="historyModal = false">{{ t("adminMessages.close") }}</button>
        </div>
        <p v-if="!versions.length" class="text-muted">{{ t("adminMessages.noVersions") }}</p>
        <div v-else class="version-list">
          <article v-for="item in versions" :key="item.vid" class="version-item">
            <div>
              <strong>v{{ item.version }} · {{ item.snapshot.is_public ? t("adminMessages.public") : t("adminMessages.private") }}</strong>
              <p>{{ formatDate(item.created_at) }} · {{ item.actor_nickname || t("adminSecurity.system") }}</p>
              <p class="version-preview">{{ item.snapshot.content }}</p>
            </div>
            <button class="btn-secondary" :disabled="busy" @click="rollbackVersion(item.version)">{{ t("adminMessages.rollback") }}</button>
          </article>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from "vue";
import {
  deleteMessage,
  fetchMessageVersions,
  fetchMessages,
  rollbackMessageVersion,
  updateMessage,
} from "../lib/api";
import { confirmDialog } from "../lib/dialog";
import { t } from "../locales";
import { parseError, parseTags } from "../utils/helpers";

const showMessage = inject("showMessage");
const messages = ref([]);
const versions = ref([]);
const editModal = ref(false);
const historyModal = ref(false);
const busy = ref(false);
let currentMessageId = null;

const editForm = reactive({
  content: "",
  tagsText: "",
  is_public: true,
});

function formatDate(raw) {
  if (!raw) return "";
  return new Date(raw).toLocaleString("zh-CN", { hour12: false });
}

async function loadMessages() {
  try {
    const data = await fetchMessages({ include_private: true });
    messages.value = data.items || [];
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

function openEdit(item) {
  currentMessageId = item.msg_id;
  editForm.content = item.content || "";
  editForm.tagsText = (item.tags || []).join(", ");
  editForm.is_public = !!item.is_public;
  editModal.value = true;
}

async function submitEdit() {
  busy.value = true;
  try {
    await updateMessage(currentMessageId, {
      content: editForm.content,
      tags: parseTags(editForm.tagsText),
      is_public: editForm.is_public,
    });
    showMessage?.(t("adminMessages.messageSaved"));
    editModal.value = false;
    await loadMessages();
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function openHistory(item) {
  currentMessageId = item.msg_id;
  historyModal.value = true;
  busy.value = true;
  try {
    const data = await fetchMessageVersions(item.msg_id);
    versions.value = data.items || [];
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function rollbackVersion(version) {
  if (!(await confirmDialog(t("adminMessages.confirmRollback", { version })))) return;
  busy.value = true;
  try {
    await rollbackMessageVersion(currentMessageId, version);
    showMessage?.(t("adminMessages.rollbackSuccess"));
    await loadMessages();
    await openHistory({ msg_id: currentMessageId });
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function handleDelete(id) {
  if (!(await confirmDialog(t("adminMessages.confirmDelete"), { danger: true }))) return;
  try {
    await deleteMessage(id);
    showMessage?.(t("adminMessages.deleteSuccess"));
    await loadMessages();
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

onMounted(loadMessages);
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

.td-content {
  max-width: 360px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

.status-private {
  background: #fef3c7;
  color: #92400e;
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

.check-line {
  grid-template-columns: auto 1fr;
  align-items: center;
}

.input {
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  padding: 0.7rem;
  font-size: 0.92rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
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
