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
  <div class="content-section security-center">
    <header class="security-header">
      <div>
        <h2>{{ t("securityCenter.title") }}</h2>
        <p>{{ t("securityCenter.subtitle") }}</p>
      </div>
      <router-link to="/cottage" class="security-back">{{ t("securityCenter.back") }}</router-link>
    </header>

    <!-- 两步验证 -->
    <section class="glass-card section-block totp-card">
      <div class="block-head">
        <h3>{{ t("securityCenter.totpTitle") }}</h3>
        <span class="status-pill" :class="totpEnabled ? 'status-on' : 'status-off'">
          {{ totpEnabled ? t("securityCenter.totpEnabled") : t("securityCenter.totpDisabled") }}
        </span>
      </div>
      <p class="block-desc">{{ t("securityCenter.totpDesc") }}</p>
      <p v-if="totpEnabled" class="block-meta">
        {{ t("securityCenter.recoveryRemaining", { count: recoveryRemaining }) }}
      </p>

      <template v-if="!totpEnabled">
        <button v-if="!wizard" class="btn" @click="startSetup">
          {{ t("securityCenter.totpSetupBtn") }}
        </button>

        <!-- 开启向导 · 步骤 1：绑定验证器 -->
        <div v-else-if="wizard === 'setup'" class="wizard">
          <h4 class="wizard-title">{{ t("securityCenter.totpSetupTitle") }}</h4>
          <p class="wizard-step">{{ t("securityCenter.totpSetupStep1") }}</p>
          <div class="secret-box">
            <span class="secret-label">{{ t("securityCenter.totpSecretLabel") }}</span>
            <div class="secret-row">
              <code class="mono secret-value">{{ setupSecret }}</code>
              <button class="btn-small ghost" type="button" @click="copyText(setupSecret)">
                {{ t("common.copy") }}
              </button>
            </div>
          </div>
          <div class="secret-box">
            <span class="secret-label">{{ t("securityCenter.totpUriLabel") }}</span>
            <div class="secret-row">
              <code class="mono secret-value uri">{{ setupUri }}</code>
              <button class="btn-small ghost" type="button" @click="copyText(setupUri)">
                {{ t("common.copy") }}
              </button>
            </div>
          </div>
          <p class="wizard-step">{{ t("securityCenter.totpSetupStep2") }}</p>
          <form class="wizard-form" @submit.prevent="confirmEnable">
            <input
              v-model="code"
              class="input mono"
              :class="{ invalid: codeInvalid }"
              maxlength="6"
              inputmode="numeric"
              autocomplete="one-time-code"
              :placeholder="t('securityCenter.totpCodePlaceholder')"
              required
            />
            <button class="btn" type="submit" :disabled="enableBusy || !code.trim()">
              {{ t("securityCenter.totpConfirm") }}
            </button>
            <button class="text-action" type="button" @click="cancelWizard">
              {{ t("common.cancel") }}
            </button>
          </form>
        </div>

        <!-- 开启向导 · 步骤 2：恢复码 -->
        <div v-else-if="wizard === 'recovery'" class="wizard">
          <h4 class="wizard-title">{{ t("securityCenter.totpRecoveryTitle") }}</h4>
          <p class="wizard-step">{{ t("securityCenter.totpRecoveryDesc") }}</p>
          <ul class="recovery-list">
            <li v-for="(item, index) in recoveryCodes" :key="index" class="mono">{{ item }}</li>
          </ul>
          <div class="wizard-actions">
            <button class="btn-small ghost" type="button" @click="copyRecoveryCodes">
              {{ t("common.copy") }}
            </button>
            <button class="btn" type="button" @click="finishWizard">
              {{ t("securityCenter.totpRecoveryDone") }}
            </button>
          </div>
        </div>
      </template>

      <template v-else>
        <button v-if="!showDisable" class="btn danger" @click="showDisable = true">
          {{ t("securityCenter.totpDisableBtn") }}
        </button>

        <!-- 关闭两步验证 -->
        <form v-else class="wizard" @submit.prevent="confirmDisable">
          <h4 class="wizard-title">{{ t("securityCenter.totpDisableTitle") }}</h4>
          <label class="field">
            <span>{{ t("securityCenter.totpDisableCode") }}</span>
            <input
              v-model="disableForm.code"
              class="input mono"
              :class="{ invalid: disableCodeInvalid }"
              maxlength="16"
              autocomplete="one-time-code"
              :placeholder="t('securityCenter.totpCodePlaceholder')"
              required
            />
          </label>
          <label class="field">
            <span>{{ t("securityCenter.totpDisablePassword") }}</span>
            <input
              v-model="disableForm.password"
              class="input"
              type="password"
              autocomplete="current-password"
              required
            />
          </label>
          <div class="wizard-actions">
            <button
              class="btn danger"
              type="submit"
              :disabled="disableBusy || !disableForm.code.trim() || !disableForm.password"
            >
              {{ t("securityCenter.totpDisableConfirm") }}
            </button>
            <button class="text-action" type="button" @click="closeDisableForm">
              {{ t("common.cancel") }}
            </button>
          </div>
        </form>
      </template>
    </section>

    <!-- 登录设备 -->
    <section class="glass-card section-block devices-card">
      <div class="block-head">
        <h3>{{ t("securityCenter.devicesTitle") }}</h3>
        <button class="btn-small ghost" :disabled="devicesLoading" @click="loadDevices">
          {{ t("common.refresh") }}
        </button>
      </div>
      <p class="block-desc">{{ t("securityCenter.devicesDesc") }}</p>

      <p v-if="devicesLoading" class="empty-text">{{ t("common.loading") }}</p>
      <p v-else-if="!devices.length" class="empty-text">{{ t("securityCenter.noDevices") }}</p>

      <ul v-else class="device-list">
        <li
          v-for="device in devices"
          :key="device.did"
          class="device-row"
          :title="device.user_agent || ''"
        >
          <div class="device-main">
            <p class="device-name">{{ device.device_name || t("securityCenter.unknownDevice") }}</p>
            <p class="device-meta">
              <span class="mono">{{ device.ip || "-" }}</span>
              <span>{{ t("securityCenter.lastLogin") }}: {{ formatDateTime(device.last_login_at) }}</span>
              <span>{{ t("securityCenter.firstSeen") }}: {{ formatDateTime(device.first_seen_at) }}</span>
            </p>
          </div>
          <button
            class="text-action danger"
            :disabled="deviceBusy"
            @click="removeDevice(device)"
          >
            {{ t("securityCenter.removeDevice") }}
          </button>
        </li>
      </ul>

      <div v-if="devices.length" class="devices-footer">
        <button class="btn danger-outline" :disabled="deviceBusy" @click="removeAllDevices">
          {{ t("securityCenter.removeAllDevices") }}
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  fetchLoginDevices,
  revokeAllLoginDevices,
  revokeLoginDevice,
  totpDisable,
  totpEnable,
  totpSetup,
  totpStatus,
} from "../../../lib/api";
import { confirmDialog } from "../../../lib/dialog";
import { parseError } from "../../../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

