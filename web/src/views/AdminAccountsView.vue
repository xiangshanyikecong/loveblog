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
      <div class="tab-nav">
        <button
          :class="['tab-btn', { active: activeTab === 'partners' }]"
          @click="activeTab = 'partners'"
        >
          {{ t("adminAccounts.partnersTab") }}
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'visitors' }]"
          @click="activeTab = 'visitors'"
        >
          {{ t("adminAccounts.visitorsTab") }}
        </button>
      </div>
      <button class="btn-secondary" @click="refresh">
        {{ activeTab === 'partners' ? t("adminAccounts.refreshPartners") : t("adminAccounts.refreshVisitors") }}
      </button>
    </div>

    <!-- 伴侣账号管理 -->
    <div v-if="activeTab === 'partners'" class="accounts-section">
      <div class="accounts-grid">
        <div v-for="partner in partners" :key="partner.uid" class="account-card">
          <div class="account-info">
            <div class="account-avatar">
              {{ partner.nickname.charAt(0).toUpperCase() }}
            </div>
            <div>
              <h3>{{ partner.nickname }}</h3>
              <p class="account-meta">{{ t("adminAccounts.usernameLabel") }}: {{ partner.username }}</p>
              <span class="role-badge">{{ partner.role === 'PartnerA' ? t("adminAccounts.partnerA") : t("adminAccounts.partnerB") }}</span>
            </div>
          </div>
          <button class="btn-primary" @click="openEditPartnerModal(partner)">{{ t("adminAccounts.editPasswordProfile") }}</button>
        </div>

        <!-- 添加缺失的伴侣账号（部署初期通常只有伴侣 A） -->
        <div v-if="missingPartnerRole" class="account-card account-card--add" @click="openAddPartnerModal">
          <div class="add-partner-inner">
            <div class="add-partner-plus">＋</div>
            <h3>{{ t("adminAccounts.addPartner", { label: missingPartnerLabel }) }}</h3>
            <p class="account-meta">{{ t("adminAccounts.addPartnerDesc") }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 访客列表管理 -->
    <div v-if="activeTab === 'visitors'" class="visitors-section">
      <!-- 筛选器 -->
      <div class="filter-bar">
        <select v-model="visitorFilters.sso_source" class="filter-select" @change="loadVisitors">
          <option value="">{{ t("adminAccounts.allSources") }}</option>
          <option value="hub">Hub</option>
          <option value="center">Center</option>
        </select>
        <select v-model="visitorFilters.permission_status" class="filter-select" @change="loadVisitors">
          <option value="">{{ t("adminAccounts.allStatus") }}</option>
          <option value="active">{{ t("adminAccounts.statusActive") }}</option>
          <option value="limited">{{ t("adminAccounts.statusLimited") }}</option>
          <option value="banned">{{ t("adminAccounts.statusBanned") }}</option>
        </select>
        <label class="checkbox-label">
          <input v-model="visitorFilters.is_banned" type="checkbox" @change="loadVisitors" />
          {{ t("adminAccounts.onlyBanned") }}
        </label>
      </div>

      <!-- 访客列表 -->
      <div class="visitors-table-wrapper">
        <table class="visitors-table">
          <thead>
            <tr>
              <th>{{ t("adminAccounts.avatar") }}</th>
              <th>{{ t("adminAccounts.nickname") }}</th>
              <th>{{ t("adminAccounts.username") }}</th>
              <th>{{ t("adminAccounts.ssoSource") }}</th>
              <th>{{ t("adminAccounts.lastLogin") }}</th>
              <th>{{ t("adminAccounts.permissionStatus") }}</th>
              <th>{{ t("adminAccounts.ban") }}</th>
              <th>{{ t("adminAccounts.remark") }}</th>
              <th>{{ t("adminAccounts.syncRecord") }}</th>
              <th>{{ t("adminAccounts.actions") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="visitor in visitors" :key="visitor.uid">
              <td>
                <div class="visitor-avatar">
                  {{ visitor.nickname.charAt(0).toUpperCase() }}
                </div>
              </td>
              <td>{{ visitor.nickname }}</td>
              <td>{{ visitor.username }}</td>
              <td>
                <span class="source-badge">{{ visitor.sso_source || t("adminAccounts.localSource") }}</span>
              </td>
              <td>{{ formatDate(visitor.last_login_at) }}</td>
              <td>
                <span :class="['status-badge', visitor.permission_status]">
                  {{ statusText(visitor.permission_status) }}
                </span>
              </td>
              <td>
                <span :class="['ban-indicator', { banned: visitor.is_banned }]">
                  {{ visitor.is_banned ? t("adminAccounts.yes") : t("adminAccounts.no") }}
                </span>
              </td>
              <td class="remark-cell">
                <span :title="visitor.remark">{{ visitor.remark || '-' }}</span>
              </td>
              <td class="sync-cell">
                <span :title="visitor.avatar_sync_record">{{ visitor.avatar_sync_record ? t("adminAccounts.hasSync") : '-' }}</span>
              </td>
              <td>
                <button class="btn-small" @click="openEditVisitorModal(visitor)">{{ t("adminAccounts.edit") }}</button>
                <button
                  :class="['btn-small', visitor.is_banned ? 'btn-unban' : 'btn-ban']"
                  @click="toggleBan(visitor)"
                >
                  {{ visitor.is_banned ? t("adminAccounts.unban") : t("adminAccounts.banAction") }}
                </button>
              </td>
            </tr>
            <tr v-if="visitors.length === 0">
              <td colspan="10" class="empty-row">{{ t("adminAccounts.noVisitors") }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div v-if="visitorTotal > visitorPageSize" class="pagination">
        <button
          class="btn-page"
          :disabled="visitorPage <= 1"
          @click="changeVisitorPage(visitorPage - 1)"
        >
          {{ t("adminAccounts.prevPage") }}
        </button>
        <span class="page-info">{{ visitorPage }} / {{ Math.ceil(visitorTotal / visitorPageSize) }}</span>
        <button
          class="btn-page"
          :disabled="visitorPage >= Math.ceil(visitorTotal / visitorPageSize)"
          @click="changeVisitorPage(visitorPage + 1)"
        >
          {{ t("adminAccounts.nextPage") }}
        </button>
      </div>
    </div>

    <!-- 编辑伴侣 Modal -->
    <div v-if="showPartnerModal" class="modal-overlay">
      <div class="modal-content">
        <h3>{{ t("adminAccounts.editAccountProfile") }}</h3>
        <form class="modal-form" @submit.prevent="submitPartnerEdit">
          <div class="form-group">
            <label>{{ t("adminAccounts.usernameLabel") }}</label>
            <input v-model="partnerEditForm.username" required class="input" minlength="3" maxlength="32" />
          </div>
          <div class="form-group">
            <label>{{ t("adminAccounts.nicknameLabel") }}</label>
            <input v-model="partnerEditForm.nickname" required class="input" minlength="1" maxlength="50" />
          </div>
          <div class="form-group">
            <label>{{ t("adminAccounts.newPasswordOptional") }}</label>
            <input v-model="partnerEditForm.password" type="password" class="input" minlength="8" maxlength="128" :placeholder="t('adminAccounts.passwordPlaceholder')" />
          </div>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showPartnerModal = false">{{ t("adminAccounts.cancel") }}</button>
            <button type="submit" class="btn-primary" :disabled="busy">{{ t("adminAccounts.save") }}</button>
          </div>
        </form>
      </div>
    </div>

    <!-- 添加伴侣 Modal -->
    <div v-if="showAddPartnerModal" class="modal-overlay">
      <div class="modal-content">
        <h3>{{ t("adminAccounts.addPartner", { label: missingPartnerLabel }) }}</h3>
        <form class="modal-form" @submit.prevent="submitAddPartner">
          <div class="form-group">
            <label>{{ t("adminAccounts.usernameLabel") }}</label>
            <input
              v-model="addPartnerForm.username"
              required
              class="input"
              minlength="3"
              maxlength="32"
              :placeholder="t('adminAccounts.usernamePlaceholder')"
              autocomplete="username"
            />
          </div>
          <div class="form-group">
            <label>{{ t("adminAccounts.nicknameLabel") }}</label>
            <input v-model="addPartnerForm.nickname" required class="input" minlength="1" maxlength="50" :placeholder="t('adminAccounts.nicknamePlaceholder')" />
          </div>
          <div class="form-group">
            <label>{{ t("adminAccounts.passwordLabel") }}</label>
            <input
              v-model="addPartnerForm.password"
              type="password"
              required
              class="input"
              minlength="8"
              maxlength="128"
              :placeholder="t('adminAccounts.passwordRequiredPlaceholder')"
              autocomplete="new-password"
            />
          </div>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showAddPartnerModal = false">{{ t("adminAccounts.cancel") }}</button>
            <button type="submit" class="btn-primary" :disabled="busy">{{ busy ? t("adminAccounts.creating") : t("adminAccounts.create") }}</button>
          </div>
        </form>
      </div>
    </div>

    <!-- 编辑访客 Modal -->
    <div v-if="showVisitorModal" class="modal-overlay">
      <div class="modal-content">
        <h3>{{ t("adminAccounts.editVisitorProfile") }}</h3>
        <form class="modal-form" @submit.prevent="submitVisitorEdit">
          <div class="form-group">
            <label>{{ t("adminAccounts.nicknameLabel") }}</label>
            <input v-model="visitorEditForm.nickname" class="input" minlength="1" maxlength="50" />
          </div>
          <div class="form-group">
            <label>{{ t("adminAccounts.permissionStatus") }}</label>
            <select v-model="visitorEditForm.permission_status" class="input">
              <option value="active">{{ t("adminAccounts.statusActive") }}</option>
              <option value="limited">{{ t("adminAccounts.statusLimited") }}</option>
              <option value="banned">{{ t("adminAccounts.statusBanned") }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>{{ t("adminAccounts.ban") }}</label>
            <label class="checkbox-label">
              <input v-model="visitorEditForm.is_banned" type="checkbox" />
              {{ t("adminAccounts.visitorBanned") }}
            </label>
          </div>
          <div class="form-group">
            <label>{{ t("adminAccounts.remark") }}</label>
            <textarea
              v-model="visitorEditForm.remark"
              class="input textarea"
              maxlength="500"
              rows="3"
              :placeholder="t('adminAccounts.remarkPlaceholder')"
            ></textarea>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showVisitorModal = false">{{ t("adminAccounts.cancel") }}</button>
            <button type="submit" class="btn-primary" :disabled="busy">{{ t("adminAccounts.save") }}</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive, computed, inject } from "vue";
import { fetchPartners, updatePartner, registerPartner, fetchVisitors, updateVisitor, toggleVisitorBan } from "../lib/api";
import { t } from "../locales";
import { parseError } from "../utils/helpers";

const showMessage = inject("showMessage");

// Tab 状态
const activeTab = ref('partners');

// 伴侣数据
const partners = ref([]);
const showPartnerModal = ref(false);
const busy = ref(false);
let currentPartnerId = null;

const partnerEditForm = reactive({
  username: "",
  nickname: "",
  password: ""
});

// 添加伴侣（创建缺失的伴侣槽位：一个 PartnerA + 一个 PartnerB）
const showAddPartnerModal = ref(false);
const addPartnerForm = reactive({
  username: "",
  nickname: "",
  password: ""
});

// 当前缺失的伴侣角色；两个都存在时为 null，不展示添加入口
const missingPartnerRole = computed(() => {
  const roles = partners.value.map((p) => p.role);
  if (!roles.includes("PartnerA")) return "PartnerA";
  if (!roles.includes("PartnerB")) return "PartnerB";
  return null;
});
const missingPartnerLabel = computed(() =>
  missingPartnerRole.value === "PartnerA" ? t("adminAccounts.partnerA") : t("adminAccounts.partnerB")
);

// 访客数据
const visitors = ref([]);
const showVisitorModal = ref(false);
const visitorPage = ref(1);
const visitorPageSize = ref(20);
const visitorTotal = ref(0);
let currentVisitorId = null;

const visitorFilters = reactive({
  sso_source: "",
  permission_status: "",
  is_banned: null
});

const visitorEditForm = reactive({
  nickname: "",
  permission_status: "active",
  is_banned: false,
  remark: ""
});

// 伴侣操作
async function loadPartners() {
  try {
    const data = await fetchPartners();
    partners.value = data.items || [];
  } catch (error) {
    showMessage(parseError(error));
  }
}

function openEditPartnerModal(partner) {
  currentPartnerId = partner.uid;
  partnerEditForm.username = partner.username;
  partnerEditForm.nickname = partner.nickname;
  partnerEditForm.password = "";
  showPartnerModal.value = true;
}

async function submitPartnerEdit() {
  busy.value = true;
  try {
    const payload = {
      username: partnerEditForm.username,
      nickname: partnerEditForm.nickname,
    };
    if (partnerEditForm.password) {
      payload.password = partnerEditForm.password;
    }
    
    await updatePartner(currentPartnerId, payload);
    showMessage(t("adminAccounts.accountUpdated"));
    showPartnerModal.value = false;
    loadPartners();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

function openAddPartnerModal() {
  if (!missingPartnerRole.value) return;
  addPartnerForm.username = "";
  addPartnerForm.nickname = "";
  addPartnerForm.password = "";
  showAddPartnerModal.value = true;
}

async function submitAddPartner() {
  if (!missingPartnerRole.value) return;
  busy.value = true;
  try {
    await registerPartner({
      username: addPartnerForm.username,
      nickname: addPartnerForm.nickname,
      password: addPartnerForm.password,
      role: missingPartnerRole.value
    });
    showMessage(t("adminAccounts.partnerCreated"));
    showAddPartnerModal.value = false;
    loadPartners();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

// 访客操作
async function loadVisitors() {
  try {
    const params = {
      page: visitorPage.value,
      page_size: visitorPageSize.value
    };
    if (visitorFilters.sso_source) params.sso_source = visitorFilters.sso_source;
    if (visitorFilters.permission_status) params.permission_status = visitorFilters.permission_status;
    if (visitorFilters.is_banned !== null) params.is_banned = visitorFilters.is_banned;
    
    const data = await fetchVisitors(params);
    visitors.value = data.items || [];
    visitorTotal.value = data.total || 0;
  } catch (error) {
    showMessage(parseError(error));
  }
}

function openEditVisitorModal(visitor) {
  currentVisitorId = visitor.uid;
  visitorEditForm.nickname = visitor.nickname;
  visitorEditForm.permission_status = visitor.permission_status;
  visitorEditForm.is_banned = visitor.is_banned;
  visitorEditForm.remark = visitor.remark || "";
  showVisitorModal.value = true;
}

async function submitVisitorEdit() {
  busy.value = true;
  try {
    const payload = {
      nickname: visitorEditForm.nickname,
      permission_status: visitorEditForm.permission_status,
      is_banned: visitorEditForm.is_banned,
      remark: visitorEditForm.remark || null
    };
    
    await updateVisitor(currentVisitorId, payload);
    showMessage(t("adminAccounts.visitorUpdated"));
    showVisitorModal.value = false;
    loadVisitors();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function toggleBan(visitor) {
  try {
    await toggleVisitorBan(visitor.uid);
    showMessage(visitor.is_banned ? t("adminAccounts.visitorUnbanned") : t("adminAccounts.visitorBannedToast"));
    loadVisitors();
  } catch (error) {
    showMessage(parseError(error));
  }
}

function changeVisitorPage(page) {
  visitorPage.value = page;
  loadVisitors();
}

function refresh() {
  if (activeTab.value === 'partners') {
    loadPartners();
  } else {
    loadVisitors();
  }
}

function formatDate(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('zh-CN', { 
    year: 'numeric', 
    month: '2-digit', 
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function statusText(status) {
  const map = {
    active: t("adminAccounts.statusActive"),
    limited: t("adminAccounts.statusLimited"),
    banned: t("adminAccounts.statusBanned")
  };
  return map[status] || status;
}

onMounted(() => {
  loadPartners();
  loadVisitors();
});
</script>

<style scoped>
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

/* Tab Navigation */
.tab-nav {
  display: flex;
  gap: 0.5rem;
}
.tab-btn {
  padding: 0.5rem 1.25rem;
  border: none;
  background: #f1f5f9;
  color: #64748b;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s;
}
.tab-btn:hover { background: #e2e8f0; }
.tab-btn.active {
  background: #3b82f6;
  color: white;
}

/* Partners Grid */
.accounts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
}
.account-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  background: #f8fafc;
}
.account-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.account-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #a855f7, #ec4899);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: bold;
}
.account-info h3 { margin: 0 0 0.25rem 0; font-size: 1.1rem; color: #1e293b; }
.account-meta { margin: 0 0 0.5rem 0; font-size: 0.85rem; color: #64748b; }
.role-badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  background: #e0e7ff;
  color: #4338ca;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
}

/* 添加伴侣卡片 */
.account-card--add {
  border: 2px dashed #cbd5e1;
  background: #fff;
  align-items: center;
  justify-content: center;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, transform 0.15s;
}
.account-card--add:hover {
  border-color: #ec4899;
  background: #fdf2f8;
  transform: translateY(-2px);
}
.add-partner-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
}
.add-partner-plus {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #a855f7, #ec4899);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.6rem;
  line-height: 1;
  margin-bottom: 0.25rem;
}
.account-card--add h3 { margin: 0; font-size: 1.05rem; color: #1e293b; }

/* Visitors Table */
.filter-bar {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  padding: 1rem;
  background: #f8fafc;
  border-radius: 8px;
}
.filter-select {
  padding: 0.5rem 0.75rem;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 0.875rem;
  outline: none;
}
.filter-select:focus { border-color: #3b82f6; }
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #475569;
  cursor: pointer;
}

.visitors-table-wrapper {
  overflow-x: auto;
}
.visitors-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}
.visitors-table th,
.visitors-table td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
}
.visitors-table th {
  background: #f8fafc;
  font-weight: 600;
  color: #475569;
}
.visitor-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  font-weight: bold;
}
.source-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  background: #dbeafe;
  color: #1d4ed8;
  border-radius: 4px;
  font-size: 0.75rem;
}
.status-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}
.status-badge.active { background: #dcfce7; color: #166534; }
.status-badge.limited { background: #fef9c3; color: #854d0e; }
.status-badge.banned { background: #fee2e2; color: #991b1b; }
.ban-indicator { color: #64748b; }
.ban-indicator.banned { color: #dc2626; font-weight: 600; }
.remark-cell, .sync-cell {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empty-row { text-align: center; color: #94a3b8; padding: 2rem; }

/* Pagination */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  margin-top: 1.5rem;
}
.page-info { font-size: 0.875rem; color: #64748b; }

/* Buttons */
.btn-secondary { background-color: #f1f5f9; color: #475569; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; font-weight: 500; }
.btn-secondary:hover { background-color: #e2e8f0; }
.btn-primary { background-color: #3b82f6; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; font-weight: 500; width: 100%; }
.btn-primary:hover { background-color: #2563eb; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-small {
  padding: 0.25rem 0.5rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.75rem;
  margin-right: 0.25rem;
  background: #e2e8f0;
  color: #475569;
}
.btn-small:hover { background: #cbd5e1; }
.btn-ban { background: #fee2e2; color: #dc2626; }
.btn-ban:hover { background: #fecaca; }
.btn-unban { background: #dcfce7; color: #166534; }
.btn-unban:hover { background: #bbf7d0; }
.btn-page {
  padding: 0.375rem 0.75rem;
  border: 1px solid #cbd5e1;
  background: white;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
}
.btn-page:disabled { opacity: 0.5; cursor: not-allowed; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 50; }
.modal-content { background: white; padding: 2rem; border-radius: 12px; width: 100%; max-width: 450px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
.modal-content h3 { margin-top: 0; margin-bottom: 1.5rem; color: #1e293b; }
.modal-form { display: flex; flex-direction: column; gap: 1rem; }
.form-group { display: flex; flex-direction: column; gap: 0.5rem; }
.form-group label { font-size: 0.875rem; font-weight: 500; color: #475569; }
.input { padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.9rem; outline: none; }
.input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.2); }
.textarea { resize: vertical; min-height: 80px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 1rem; }
</style>
