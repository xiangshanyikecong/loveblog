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
  <Transition name="heartbeat-slide">
    <div
      v-if="isDisconnected"
      class="frontend-heartbeat"
      role="alert"
      aria-live="assertive"
    >
      <div>
        <p class="frontend-heartbeat-title">{{ t("heartbeat.title") }}</p>
        <p class="frontend-heartbeat-text">{{ t("heartbeat.text") }}</p>
      </div>
      <button class="frontend-heartbeat-btn" type="button" :disabled="isChecking" @click="checkNow">
        {{ isChecking ? t("heartbeat.checking") : t("heartbeat.recheck") }}
      </button>
    </div>
  </Transition>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const CHECK_INTERVAL_MS = 5000;
const REQUEST_TIMEOUT_MS = 2500;
const FAILURE_THRESHOLD = 2;

const isDisconnected = ref(false);
const isChecking = ref(false);

let failureCount = 0;
let intervalId = null;
let currentController = null;

function getHeartbeatUrl() {
  const basePath = import.meta.env.BASE_URL || "/";
  const url = new URL(basePath, window.location.origin);
  url.searchParams.set("__frontend_heartbeat", String(Date.now()));
  return url.toString();
}

async function checkFrontend() {
  if (window.location.protocol === "file:" || isChecking.value) {
    return;
  }

  isChecking.value = true;
  currentController = new AbortController();

  const timeoutId = window.setTimeout(() => {
    currentController?.abort();
  }, REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(getHeartbeatUrl(), {
      cache: "no-store",
      credentials: "same-origin",
      signal: currentController.signal
    });

    if (!response.ok) {
      throw new Error(`Frontend heartbeat failed: ${response.status}`);
    }

    failureCount = 0;
    isDisconnected.value = false;
  } catch {
    failureCount += 1;
    if (failureCount >= FAILURE_THRESHOLD) {
      isDisconnected.value = true;
    }
  } finally {
    window.clearTimeout(timeoutId);
    currentController = null;
    isChecking.value = false;
  }
}

function checkNow() {
  failureCount = 0;
  checkFrontend();
}

onMounted(() => {
  checkFrontend();
  intervalId = window.setInterval(checkFrontend, CHECK_INTERVAL_MS);
});

onUnmounted(() => {
  if (intervalId !== null) {
    window.clearInterval(intervalId);
  }
  currentController?.abort();
});
</script>

<style scoped>
.frontend-heartbeat {
  position: fixed;
  left: 50%;
  top: 1rem;
  z-index: 9999;
  width: min(calc(100vw - 2rem), 520px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid rgb(248 113 113 / 0.45);
  border-radius: 14px;
  background: rgb(255 247 237 / 0.96);
  box-shadow: 0 18px 42px rgb(127 29 29 / 0.18);
  color: #7f1d1d;
  padding: 0.85rem 0.95rem;
  transform: translateX(-50%);
}

.frontend-heartbeat-title {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 700;
}

.frontend-heartbeat-text {
  margin: 0.22rem 0 0;
  color: #991b1b;
  font-size: 0.78rem;
  line-height: 1.45;
}

.frontend-heartbeat-btn {
  flex: 0 0 auto;
  border: 0;
  border-radius: 10px;
  background: #dc2626;
  color: #fff;
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 700;
  padding: 0.5rem 0.72rem;
}

.frontend-heartbeat-btn:disabled {
  cursor: progress;
  opacity: 0.72;
}

.heartbeat-slide-enter-active,
.heartbeat-slide-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.heartbeat-slide-enter-from,
.heartbeat-slide-leave-to {
  opacity: 0;
  transform: translate(-50%, -0.5rem);
}

@media (max-width: 560px) {
  .frontend-heartbeat {
    align-items: stretch;
    flex-direction: column;
  }

  .frontend-heartbeat-btn {
    width: 100%;
  }
}
</style>
