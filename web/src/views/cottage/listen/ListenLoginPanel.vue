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
  <div class="login-panel">
    <button
      v-if="!showQrModal"
      type="button"
      class="login-btn"
      :class="{ 'login-btn--primary': !meLoggedIn }"
      @click="openQrLogin"
    >
      {{ meLoggedIn ? t("listenLogin.relogin") : t("listenLogin.login") }}
    </button>

    <button
      v-if="!showQrModal && !showImportModal"
      type="button"
      class="login-btn"
      @click="openImport"
    >
      {{ t("listenLogin.importCookie") }}
    </button>

    <button
      v-if="meLoggedIn && !showQrModal && !showImportModal"
      type="button"
      class="login-btn"
      @click="onLogout"
    >
      {{ t("listenLogin.logout") }}
    </button>

    <div v-if="showQrModal" class="qr-modal">
      <div class="qr-card glass-card">
        <h3>{{ t("listenLogin.qrTitle") }}</h3>
        <p v-if="qrError" class="qr-error">{{ qrError }}</p>
        <img
          v-if="qrImage"
          :src="qrImage"
          :alt="t('listenLogin.qrAlt')"
          class="qr-img"
        />
        <p v-else class="qr-loading">{{ t("listenLogin.qrLoading") }}</p>
        <p class="qr-status">{{ statusLabel }}</p>
        <div class="qr-actions">
          <button type="button" class="login-btn" @click="closeQr">{{ t("listenLogin.cancel") }}</button>
        </div>
      </div>
    </div>

    <div v-if="showImportModal" class="qr-modal">
      <div class="qr-card import-card glass-card">
        <h3>{{ t("listenLogin.importTitle") }}</h3>
        <!-- eslint-disable-next-line vue/no-v-html -- translation markup is bundled static content. -->
        <p class="import-hint" v-html="t('listenLogin.importHint')"></p>
        <ol class="import-steps">
          <!-- eslint-disable-next-line vue/no-v-html -- translation markup is bundled static content. -->
          <li v-html="t('listenLogin.step1')"></li>
          <!-- eslint-disable-next-line vue/no-v-html -- translation markup is bundled static content. -->
          <li v-html="t('listenLogin.step2')"></li>
          <!-- eslint-disable-next-line vue/no-v-html -- translation markup is bundled static content. -->
          <li v-html="t('listenLogin.step3')"></li>
        </ol>
        <textarea
          v-model="importText"
          class="import-input"
          rows="4"
          placeholder="MUSIC_U=xxxxxxxx..."
        ></textarea>
        <p v-if="importError" class="qr-error">{{ importError }}</p>
        <p v-if="importOk" class="import-ok">{{ importOk }}</p>
        <div class="qr-actions import-actions">
          <button type="button" class="login-btn" @click="closeImport">{{ t("listenLogin.cancel") }}</button>
          <button
            type="button"
            class="login-btn login-btn--primary"
            :disabled="importing || !importText.trim()"
            @click="submitImport"
          >
            {{ importing ? t("listenLogin.importing") : t("listenLogin.importBtn") }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  fetchListenQrKey,
  fetchListenQrStatus,
  importListenCookie,
  listenLogout
} from "../../../lib/api";

const { t } = useI18n();

const emit = defineEmits(["login-success", "logout"]);

const showQrModal = ref(false);
const qrImage = ref("");
const qrUnikey = ref("");
const qrStatus = ref("waiting");
const qrError = ref("");
let pollTimer = null;

const showImportModal = ref(false);
const importText = ref("");
const importError = ref("");
const importOk = ref("");
const importing = ref(false);

const statusLabel = computed(() => {
  switch (qrStatus.value) {
    case "waiting":
      return t("listenLogin.statusWaiting");
    case "scanned":
      return t("listenLogin.statusScanned");
    case "confirmed":
      return t("listenLogin.statusConfirmed");
    case "expired":
      return t("listenLogin.statusExpired");
    default:
      return "";
  }
});

