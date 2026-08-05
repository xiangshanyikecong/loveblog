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
  <div class="content-section notifications-view">
    <ModuleTabs :items="interactionTabs" :label="t('notifications.navLabel')" />

    <div class="section-header">
      <div>
        <h2>{{ t('notifications.title') }}</h2>
        <p class="sub-text">{{ t('notifications.desc') }}</p>
      </div>
      <div class="toolbar">
        <label class="check">
          <input v-model="unreadOnly" type="checkbox" @change="loadNotifications" />
          {{ t('notifications.unreadOnly') }}
        </label>
        <button class="ghost-btn" :disabled="loading" @click="loadNotifications">
          {{ loading ? t('notifications.refreshing') : t('notifications.refresh') }}
        </button>
        <button class="ghost-btn" :disabled="!unreadCount" @click="readAll">{{ t('notifications.readAll') }}</button>
      </div>
    </div>

    <section class="glass-card section-block pwa-panel">
      <div>
        <h3>{{ t('notifications.pwaTitle') }}</h3>
        <p class="sub-text">
          {{ t('notifications.pwaDesc') }}
        </p>
      </div>
      <div class="pwa-status-grid">
        <div class="pwa-status-item">
          <span class="pwa-status-label">{{ t('notifications.installStatus') }}</span>
          <strong>{{ installStatusText }}</strong>
        </div>
        <div class="pwa-status-item">
          <span class="pwa-status-label">{{ t('notifications.permissionLabel') }}</span>
          <strong>{{ permissionText }}</strong>
        </div>
        <div class="pwa-status-item">
          <span class="pwa-status-label">{{ t('notifications.pushServer') }}</span>
          <strong>{{ pushServerEnabled ? t('notifications.pushServerOn') : t('notifications.pushServerOff') }}</strong>
        </div>
        <div class="pwa-status-item">
          <span class="pwa-status-label">{{ t('notifications.subscriptionLabel') }}</span>
          <strong>{{ hasPushSubscription ? t('notifications.subscribed') : t('notifications.notSubscribed') }}</strong>
        </div>
      </div>
      <div class="toolbar">
        <button
          v-if="canInstallApp"
          class="ghost-btn"
          :disabled="pushBusy"
          @click="handleInstall"
        >
          {{ t('notifications.installApp') }}
        </button>
        <button
          v-if="pushSupported && !hasPushSubscription"
          class="ghost-btn"
          :disabled="pushBusy"
          @click="handleEnablePush"
        >
          {{ pushBusy ? t('notifications.enabling') : t('notifications.enablePush') }}
        </button>
        <button
          v-if="pushSupported && hasPushSubscription"
          class="ghost-btn"
          :disabled="pushBusy"
          @click="handleDisablePush"
        >
          {{ pushBusy ? t('notifications.disabling') : t('notifications.disablePush') }}
        </button>
        <button class="ghost-btn" :disabled="pushBusy" @click="refreshPushStatus">
          {{ t('notifications.refreshPush') }}
        </button>
      </div>
      <p v-if="!pushSupported" class="sub-text">
        {{ t('notifications.pushUnsupported') }}
      </p>
    </section>

    <section class="glass-card section-block">
      <div v-if="!items.length && !loading" class="empty-state">{{ t('notifications.empty') }}</div>
      <div v-else class="notification-list">
        <article
          v-for="item in items"
          :key="item.nid"
          class="notification-item"
          :class="{ 'notification-item--unread': !item.is_read }"
        >
          <div class="notification-main">
            <div class="notification-title-row">
              <span class="type-dot" :class="`type-dot--${typeClass(item.type)}`" />
              <h3>{{ item.title }}</h3>
            </div>
            <p v-if="item.body" class="notification-body">{{ item.body }}</p>
            <p class="notification-meta">{{ formatTime(item.created_at) }}</p>
          </div>
          <div class="notification-actions">
            <router-link v-if="item.link" :to="item.link" class="ghost-btn compact" @click="markRead(item)">
              {{ t('notifications.view') }}
            </router-link>
            <button v-if="!item.is_read" class="ghost-btn compact" @click="markRead(item)">{{ t('notifications.markRead') }}</button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import ModuleTabs from "../components/ModuleTabs.vue";
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from "../lib/api";
import {
  disablePushNotifications,
  enablePushNotifications,
  promptInstall,
  refreshPushState,
  usePwa
} from "../lib/pwa";
import { parseError } from "../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage");
const items = ref([]);
const unreadCount = ref(0);
const unreadOnly = ref(false);
const loading = ref(false);
const interactionTabs = computed(() => [
  { label: t("nav.messages"), to: "/messages" },
  { label: t("nav.notifications"), to: "/notifications" }
]);
const {
  canInstallApp,
  hasPushSubscription,
  isInstalled,
  pushBusy,
  pushPermission,
  pushServerEnabled,
  pushSupported
} = usePwa();

const installStatusText = computed(() => {
  if (isInstalled.value) return t("notifications.installed");
  if (canInstallApp.value) return t("notifications.installable");
  return t("notifications.noInstallEntry");
});

const permissionText = computed(() => {
  if (pushPermission.value === "granted") return t("notifications.permissionGranted");
  if (pushPermission.value === "denied") return t("notifications.permissionDenied");
  return t("notifications.permissionPending");
});

function typeClass(type) {
  if (type.startsWith("backup")) return "backup";
  if (type.startsWith("event")) return "event";
  if (type.startsWith("comment")) return "comment";
  return "message";
}

function formatTime(raw) {
  if (!raw) return "";
  return new Date(raw).toLocaleString(undefined, { hour12: false });
}

async function loadNotifications() {
  loading.value = true;
  try {
    const data = await fetchNotifications({ unread_only: unreadOnly.value, limit: 80 });
    items.value = data.items || [];
    unreadCount.value = data.unread_count || 0;
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    loading.value = false;
  }
}

async function markRead(item) {
  if (item.is_read) return;
  try {
    await markNotificationRead(item.nid);
    item.is_read = true;
    unreadCount.value = Math.max(0, unreadCount.value - 1);
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

async function readAll() {
  try {
    await markAllNotificationsRead();
    await loadNotifications();
    showMessage?.(t("notifications.allReadToast"));
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

async function refreshPushStatus() {
  try {
    await refreshPushState();
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

async function handleInstall() {
  const accepted = await promptInstall();
  if (accepted) {
    showMessage?.(t("notifications.installTriggeredToast"));
  }
}

async function handleEnablePush() {
  try {
    await enablePushNotifications();
    showMessage?.(t("notifications.pushEnabledToast"));
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

async function handleDisablePush() {
  try {
    await disablePushNotifications();
    showMessage?.(t("notifications.pushDisabledToast"));
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

onMounted(async () => {
  await Promise.all([loadNotifications(), refreshPushStatus()]);
});
</script>
