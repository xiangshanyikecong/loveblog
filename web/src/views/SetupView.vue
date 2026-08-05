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
  <div class="setup-root">
    <!-- Background blobs -->
    <div class="setup-blob setup-blob--a"></div>
    <div class="setup-blob setup-blob--b"></div>

    <div class="setup-card">
      <!-- Header -->
      <div class="setup-header">
        <div class="setup-logo">💕</div>
        <h1 class="setup-title">{{ t('setup.title') }}</h1>
        <p class="setup-subtitle">{{ t('setup.subtitle') }}</p>
      </div>

      <!-- Step indicators -->
      <div class="step-indicators">
        <div v-for="i in 3" :key="i" class="step-dot-wrap">
          <div class="step-dot" :class="{ active: step === i, done: step > i }">
            <span v-if="step > i">✓</span>
            <span v-else>{{ i }}</span>
          </div>
          <div class="step-label">{{ stepLabels[i - 1] }}</div>
          <div v-if="i < 3" class="step-line" :class="{ done: step > i }"></div>
        </div>
      </div>

      <!-- Step 1: Token -->
      <transition name="slide" mode="out-in">
        <div v-if="step === 1" key="step1" class="step-body">
          <div class="field-group">
            <label class="field-label">{{ t('setup.tokenLabel') }}</label>
            <p class="field-hint">{{ t('setup.tokenHint') }}</p>
            <input
              id="bootstrap-token-input"
              v-model="form.token"
              class="setup-input"
              type="password"
              :placeholder="t('setup.tokenPlaceholder')"
              autocomplete="off"
              @keyup.enter="verifyToken"
            />
          </div>
          <div v-if="errMsg" class="setup-err">{{ errMsg }}</div>
          <button id="btn-verify-token" class="setup-btn" :disabled="busy || !form.token.trim()" @click="verifyToken">
            <span v-if="busy" class="spinner"></span>
            {{ busy ? t('setup.verifying') : t('setup.verifyToken') }}
          </button>
        </div>

        <!-- Step 2: Site info -->
        <div v-else-if="step === 2" key="step2" class="step-body">
          <div class="field-group">
            <label class="field-label">{{ t('setup.siteNameLabel') }}</label>
            <input
              id="site-name-input"
              v-model="form.siteName"
              class="setup-input"
              type="text"
              :placeholder="t('setup.siteNamePlaceholder')"
              maxlength="120"
            />
          </div>
          <div class="field-group">
            <label class="field-label">{{ t('setup.loveDateLabel') }}</label>
            <p class="field-hint">{{ t('setup.loveDateHint') }}</p>
            <input
              id="love-date-input"
              v-model="form.loveDate"
              class="setup-input"
              type="date"
            />
          </div>
          <div v-if="errMsg" class="setup-err">{{ errMsg }}</div>
          <button id="btn-site-next" class="setup-btn" :disabled="!form.siteName.trim()" @click="goStep3">
            {{ t('setup.next') }}
          </button>
        </div>

        <!-- Step 3: Account -->
        <div v-else key="step3" class="step-body">
          <p class="field-hint" style="margin-bottom:1rem;">{{ t('setup.accountHint') }}</p>
          <div class="form-row">
            <div class="field-group">
              <label class="field-label">{{ t('setup.usernameLabel') }}</label>
              <input
                id="reg-username"
                v-model="form.username"
                class="setup-input"
                type="text"
                :placeholder="t('setup.usernamePlaceholder')"
                autocomplete="username"
              />
            </div>
            <div class="field-group">
              <label class="field-label">{{ t('setup.nicknameLabel') }}</label>
              <input
                id="reg-nickname"
                v-model="form.nickname"
                class="setup-input"
                type="text"
                :placeholder="t('setup.nicknamePlaceholder')"
              />
            </div>
          </div>
          <div class="field-group">
            <label class="field-label">{{ t('setup.passwordLabel') }}</label>
            <input
              id="reg-password"
              v-model="form.password"
              class="setup-input"
              type="password"
              :placeholder="t('setup.passwordPlaceholder')"
              autocomplete="new-password"
            />
          </div>
          <div v-if="errMsg" class="setup-err">{{ errMsg }}</div>
          <div class="btn-row">
            <button class="setup-btn setup-btn--ghost" @click="step = 2">{{ t('setup.prev') }}</button>
            <button
              id="btn-submit-setup"
              class="setup-btn"
              :disabled="busy || !canSubmit"
              @click="submitSetup"
            >
              <span v-if="busy" class="spinner"></span>
              {{ busy ? t('setup.initializing') : t('setup.complete') }}
            </button>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { fetchBootstrapStatus, submitBootstrap } from "../lib/api";
import { invalidateBootstrapCache } from "../router";
import { parseError } from "../utils/helpers";

const { t } = useI18n();
const router = useRouter();
const step = ref(1);
const busy = ref(false);
const errMsg = ref("");

const stepLabels = computed(() => [t("setup.stepToken"), t("setup.stepSite"), t("setup.stepAccount")]);

const form = reactive({
  token: "",
  siteName: t("setup.defaultSiteName"),
  loveDate: "",
  username: "",
  nickname: "",
  password: ""
});