// ── 两步验证状态 ──────────────────────────────────────────────────────────────
const totpEnabled = ref(false);
const recoveryRemaining = ref(0);
const wizard = ref(""); // "" | "setup" | "recovery"
const setupSecret = ref("");
const setupUri = ref("");
const code = ref("");
const codeInvalid = ref(false);
const enableBusy = ref(false);
const recoveryCodes = ref([]);
const showDisable = ref(false);
const disableBusy = ref(false);
const disableCodeInvalid = ref(false);
const disableForm = reactive({ code: "", password: "" });

// ── 登录设备 ──────────────────────────────────────────────────────────────────
const devices = ref([]);
const devicesLoading = ref(true);
const deviceBusy = ref(false);

function formatDateTime(raw) {
  if (!raw) return "-";
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? String(raw) : date.toLocaleString("zh-CN", { hour12: false });
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    showMessage(t("common.copied"));
  } catch {
    showMessage(t("privacyCenter.clipboardDenied"));
  }
}

function copyRecoveryCodes() {
  return copyText(recoveryCodes.value.join("\n"));
}

function isInvalidCodeError(error) {
  return /invalid (verification )?code/i.test(String(error?.response?.data?.detail || ""));
}

function isPasswordError(error) {
  const detail = String(error?.response?.data?.detail || "");
  return /password/i.test(detail) || detail.includes("密码");
}

