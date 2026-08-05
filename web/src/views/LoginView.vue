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
        <h2>{{ t('auth.loginTitle') }}</h2>
      </div>
      <form class="form-stack" @submit.prevent="login">
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

      <div class="status-card">
        <p>{{ t('auth.loginStatus') }}{{ token ? t('auth.loggedIn') : t('auth.loggedOut') }}</p>
        <button v-if="token" class="text-btn" @click="handleLogout">{{ t('nav.logout') }}</button>
      </div>
    </article>
  </div>
</template>

<script setup>
import { reactive, inject, computed } from "vue";
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
  login: false
});

const loginForm = reactive({
  username: "",
  password: ""
});

async function login() {
  busy.login = true;
  try {
    const previousSessionEnded = await prepareForLogin();
    if (!previousSessionEnded) {
      showMessage(t("auth.loginPrevSessionFail"), "error");
      return;
    }
    const { data } = await api.post("/v1/auth/login", loginForm);
    setAuthToken(data.access_token, data.role, { newSession: true });

    showMessage(canManageContent.value ? t("auth.loginSuccess") : t("auth.loginSuccessLimited"));

    const redirect = typeof route.query.redirect === "string" && route.query.redirect.startsWith("/")
      ? route.query.redirect
      : { name: "dashboard" };
    router.push(redirect);
  } catch (error) {
    showMessage(parseError(error), "error");
  } finally {
    busy.login = false;
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
</style>