const canSubmit = computed(() =>
  form.username.trim() && form.nickname.trim() && form.password.length >= 8
);

async function verifyToken() {
  if (!form.token.trim()) return;
  errMsg.value = "";
  busy.value = true;
  try {
    // Quick check: if bootstrap is already done, redirect
    const status = await fetchBootstrapStatus();
    if (status.bootstrapped) {
      router.replace({ name: "dashboard" });
      return;
    }
    // Token will be validated on actual submit; for now just proceed
    step.value = 2;
  } catch (e) {
    errMsg.value = parseError(e);
  } finally {
    busy.value = false;
  }
}

function goStep3() {
  errMsg.value = "";
  if (!form.siteName.trim()) {
    errMsg.value = t("setup.siteNameRequired");
    return;
  }
  step.value = 3;
}

async function submitSetup() {
  errMsg.value = "";
  busy.value = true;
  try {
    const payload = {
      username: form.username,
      nickname: form.nickname,
      password: form.password,
      role: "PartnerA",
      site_name: form.siteName,
      love_start_date: form.loveDate || null
    };
    await submitBootstrap(payload, form.token);
    invalidateBootstrapCache();
    // Success - go to login
    router.replace({ name: "login", query: { setup: "done" } });
  } catch (e) {
    errMsg.value = parseError(e);
    // If token was wrong, send back to step 1
    if (errMsg.value.includes("token") || errMsg.value.includes("令牌") || errMsg.value.includes("401")) {
      step.value = 1;
    }
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.setup-root {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  padding: 1.5rem;
  background: linear-gradient(135deg, #fdf0f9 0%, #eef2ff 50%, #f0fdf4 100%);
}

.setup-blob {
  position: fixed;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
  z-index: 0;
}
.setup-blob--a {
  width: 480px; height: 480px;
  background: radial-gradient(circle, rgba(236,72,153,0.18) 0%, transparent 70%);
  top: -120px; left: -120px;
  animation: blobFloat 8s ease-in-out infinite;
}
.setup-blob--b {
  width: 400px; height: 400px;
  background: radial-gradient(circle, rgba(99,102,241,0.16) 0%, transparent 70%);
  bottom: -100px; right: -100px;
  animation: blobFloat 10s ease-in-out infinite reverse;
}
@keyframes blobFloat {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(20px, -20px) scale(1.05); }
}

.setup-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 480px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px);
  border-radius: 24px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.08);
  padding: 2rem;
}

.setup-header {
  text-align: center;
  margin-bottom: 1.5rem;
}
.setup-logo {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}
.setup-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 800;
  color: #2f3754;
}
.setup-subtitle {
  margin: 0.5rem 0 0;
  font-size: 0.88rem;
  color: #64748b;
}

.step-indicators {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1.5rem;
}
.step-dot-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.step-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.82rem;
  font-weight: 700;
  border: 2px solid #e2e8f0;
  background: #f8fafc;
  color: #94a3b8;
  transition: all 0.3s ease;
}
.step-dot.active {
  border-color: #ec4899;
  background: #fdf2f8;
  color: #ec4899;
}
.step-dot.done {
  border-color: #10b981;
  background: #10b981;
  color: #fff;
}
.step-label {
  font-size: 0.78rem;
  color: #64748b;
  white-space: nowrap;
}
.step-line {
  width: 40px;
  height: 2px;
  background: #e2e8f0;
  margin: 0 0.5rem;
  transition: background 0.3s ease;
}
.step-line.done {
  background: #10b981;
}

.step-body {
  display: grid;
  gap: 1rem;
}

.field-group {
  display: grid;
  gap: 0.35rem;
}
.field-label {
  font-size: 0.86rem;
  font-weight: 600;
  color: #2f3754;
}
.field-hint {
  margin: 0;
  font-size: 0.78rem;
  color: #94a3b8;
  line-height: 1.5;
}
.field-hint code {
  background: #f1f5f9;
  padding: 0.1rem 0.3rem;
  border-radius: 4px;
  font-size: 0.76rem;
}
.setup-input {
  width: 100%;
  padding: 0.7rem 0.9rem;
  border: 1.5px solid #e2e8f0;
  border-radius: 12px;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s ease;
  background: #fff;
  color: #1e293b;
}
.setup-input:focus {
  border-color: #ec4899;
}
.setup-err {
  color: #ef4444;
  font-size: 0.82rem;
  padding: 0.5rem 0.8rem;
  background: #fef2f2;
  border-radius: 8px;
}
.setup-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 12px;
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  background: linear-gradient(135deg, #ec4899, #f43f5e);
  color: #fff;
}
.setup-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.setup-btn--ghost {
  background: transparent;
  color: #64748b;
  border: 1.5px solid #e2e8f0;
}
.btn-row {
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.slide-enter-active, .slide-leave-active {
  transition: all 0.3s ease;
}
.slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

@media (max-width: 480px) {
  .form-row {
    grid-template-columns: 1fr;
  }
  .setup-card {
    padding: 1.5rem;
  }
}
</style>