async function loadStatus() {
  try {
    const data = await totpStatus();
    totpEnabled.value = !!data.enabled;
    recoveryRemaining.value = data.recovery_codes_remaining ?? 0;
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function loadDevices() {
  devicesLoading.value = true;
  try {
    const data = await fetchLoginDevices();
    devices.value = data.items || [];
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    devicesLoading.value = false;
  }
}

async function startSetup() {
  try {
    const data = await totpSetup();
    setupSecret.value = data.secret || "";
    setupUri.value = data.uri || "";
    code.value = "";
    codeInvalid.value = false;
    wizard.value = "setup";
  } catch (error) {
    showMessage(parseError(error));
  }
}

function cancelWizard() {
  wizard.value = "";
  code.value = "";
  codeInvalid.value = false;
}

function finishWizard() {
  wizard.value = "";
  code.value = "";
  recoveryCodes.value = [];
}

async function confirmEnable() {
  const value = code.value.trim();
  if (!value || enableBusy.value) return;
  enableBusy.value = true;
  codeInvalid.value = false;
  try {
    const data = await totpEnable(value);
    recoveryCodes.value = data.recovery_codes || [];
    wizard.value = "recovery";
    showMessage(t("securityCenter.totpEnabledToast"));
    await loadStatus();
  } catch (error) {
    if (isInvalidCodeError(error)) {
      codeInvalid.value = true;
      showMessage(t("securityCenter.totpInvalidCode"));
    } else {
      showMessage(parseError(error));
    }
  } finally {
    enableBusy.value = false;
  }
}

function closeDisableForm() {
  showDisable.value = false;
  disableForm.code = "";
  disableForm.password = "";
  disableCodeInvalid.value = false;
}

async function confirmDisable() {
  if (disableBusy.value) return;
  disableBusy.value = true;
  disableCodeInvalid.value = false;
  try {
    await totpDisable(disableForm.code.trim(), disableForm.password);
    showMessage(t("securityCenter.totpDisabledToast"));
    closeDisableForm();
    await loadStatus();
  } catch (error) {
    if (isInvalidCodeError(error)) {
      disableCodeInvalid.value = true;
      showMessage(t("securityCenter.totpInvalidCode"));
    } else if (isPasswordError(error)) {
      showMessage(t("securityCenter.totpInvalidPassword"));
    } else {
      showMessage(parseError(error));
    }
  } finally {
    disableBusy.value = false;
  }
}

function handleSessionRevoked() {
  showMessage(t("securityCenter.deviceRemovedToast"));
  // Session 已被服务端失效，稍等 toast 展示后回到登录页。
  setTimeout(() => {
    window.location.href = "/login";
  }, 1500);
}

async function removeDevice(device) {
  if (deviceBusy.value) return;
  if (!(await confirmDialog(t("securityCenter.confirmRemoveDevice"), { danger: true }))) return;
  deviceBusy.value = true;
  try {
    await revokeLoginDevice(device.did);
    handleSessionRevoked();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    deviceBusy.value = false;
  }
}

async function removeAllDevices() {
  if (deviceBusy.value) return;
  if (!(await confirmDialog(t("securityCenter.confirmRemoveAll"), { danger: true }))) return;
  deviceBusy.value = true;
  try {
    await revokeAllLoginDevices();
    handleSessionRevoked();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    deviceBusy.value = false;
  }
}

onMounted(() => {
  loadStatus();
  loadDevices();
});
</script>

<style scoped>
.security-center { display: grid; gap: 1rem; }

.security-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.security-header h2 { margin: 0; font-size: 1.4rem; color: #2f3754; }
.security-header p { margin: 0.35rem 0 0; color: var(--text-soft); font-size: 0.9rem; }
.security-back {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  font-size: 0.82rem;
  text-decoration: none;
  white-space: nowrap;
}

.totp-card,
.devices-card { display: grid; gap: 0.7rem; border-radius: 16px; }

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}
.block-head h3 { margin: 0; font-size: 1.05rem; color: #2f3754; }

.status-pill {
  border-radius: 999px;
  padding: 0.18rem 0.65rem;
  font-size: 0.74rem;
  font-weight: 700;
}
.status-on {
  background: rgba(52, 211, 153, 0.18);
  color: #047857;
}
.status-off {
  background: rgba(148, 163, 184, 0.22);
  color: #64748b;
}

.block-desc {
  margin: 0;
  color: var(--text-soft);
  font-size: 0.86rem;
  line-height: 1.6;
}
.block-meta {
  margin: 0;
  color: #475569;
  font-size: 0.82rem;
  font-weight: 700;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.btn {
  border: 0;
  border-radius: 12px;
  padding: 0.62rem 0.95rem;
  background: linear-gradient(120deg, #dc4b78, #8f9bff);
  color: #fff;
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
}
.btn:disabled { cursor: not-allowed; opacity: 0.65; }
.btn.danger { background: linear-gradient(120deg, #ff6b6b, #ff9a5c); }
.btn.danger-outline {
  border: 1px solid rgba(220, 75, 120, 0.5);
  background: rgba(255, 255, 255, 0.8);
  color: #dc4b78;
}
.btn-small {
  border: 0;
  border-radius: 10px;
  padding: 0.42rem 0.85rem;
  background: #dc4b78;
  color: #fff;
  font-size: 0.8rem;
  cursor: pointer;
}
.btn-small.ghost {
  background: rgba(143, 155, 255, 0.15);
  border: 1px solid rgba(143, 155, 255, 0.4);
  color: #4f5ecf;
}
.btn-small:disabled { cursor: not-allowed; opacity: 0.6; }

.text-action {
  border: 0;
  background: transparent;
  color: #5b68a5;
  cursor: pointer;
  padding: 0;
  font-size: 0.82rem;
}
.text-action.danger { color: #dc4b78; }
.text-action:disabled { cursor: not-allowed; opacity: 0.6; }

.wizard {
  display: grid;
  gap: 0.7rem;
  border-top: 1px dashed rgba(148, 163, 184, 0.4);
  padding-top: 0.9rem;
}
.wizard-title { margin: 0; font-size: 0.95rem; color: #2f3754; }
.wizard-step {
  margin: 0;
  color: #475569;
  font-size: 0.85rem;
  line-height: 1.6;
}

.secret-box {
  display: grid;
  gap: 0.3rem;
  background: rgba(248, 250, 255, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 12px;
  padding: 0.65rem 0.8rem;
}
.secret-label { color: #64748b; font-size: 0.74rem; }
.secret-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.secret-value {
  flex: 1 1 auto;
  min-width: 0;
  color: #2f3754;
  font-size: 0.85rem;
  overflow-wrap: anywhere;
}
.secret-value.uri { font-size: 0.72rem; color: #475569; }

.wizard-form {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.wizard-form .input { max-width: 180px; }

.input.invalid {
  border-color: #dc4b78;
  box-shadow: 0 0 0 2px rgba(220, 75, 120, 0.18);
}

.wizard-actions {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  flex-wrap: wrap;
}

.recovery-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.4rem;
  list-style: none;
  margin: 0;
  padding: 0;
}
.recovery-list li {
  background: rgba(248, 250, 255, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 10px;
  color: #2f3754;
  font-size: 0.85rem;
  padding: 0.42rem 0.6rem;
  overflow-wrap: anywhere;
}

.field {
  display: grid;
  gap: 0.35rem;
  color: #475569;
  font-size: 0.82rem;
  font-weight: 700;
}

.empty-text {
  margin: 0;
  color: var(--text-soft);
  font-size: 0.86rem;
}

.device-list {
  display: grid;
  gap: 0.7rem;
  list-style: none;
  margin: 0;
  padding: 0;
}
.device-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  background: rgba(248, 250, 255, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  padding: 0.75rem 1rem;
}
.device-main { min-width: 0; display: grid; gap: 0.25rem; }
.device-name {
  margin: 0;
  color: #2f3754;
  font-size: 0.9rem;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.device-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin: 0;
  color: var(--text-soft);
  font-size: 0.76rem;
}
.devices-footer {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .security-header { flex-direction: column; }
  .security-back { width: 100%; justify-content: center; }
  .device-row { flex-direction: column; align-items: flex-start; }
}
</style>
