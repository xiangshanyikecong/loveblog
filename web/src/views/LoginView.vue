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
  <div class="content-section login-view">
    <div v-if="setupJustDone" class="setup-success-banner">
      <CircleCheck :size="18" :stroke-width="2" aria-hidden="true" />
      <span>{{ t('auth.loginSetupDone') }}</span>
    </div>
    <article class="glass-card section-block login-block">
      <div class="section-header">
        <h2>{{ totpStep ? t('loginTotp.title') : t('auth.loginTitle') }}</h2>
      </div>
      <form v-if="!totpStep" class="form-stack" @submit.prevent="login">
        <label class="form-field">
          <span>{{ t('auth.username') }}</span>
          <input v-model="loginForm.username" class="input" autocomplete="username" :placeholder="t('auth.usernamePlaceholder')" required />
        </label>
        <label class="form-field">
          <span>{{ t('auth.password') }}</span>
          <input v-model="loginForm.password" class="input" type="password" autocomplete="current-password" :placeholder="t('auth.passwordPlaceholder')" required />
        </label>
        <button class="btn-primary button-with-icon" :disabled="busy.login">
          <LogIn :size="17" :stroke-width="1.8" aria-hidden="true" />
          {{ busy.login ? t('auth.loginSubmitting') : t('auth.loginSubmit') }}
        </button>
      </form>

      <form v-else class="form-stack" @submit.prevent="loginWithTotp">
        <p class="totp-hint">{{ t('loginTotp.desc') }}</p>
        <label class="form-field">
          <span>{{ t('loginTotp.title') }}</span>
          <input
            v-model="totpCode"
            class="input totp-input"
            autocomplete="one-time-code"
            maxlength="16"
            :placeholder="t('loginTotp.placeholder')"
            required
          />
        </label>
        <button class="btn-primary button-with-icon" :disabled="busy.login">
          <LogIn :size="17" :stroke-width="1.8" aria-hidden="true" />
          {{ busy.login ? t('auth.loginSubmitting') : t('loginTotp.submit') }}
        </button>
        <button class="text-btn totp-back" type="button" @click="backToCredentials">
          {{ t('loginTotp.back') }}
        </button>
      </form>

      <div class="recovery-toggle-row">
        <button class="text-btn" type="button" @click="showRecovery = !showRecovery">
          {{ t('auth.forgotPasswordToggle') }}
        </button>
      </div>

      <form v-if="showRecovery" class="form-stack recovery-form" @submit.prevent="submitRecovery">
        <p class="recovery-hint">{{ t('auth.forgotPasswordHint') }}</p>
        <label class="form-field">
          <span>{{ t('auth.username') }}</span>
          <input v-model="recoveryForm.username" class="input" autocomplete="username" :placeholder="t('auth.usernamePlaceholder')" required />
        </label>
        <label class="form-field">
          <span>{{ t('auth.forgotPasswordNewPassword') }}</span>
          <input v-model="recoveryForm.newPassword" class="input" type="password" autocomplete="new-password" :placeholder="t('auth.passwordPlaceholder')" minlength="8" maxlength="128" required />
        </label>
        <label class="form-field">
          <span>{{ t('auth.forgotPasswordToken') }}</span>
          <input v-model="recoveryForm.bootstrapToken" class="input" type="password" autocomplete="off" required />
        </label>
        <div class="recovery-actions">
          <button type="button" class="text-btn" @click="showRecovery = false">{{ t('auth.forgotPasswordCancel') }}</button>
          <button class="btn-primary" :disabled="busy.recovery">
            {{ busy.recovery ? t('auth.forgotPasswordSubmitting') : t('auth.forgotPasswordSubmit') }}
          </button>
        </div>
      </form>

      <div class="status-card">
        <p>{{ t('auth.loginStatus') }}{{ token ? t('auth.loggedIn') : t('auth.loggedOut') }}</p>
        <button v-if="token" class="text-btn" @click="handleLogout">{{ t('nav.logout') }}</button>
      </div>
    </article>
  </div>
</template>