async function openQrLogin() {
  qrError.value = "";
  qrImage.value = "";
  qrStatus.value = "waiting";
  showQrModal.value = true;
  try {
    const data = await fetchListenQrKey();
    qrUnikey.value = data.unikey;
    qrImage.value = data.qr_image_data_url;
    startPolling();
  } catch (e) {
    qrError.value = e?.response?.data?.detail?.message || t("listenLogin.errOpenLogin");
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    if (!showQrModal.value || !qrUnikey.value) return;
    try {
      const data = await fetchListenQrStatus(qrUnikey.value);
      qrStatus.value = data.status;
      if (data.status === "confirmed") {
        stopPolling();
        emit("login-success");
        setTimeout(() => closeQr(), 1500);
      } else if (data.status === "expired") {
        stopPolling();
        // Auto-refresh expired QR after a short pause.
        setTimeout(() => {
          if (showQrModal.value) openQrLogin();
        }, 1500);
      }
    } catch (e) {
      qrError.value = e?.response?.data?.detail?.message || t("listenLogin.errQrStatus");
      stopPolling();
    }
  }, 2000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function closeQr() {
  showQrModal.value = false;
  stopPolling();
  qrImage.value = "";
  qrUnikey.value = "";
  qrStatus.value = "waiting";
}

function openImport() {
  importText.value = "";
  importError.value = "";
  importOk.value = "";
  importing.value = false;
  showImportModal.value = true;
}

function closeImport() {
  showImportModal.value = false;
  importText.value = "";
  importError.value = "";
  importOk.value = "";
  importing.value = false;
}

async function submitImport() {
  const raw = importText.value.trim();
  if (!raw || importing.value) return;
  importError.value = "";
  importOk.value = "";
  importing.value = true;
  try {
    const data = await importListenCookie(raw);
    importOk.value = data?.message || t("listenLogin.importOkMsg");
    emit("login-success");
    setTimeout(() => closeImport(), 1200);
  } catch (e) {
    importError.value =
      e?.response?.data?.detail?.message || t("listenLogin.errImport");
  } finally {
    importing.value = false;
  }
}

async function onLogout() {
  try {
    await listenLogout();
    emit("logout");
  } catch (_) {
    /* ignore */
  }
}

onUnmounted(stopPolling);
</script>

<style scoped>
.login-panel {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.login-btn {
  min-height: 44px;
  padding: 0.55rem 1.05rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.5);
  background: rgba(255, 255, 255, 0.85);
  color: #3d4665;
  font-size: 0.84rem;
  font-weight: 600;
  cursor: pointer;
}

.login-btn--primary {
  border-color: transparent;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
}

.qr-modal {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 1rem;
}

.qr-card {
  width: 100%;
  max-width: 320px;
  padding: 1.5rem 1.5rem 1.2rem;
  text-align: center;
}

.qr-card h3 {
  margin: 0 0 0.85rem;
  color: #2f3754;
}

.qr-img {
  width: 200px;
  height: 200px;
  display: block;
  margin: 0 auto 0.7rem;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.qr-loading {
  margin: 1.4rem 0;
  color: #64748b;
}

.qr-status {
  margin: 0 0 0.7rem;
  color: #475569;
  font-size: 0.88rem;
}

.qr-error {
  margin: 0 0 0.6rem;
  color: #dc2626;
  font-size: 0.84rem;
}

.qr-actions {
  display: flex;
  justify-content: center;
}

.import-card {
  max-width: 380px;
  text-align: left;
}

.import-hint {
  margin: 0 0 0.6rem;
  color: #475569;
  font-size: 0.84rem;
  line-height: 1.5;
}

.import-steps {
  margin: 0 0 0.8rem;
  padding-left: 1.2rem;
  color: #475569;
  font-size: 0.82rem;
  line-height: 1.6;
}

.import-steps code,
.import-hint code {
  background: rgba(148, 163, 184, 0.18);
  padding: 0.05rem 0.3rem;
  border-radius: 4px;
  font-size: 0.78rem;
}

.import-input {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  padding: 0.55rem 0.7rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.5);
  font-size: 0.8rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  margin-bottom: 0.5rem;
}

.import-ok {
  margin: 0 0 0.5rem;
  color: #16a34a;
  font-size: 0.84rem;
}

.import-actions {
  justify-content: flex-end;
  gap: 0.5rem;
}

.login-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
