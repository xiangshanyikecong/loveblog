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
  <div class="admin-panel security-panel">
    <div class="panel-header">
      <div>
        <h2>{{ t("adminSecurity.title") }}</h2>
        <p class="panel-subtitle">{{ t("adminSecurity.subtitle") }}</p>
      </div>
      <button class="btn-secondary" @click="loadSecurityUsers">{{ t("adminSecurity.refresh") }}</button>
    </div>

    <!-- Tab Navigation -->
    <div class="tab-nav">
      <button :class="['tab-btn', { active: activeTab === 'security' }]" @click="activeTab = 'security'">
        {{ t("adminSecurity.securityTab") }}
      </button>
      <button :class="['tab-btn', { active: activeTab === 'logs' }]" @click="activeTab = 'logs'">
        {{ t("adminSecurity.logsTab") }}
      </button>
    </div>

    <!-- 安全管理 Tab -->
    <div v-if="activeTab === 'security'" class="security-section">
      <!-- 用户安全状态表格 -->
      <div class="security-table-wrapper">
        <table class="security-table">
          <thead>
            <tr>
              <th>{{ t("adminSecurity.user") }}</th>
              <th>{{ t("adminSecurity.role") }}</th>
              <th>{{ t("adminSecurity.failedCount") }}</th>
              <th>{{ t("adminSecurity.freezeStatus") }}</th>
              <th>{{ t("adminSecurity.sessionVersion") }}</th>
              <th>{{ t("adminSecurity.lastLoginIp") }}</th>
              <th>{{ t("adminSecurity.passwordChangedAt") }}</th>
              <th>{{ t("adminSecurity.actions") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in securityUsers" :key="user.uid">
              <td>
                <div class="user-cell">
                  <strong>{{ user.nickname }}</strong>
                  <span>{{ user.username }}</span>
                </div>
              </td>
              <td>
                <span class="role-badge">{{ roleLabel(user.role) }}</span>
              </td>
              <td>
                <span :class="['failed-count', { warning: user.login_failed_count > 0 }]">
                  {{ user.login_failed_count }}
                </span>
              </td>
              <td>
                <span v-if="user.login_freeze_until" class="freeze-badge frozen">
                  {{ t("adminSecurity.frozenUntil", { date: formatDate(user.login_freeze_until) }) }}
                </span>
                <span v-else class="freeze-badge normal">{{ t("adminSecurity.normal") }}</span>
              </td>
              <td>v{{ user.session_version }}</td>
              <td>{{ user.last_login_ip || '-' }}</td>
              <td>{{ formatDate(user.password_changed_at) }}</td>
              <td>
                <button class="btn-small" @click="openResetPasswordModal(user)">{{ t("adminSecurity.resetPassword") }}</button>
                <button
                  v-if="user.login_freeze_until"
                  class="btn-small btn-unlock"
                  @click="unlockUser(user)"
                >
                  {{ t("adminSecurity.unlock") }}
                </button>
                <button class="btn-small btn-revoke" @click="revokeUserSessions(user)">{{ t("adminSecurity.revokeSessions") }}</button>
              </td>
            </tr>
            <tr v-if="securityUsers.length === 0">
              <td colspan="8" class="empty-row">{{ t("adminSecurity.noUsers") }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 安全统计 -->
      <div class="security-stats">
        <div class="stat-card">
          <span class="stat-value">{{ securityUsers.length }}</span>
          <span class="stat-label">{{ t("adminSecurity.totalUsers") }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ frozenCount }}</span>
          <span class="stat-label">{{ t("adminSecurity.frozenAccounts") }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ failedLoginCount }}</span>
          <span class="stat-label">{{ t("adminSecurity.failedLoginCount") }}</span>
        </div>
      </div>
    </div>

    <!-- 安全日志 Tab -->
    <div v-if="activeTab === 'logs'" class="logs-section">
      <form class="filters" @submit.prevent="applyFilters">
        <label>
          <span>{{ t("adminSecurity.action") }}</span>
          <select v-model="filters.action">
            <option value="">{{ t("adminSecurity.all") }}</option>
            <option v-for="item in actionOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </label>
        <label>
          <span>{{ t("adminSecurity.result") }}</span>
          <select v-model="filters.result">
            <option value="">{{ t("adminSecurity.all") }}</option>
            <option value="success">{{ t("adminSecurity.success") }}</option>
            <option value="failure">{{ t("adminSecurity.failure") }}</option>
          </select>
        </label>
        <label>
          <span>{{ t("adminSecurity.resource") }}</span>
          <select v-model="filters.resource_type">
            <option value="">{{ t("adminSecurity.all") }}</option>
            <option value="article">{{ t("adminSecurity.resourceArticle") }}</option>
            <option value="user">{{ t("adminSecurity.resourceUser") }}</option>
            <option value="backup">{{ t("adminSecurity.resourceBackup") }}</option>
            <option value="site_settings">{{ t("adminSecurity.resourceSiteSettings") }}</option>
          </select>
        </label>
        <label>
          <span>{{ t("adminSecurity.keyword") }}</span>
          <input v-model.trim="filters.q" maxlength="80" :placeholder="t('adminSecurity.keywordPlaceholder')" />
        </label>
        <label>
          <span>{{ t("adminSecurity.startTime") }}</span>
          <input v-model="filters.date_from" type="datetime-local" />
        </label>
        <label>
          <span>{{ t("adminSecurity.endTime") }}</span>
          <input v-model="filters.date_to" type="datetime-local" />
        </label>
        <div class="filter-actions">
          <button type="submit" class="btn-primary">{{ t("adminSecurity.filter") }}</button>
          <button type="button" class="btn-secondary" @click="resetFilters">{{ t("adminSecurity.reset") }}</button>
        </div>
      </form>

      <div v-if="errorMessage" class="error-box">{{ errorMessage }}</div>

      <div class="audit-table-wrap">
        <table class="audit-table">
          <thead>
            <tr>
              <th>{{ t("adminSecurity.time") }}</th>
              <th>{{ t("adminSecurity.action") }}</th>
              <th>{{ t("adminSecurity.operator") }}</th>
              <th>{{ t("adminSecurity.result") }}</th>
              <th>{{ t("adminSecurity.target") }}</th>
              <th>{{ t("adminSecurity.detail") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!loading && logs.length === 0">
              <td colspan="6" class="empty-cell">{{ t("adminSecurity.noLogs") }}</td>
            </tr>
            <tr v-for="item in logs" :key="item.log_id">
              <td class="time-cell">{{ formatDate(item.created_at) }}</td>
              <td>
                <span class="action-badge">{{ actionLabel(item.action) }}</span>
              </td>
              <td>
                <div class="actor-cell">
                  <strong>{{ item.actor_nickname || item.actor_username || t("adminSecurity.system") }}</strong>
                  <span v-if="item.actor_username">{{ item.actor_username }}</span>
                </div>
              </td>
              <td>
                <span class="result-badge" :class="item.result === 'success' ? 'result-ok' : 'result-fail'">
                  {{ item.result === "success" ? t("adminSecurity.success") : t("adminSecurity.failure") }}
                </span>
              </td>
              <td>
                <div class="resource-cell">
                  <strong>{{ resourceLabel(item.resource_type) }}</strong>
                  <span>{{ item.resource_name || item.resource_id || "-" }}</span>
                </div>
              </td>
              <td class="detail-cell">{{ detailText(item) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div v-if="totalPages > 1" class="pagination">
        <button class="btn-page" :disabled="page <= 1" @click="changePage(page - 1)">{{ t("adminSecurity.prevPage") }}</button>
        <span class="page-info">{{ page }} / {{ totalPages }}</span>
        <button class="btn-page" :disabled="page >= totalPages" @click="changePage(page + 1)">{{ t("adminSecurity.nextPage") }}</button>
      </div>
    </div>

    <!-- 重置密码 Modal -->
    <div v-if="showResetPasswordModal" class="modal-overlay">
      <div class="modal-content">
        <h3>{{ t("adminSecurity.resetPasswordTitle", { name: resetPasswordTarget?.nickname }) }}</h3>
        <form class="modal-form" @submit.prevent="submitResetPassword">
          <div class="form-group">
            <label>{{ t("adminSecurity.newPassword") }}</label>
            <input
              v-model="resetPasswordForm.new_password"
              type="password"
              required
              class="input"
              minlength="8"
              maxlength="128"
              :placeholder="t('adminSecurity.passwordPlaceholder')"
            />
          </div>
          <p class="warning-text">{{ t("adminSecurity.resetWarning") }}</p>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showResetPasswordModal = false">{{ t("adminSecurity.cancel") }}</button>
            <button type="submit" class="btn-primary" :disabled="busy">{{ t("adminSecurity.confirmReset") }}</button>
          </div>
        </form>
      </div>
    </div>

    <!-- 确认操作 Modal -->
    <div v-if="showConfirmModal" class="modal-overlay">
      <div class="modal-content">
        <h3>{{ confirmModalTitle }}</h3>
        <p>{{ confirmModalMessage }}</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showConfirmModal = false">{{ t("adminSecurity.cancel") }}</button>
          <button class="btn-danger" @click="confirmAction">{{ confirmModalAction }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from "vue";
import { inject } from "vue";
import { fetchAuditLogs, fetchMe, fetchSecurityUsers, resetUserPassword, revokeUserSessions as revokeUserSessionsApi, unlockUserAccount } from "../lib/api";
import { t } from "../locales";
import { parseError } from "../utils/helpers";

const showMessage = inject("showMessage");

const activeTab = ref('security');
const loading = ref(false);
const busy = ref(false);
const errorMessage = ref("");

// 安全用户数据
const securityUsers = ref([]);

// 日志数据
const logs = ref([]);
const page = ref(1);
const pageSize = 20;
const totalPages = computed(() => Math.ceil(logs.value.length / pageSize) || 1);

const filters = reactive({
  action: "",
  result: "",
  resource_type: "",
  q: "",
  date_from: "",
  date_to: "",
});

const actionOptions = computed(() => [
  { value: "auth.login", label: t("adminSecurity.actionLogin") },
  { value: "auth.logout", label: t("adminSecurity.actionLogout") },
  { value: "security.change_password", label: t("adminSecurity.actionChangePassword") },
  { value: "security.reset_password", label: t("adminSecurity.actionResetPassword") },
  { value: "security.revoke_sessions", label: t("adminSecurity.actionRevokeSessions") },
  { value: "security.unlock_account", label: t("adminSecurity.actionUnlockAccount") },
  { value: "account.update_partner", label: t("adminSecurity.actionUpdatePartner") },
  { value: "account.update_visitor", label: t("adminSecurity.actionUpdateVisitor") },
]);

// 统计数据
const frozenCount = computed(() => securityUsers.value.filter(u => u.login_freeze_until).length);
const failedLoginCount = computed(() => securityUsers.value.reduce((sum, u) => sum + u.login_failed_count, 0));

// 重置密码 Modal
const showResetPasswordModal = ref(false);
const resetPasswordTarget = ref(null);
const resetPasswordForm = reactive({
  new_password: ""
});

// 确认 Modal
const showConfirmModal = ref(false);
const confirmModalTitle = ref("");
const confirmModalMessage = ref("");
const confirmModalAction = ref("");
let confirmActionCallback = null;

function loadSecurityUsers() {
  fetchSecurityUsers()
    .then(data => {
      securityUsers.value = data.items || [];
    })
    .catch(err => {
      showMessage(parseError(err));
    });
}

function loadLogs() {
  loading.value = true;
  errorMessage.value = "";
  const params = { page: page.value, page_size: pageSize };
  if (filters.action) params.action = filters.action;
  if (filters.result) params.result = filters.result;
  if (filters.resource_type) params.resource_type = filters.resource_type;
  if (filters.q) params.q = filters.q;
  if (filters.date_from) params.date_from = filters.date_from;
  if (filters.date_to) params.date_to = filters.date_to;
  
  fetchAuditLogs(params)
    .then(data => {
      logs.value = data.items || [];
      loading.value = false;
    })
    .catch(err => {
      errorMessage.value = parseError(err);
      loading.value = false;
    });
}

function applyFilters() {
  page.value = 1;
  loadLogs();
}

function resetFilters() {
  filters.action = "";
  filters.result = "";
  filters.resource_type = "";
  filters.q = "";
  filters.date_from = "";
  filters.date_to = "";
  page.value = 1;
  loadLogs();
}

function changePage(newPage) {
  page.value = newPage;
  loadLogs();
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

function roleLabel(role) {
  const map = {
    PartnerA: t("adminSecurity.rolePartnerA"),
    PartnerB: t("adminSecurity.rolePartnerB"),
    Visitor: t("adminSecurity.roleVisitor")
  };
  return map[role] || role;
}

function actionLabel(action) {
  const option = actionOptions.value.find(o => o.value === action);
  return option ? option.label : action;
}

function resourceLabel(type) {
  const map = {
    article: t("adminSecurity.resourceArticle"),
    user: t("adminSecurity.resourceUser"),
    backup: t("adminSecurity.resourceBackup"),
    site_settings: t("adminSecurity.resourceSiteSettings")
  };
  return map[type] || type;
}

function detailText(item) {
  if (!item.detail) return "-";
  try {
    const d = typeof item.detail === "string" ? JSON.parse(item.detail) : item.detail;
    return Object.entries(d).map(([k, v]) => `${k}: ${v}`).join(", ");
  } catch {
    return item.detail;
  }
}

// 操作函数
function openResetPasswordModal(user) {
  resetPasswordTarget.value = user;
  resetPasswordForm.new_password = "";
  showResetPasswordModal.value = true;
}

async function submitResetPassword() {
  busy.value = true;
  try {
    await resetUserPassword(resetPasswordTarget.value.uid, {
      new_password: resetPasswordForm.new_password
    });
    showMessage(t("adminSecurity.passwordReset"));
    showResetPasswordModal.value = false;
  } catch (err) {
    showMessage(parseError(err));
  } finally {
    busy.value = false;
  }
}

async function unlockUser(user) {
  try {
    await unlockUserAccount(user.uid);
    showMessage(t("adminSecurity.accountUnlocked"));
    loadSecurityUsers();
  } catch (err) {
    showMessage(parseError(err));
  }
}

function revokeUserSessions(user) {
  confirmModalTitle.value = t("adminSecurity.revokeAllSessions");
  confirmModalMessage.value = t("adminSecurity.confirmRevokeMessage", { name: user.nickname });
  confirmModalAction.value = t("adminSecurity.confirmRevoke");
  confirmActionCallback = async () => {
    try {
      await revokeUserSessionsApi(user.uid);
      showConfirmModal.value = false;
      
      // 检查是否撤销的是当前用户自己的会话
      // 如果是，需要重定向到登录页
      const currentUserData = await fetchMe().catch(() => null);
      
      if (!currentUserData) {
        // 当前用户会话已被撤销，显示消息并重定向
        showMessage(t("adminSecurity.allSessionsRevoked"));
        setTimeout(() => {
          window.location.href = '/login';
        }, 1000);
      } else {
        // 撤销的是其他用户的会话，刷新列表
        showMessage(t("adminSecurity.sessionRevoked"));
        loadSecurityUsers();
      }
    } catch (err) {
      showMessage(parseError(err));
    }
  };
  showConfirmModal.value = true;
}

function confirmAction() {
  if (confirmActionCallback) {
    confirmActionCallback();
  }
}

onMounted(() => {
  loadSecurityUsers();
  loadLogs();
});
</script>

<style scoped>
.admin-panel { background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); padding: 1.5rem; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.panel-header h2 { margin: 0; font-size: 1.25rem; color: #1e293b; }
.panel-subtitle { margin: 0.25rem 0 0; font-size: 0.875rem; color: #64748b; }

/* Tab Navigation */
.tab-nav { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
.tab-btn { padding: 0.5rem 1.25rem; border: none; background: #f1f5f9; color: #64748b; border-radius: 6px; cursor: pointer; font-size: 0.875rem; font-weight: 500; transition: all 0.2s; }
.tab-btn:hover { background: #e2e8f0; }
.tab-btn.active { background: #3b82f6; color: white; }

/* Security Table */
.security-table-wrapper { overflow-x: auto; margin-bottom: 1.5rem; }
.security-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
.security-table th, .security-table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
.security-table th { background: #f8fafc; font-weight: 600; color: #475569; }
.user-cell { display: flex; flex-direction: column; }
.user-cell strong { color: #1e293b; }
.user-cell span { font-size: 0.75rem; color: #64748b; }
.role-badge { display: inline-block; padding: 0.15rem 0.5rem; background: #e0e7ff; color: #4338ca; border-radius: 4px; font-size: 0.75rem; }
.failed-count { font-weight: 600; }
.failed-count.warning { color: #dc2626; }
.freeze-badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }
.freeze-badge.normal { background: #dcfce7; color: #166534; }
.freeze-badge.frozen { background: #fee2e2; color: #991b1b; }

/* Security Stats */
.security-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-top: 1.5rem; }
.stat-card { background: #f8fafc; padding: 1rem; border-radius: 8px; text-align: center; }
.stat-value { display: block; font-size: 2rem; font-weight: 700; color: #1e293b; }
.stat-label { font-size: 0.875rem; color: #64748b; }

/* Filters */
.filters { display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.5rem; padding: 1rem; background: #f8fafc; border-radius: 8px; }
.filters label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.875rem; color: #475569; }
.filters select, .filters input { padding: 0.5rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.875rem; }
.filter-actions { display: flex; align-items: flex-end; gap: 0.5rem; margin-left: auto; }

/* Audit Table */
.audit-table-wrap { overflow-x: auto; }
.audit-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
.audit-table th, .audit-table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
.audit-table th { background: #f8fafc; font-weight: 600; color: #475569; }
.time-cell { white-space: nowrap; color: #64748b; font-size: 0.8rem; }
.action-badge { display: inline-block; padding: 0.15rem 0.5rem; background: #dbeafe; color: #1d4ed8; border-radius: 4px; font-size: 0.75rem; }
.result-badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }
.result-ok { background: #dcfce7; color: #166534; }
.result-fail { background: #fee2e2; color: #991b1b; }
.actor-cell, .resource-cell { display: flex; flex-direction: column; }
.actor-cell strong, .resource-cell strong { color: #1e293b; }
.actor-cell span, .resource-cell span { font-size: 0.75rem; color: #64748b; }
.detail-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.8rem; color: #64748b; }
.empty-cell, .empty-row { text-align: center; color: #94a3b8; padding: 2rem; }

/* Pagination */
.pagination { display: flex; justify-content: center; align-items: center; gap: 1rem; margin-top: 1.5rem; }
.page-info { font-size: 0.875rem; color: #64748b; }

/* Buttons */
.btn-secondary { background-color: #f1f5f9; color: #475569; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; font-weight: 500; }
.btn-secondary:hover { background-color: #e2e8f0; }
.btn-primary { background-color: #3b82f6; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; font-weight: 500; }
.btn-primary:hover { background-color: #2563eb; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-danger { background-color: #dc2626; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; font-weight: 500; }
.btn-danger:hover { background-color: #b91c1c; }
.btn-small { padding: 0.25rem 0.5rem; border: none; border-radius: 4px; cursor: pointer; font-size: 0.75rem; margin-right: 0.25rem; background: #e2e8f0; color: #475569; }
.btn-small:hover { background: #cbd5e1; }
.btn-unlock { background: #dcfce7; color: #166534; }
.btn-unlock:hover { background: #bbf7d0; }
.btn-revoke { background: #fef9c3; color: #854d0e; }
.btn-revoke:hover { background: #fef08a; }
.btn-page { padding: 0.375rem 0.75rem; border: 1px solid #cbd5e1; background: white; border-radius: 6px; cursor: pointer; font-size: 0.875rem; }
.btn-page:disabled { opacity: 0.5; cursor: not-allowed; }

/* Error Box */
.error-box { background: #fee2e2; border: 1px solid #fecaca; color: #991b1b; padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; font-size: 0.875rem; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 50; }
.modal-content { background: white; padding: 2rem; border-radius: 12px; width: 100%; max-width: 450px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
.modal-content h3 { margin-top: 0; margin-bottom: 1.5rem; color: #1e293b; }
.modal-form { display: flex; flex-direction: column; gap: 1rem; }
.form-group { display: flex; flex-direction: column; gap: 0.5rem; }
.form-group label { font-size: 0.875rem; font-weight: 500; color: #475569; }
.input { padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.9rem; outline: none; }
.input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.2); }
.warning-text { font-size: 0.875rem; color: #dc2626; background: #fee2e2; padding: 0.75rem; border-radius: 6px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 1rem; }
</style>