<script setup>
import { reactive, inject, computed, ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import { CircleCheck, LogIn } from "@lucide/vue";
import { api } from "../lib/api";
import { parseError } from "../utils/helpers";
import { useAuth } from "../stores/auth";

const { t } = useI18n();
const showMessage = inject("showMessage");
const router = useRouter();
const route = useRoute();
const { token, setAuthToken, canManageContent, logout, prepareForLogin } = useAuth();

const setupJustDone = computed(() => route.query.setup === "done");

const busy = reactive({
  login: false,
  recovery: false
});

const loginForm = reactive({
  username: "",
  password: ""
});

const totpStep = ref(false);
const totpCode = ref("");

function isTotpRequired(error) {
  return error?.response?.status === 401 && error?.response?.data?.detail === "totp_required";
}

async function completeLogin(payload) {
  const { data } = await api.post("/v1/auth/login", payload);
  setAuthToken(data.access_token, data.role, { newSession: true });

  showMessage(canManageContent.value ? t("auth.loginSuccess") : t("auth.loginSuccessLimited"));

  const redirect = typeof route.query.redirect === "string" && route.query.redirect.startsWith("/")
    ? route.query.redirect
    : { name: "dashboard" };
  router.push(redirect);
}

async function login() {
  busy.login = true;
  try {
    const previousSessionEnded = await prepareForLogin();
    if (!previousSessionEnded) {
      showMessage(t("auth.loginPrevSessionFail"), "error");
      return;
    }
    await completeLogin({ ...loginForm });
  } catch (error) {
    if (isTotpRequired(error)) {
      totpStep.value = true;
      totpCode.value = "";
      return;
    }
    showMessage(parseError(error), "error");
  } finally {
    busy.login = false;
  }
}

async function loginWithTotp() {
  const code = totpCode.value.trim();
  if (!code) return;
  busy.login = true;
  try {
    await completeLogin({ ...loginForm, totp_code: code });
  } catch (error) {
    if (isTotpRequired(error) || error?.response?.status === 401) {
      showMessage(t("loginTotp.invalid"), "error");
      return;
    }
    showMessage(parseError(error), "error");
  } finally {
    busy.login = false;
  }
}

function backToCredentials() {
  totpStep.value = false;
  totpCode.value = "";
}

const showRecovery = ref(false);
const recoveryForm = reactive({
  username: "",
  newPassword: "",
  bootstrapToken: ""
});

async function submitRecovery() {
  busy.recovery = true;
  try {
    await api.post(
      "/v1/auth/password-recovery",
      { username: recoveryForm.username, new_password: recoveryForm.newPassword },
      {
        headers: { "X-Bootstrap-Token": recoveryForm.bootstrapToken },
        skipAuthInvalidation: true
      }
    );
    showMessage(t("auth.forgotPasswordSuccess"), "info");
    showRecovery.value = false;
    recoveryForm.username = "";
    recoveryForm.newPassword = "";
    recoveryForm.bootstrapToken = "";
  } catch (error) {
    showMessage(parseError(error), "error");
  } finally {
    busy.recovery = false;
  }
}

async function handleLogout() {
  const serverEnded = await logout();
  showMessage(
    serverEnded ? t("auth.logoutSuccess") : t("auth.logoutPartialFail"),
    serverEnded ? "info" : "error"
  );
  router.push({ name: "dashboard" });
}
</script>

<style scoped>
.login-block {
  max-width: 480px;
  margin: 0 auto;
}

.login-view {
  min-height: calc(100dvh - 8rem);
  align-content: center;
  padding-bottom: 2rem;
}

.setup-success-banner {
  max-width: 480px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  border-radius: var(--radius-control);
  background: var(--mint-soft);
  border: 1px solid #a6d8cb;
  padding: 0.8rem 1rem;
  font-size: 0.88rem;
  color: #246e64;
  font-weight: 500;
  text-align: center;
}

.recovery-toggle-row {
  display: flex;
  justify-content: center;
  margin-top: 0.4rem;
}

.totp-hint {
  font-size: 0.82rem;
  color: var(--text-muted, #6b7280);
  line-height: 1.55;
  margin: 0 0 0.2rem;
}

.totp-input {
  text-align: center;
  letter-spacing: 0.18em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.totp-back {
  align-self: center;
}

.recovery-form {
  margin-top: 0.6rem;
  padding-top: 0.9rem;
  border-top: 1px dashed var(--border-color, rgba(0, 0, 0, 0.08));
}

.recovery-hint {
  font-size: 0.82rem;
  color: var(--text-muted, #6b7280);
  line-height: 1.55;
  margin: 0 0 0.2rem;
}

.recovery-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}
</style>
