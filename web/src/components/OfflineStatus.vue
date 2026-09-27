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
  <div
    v-if="visible"
    :class="['offline-banner', bannerTone]"
    role="status"
  >
    <button type="button" class="offline-banner-main" @click="panelOpen = !panelOpen">
      <span class="offline-banner-dot" aria-hidden="true"></span>
      <span class="offline-banner-text">{{ bannerText }}</span>
      <span v-if="hasQueue" class="offline-banner-caret" aria-hidden="true">{{ panelOpen ? '▾' : '▸' }}</span>
    </button>
    <button
      v-if="hasQueue && !offline"
      type="button"
      class="offline-banner-action"
      :disabled="flushing"
      @click="syncNow"
    >
      {{ flushing ? t('offline.syncing') : t('offline.syncNow') }}
    </button>
  </div>

  <div v-if="panelOpen && visible" class="offline-panel" role="dialog" :aria-label="t('offline.queueTitle')">
    <div class="offline-panel-header">
      <strong>{{ t('offline.queueTitle') }}</strong>
      <span v-if="lastSyncLabel" class="offline-panel-synced">{{ t('offline.lastSync', { time: lastSyncLabel }) }}</span>
    </div>

    <p v-if="authPaused" class="offline-panel-note offline-panel-note--warn">
      {{ t('offline.authPaused') }}
    </p>

    <ul v-if="items.length" class="offline-panel-list">
      <li v-for="item in items" :key="item.id" :class="['offline-item', `offline-item--${item.status}`]">
        <div class="offline-item-main">
          <span class="offline-item-kind">{{ kindLabel(item.kind) }}</span>
          <span class="offline-item-time">{{ formatTime(item.createdAt) }}</span>
          <span class="offline-item-status">
            {{ item.status === 'conflict' ? t('offline.conflict') : item.status === 'dead' ? t('offline.dead') : t('offline.pendingLabel') }}
          </span>
        </div>
        <p v-if="item.lastError" class="offline-item-error">{{ item.lastError }}</p>
        <div class="offline-item-actions">
          <button
            v-if="item.status === 'conflict'"
            type="button"
            class="offline-btn offline-btn--primary"
            @click="overwrite(item)"
          >
            {{ t('offline.overwrite') }}
          </button>
          <button
            v-if="item.status === 'dead'"
            type="button"
            class="offline-btn"
            @click="retry(item)"
          >
            {{ t('offline.retry') }}
          </button>
          <button type="button" class="offline-btn" @click="copyItem(item)">
            {{ copiedId === item.id ? t('offline.copied') : t('offline.copy') }}
          </button>
          <button type="button" class="offline-btn offline-btn--danger" @click="drop(item)">
            {{ t('offline.drop') }}
          </button>
        </div>
      </li>
    </ul>
    <p v-else class="offline-panel-note">{{ t('offline.empty') }}</p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import {
  dropOutboxItem,
  flushOutbox,
  listOutboxItems,
  overwriteConflict,
  retryDeadItem,
  resumeOutboxAfterAuth,
  useOutbox,
} from "../lib/offline/outbox";

const { t } = useI18n();
const { pendingCount, flushing, authPaused, lastQueueEmptyAt, isOnline } = useOutbox();

const offline = computed(() => !isOnline.value);
const panelOpen = ref(false);
const items = ref([]);
const copiedId = ref(null);

const hasQueue = computed(() => pendingCount.value > 0);
const visible = computed(() => offline.value || hasQueue.value || authPaused.value);
const bannerTone = computed(() => (authPaused.value ? "offline-banner--warn" : offline.value ? "offline-banner--offline" : "offline-banner--pending"));

const bannerText = computed(() => {
  if (authPaused.value) return t("offline.authPaused");
  if (offline.value) {
    return hasQueue.value
      ? `${t("offline.offlineBanner")} · ${t("offline.pending", { count: pendingCount.value })}`
      : t("offline.offlineBanner");
  }
  return t("offline.pending", { count: pendingCount.value });
});

const lastSyncLabel = computed(() =>
  lastQueueEmptyAt.value ? formatTime(lastQueueEmptyAt.value) : ""
);

async function refresh() {
  items.value = await listOutboxItems();
}

function kindLabel(kind) {
  return t(`offline.kind.${kind}`);
}

function formatTime(ms) {
  return new Date(ms).toLocaleString();
}

function syncNow() {
  if (authPaused.value) resumeOutboxAfterAuth();
  else flushOutbox();
}

async function overwrite(item) {
  await overwriteConflict(item);
  await refresh();
}

async function retry(item) {
  await retryDeadItem(item);
  await refresh();
}

async function drop(item) {
  await dropOutboxItem(item);
  await refresh();
}

async function copyItem(item) {
  const summary = `${kindLabel(item.kind)} ${item.method} ${item.url}\n${item.body || ""}`;
  try {
    await navigator.clipboard.writeText(summary);
    copiedId.value = item.id;
    setTimeout(() => {
      copiedId.value = null;
    }, 1500);
  } catch {
    // 剪贴板不可用时静默（面板里内容本身可见）。
  }
}

watch(pendingCount, () => refresh());
watch(authPaused, () => refresh());
onMounted(() => refresh());
</script>

<style scoped>
.offline-banner {
  position: fixed;
  top: 76px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 25;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  max-width: min(640px, calc(100vw - 2rem));
  padding: 0.3rem 0.4rem 0.3rem 0.8rem;
  border-radius: 999px;
  border: 1px solid #f2d3a0;
  background: #fff8ec;
  color: #8a5a1c;
  font-size: 0.78rem;
  box-shadow: 0 8px 18px rgb(90 66 28 / 0.12);
}

.offline-banner--offline {
  border-color: #f2d3a0;
  background: #fff8ec;
  color: #8a5a1c;
}

.offline-banner--pending {
  border-color: #b9d9d2;
  background: #edf8f5;
  color: #23685f;
}

.offline-banner--warn {
  border-color: #efb9c8;
  background: #fff2f5;
  color: #9f3f55;
}

.offline-banner-main {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
  padding: 0.15rem 0;
}

.offline-banner-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.75;
  flex: 0 0 auto;
}

.offline-banner-text {
  font-weight: 600;
}

.offline-banner-caret {
  opacity: 0.7;
}

.offline-banner-action {
  border: 1px solid currentColor;
  border-radius: 999px;
  background: transparent;
  color: inherit;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  cursor: pointer;
}

.offline-banner-action:disabled {
  opacity: 0.6;
  cursor: default;
}

.offline-panel {
  position: fixed;
  top: 112px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 25;
  width: min(640px, calc(100vw - 2rem));
  max-height: 60vh;
  overflow-y: auto;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--surface-raised, #fff);
  box-shadow: 0 18px 40px rgb(30 41 59 / 0.16);
  padding: 0.9rem 1rem;
}

.offline-panel-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.offline-panel-synced {
  font-size: 0.72rem;
  color: var(--text-soft, #64748b);
}

.offline-panel-note {
  font-size: 0.8rem;
  color: var(--text-soft, #64748b);
  margin: 0.25rem 0;
}

.offline-panel-note--warn {
  color: #9f3f55;
}

.offline-panel-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.5rem;
}

.offline-item {
  border: 1px solid var(--border-subtle, #e2e8f0);
  border-radius: var(--radius-control, 8px);
  padding: 0.55rem 0.7rem;
  font-size: 0.78rem;
}

.offline-item--dead {
  border-color: #efb9c8;
  background: #fff7f9;
}

.offline-item--conflict {
  border-color: #f2d3a0;
  background: #fffaf1;
}

.offline-item-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.offline-item-kind {
  font-weight: 700;
}

.offline-item-time,
.offline-item-status {
  color: var(--text-soft, #64748b);
}

.offline-item-error {
  margin: 0.3rem 0 0;
  color: #9f3f55;
  font-size: 0.72rem;
  word-break: break-all;
}

.offline-item-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.45rem;
}

.offline-btn {
  border: 1px solid var(--border-strong, #cbd5e1);
  border-radius: 999px;
  background: var(--surface-raised, #fff);
  color: var(--text-main, #1e293b);
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.22rem 0.65rem;
  cursor: pointer;
}

.offline-btn--primary {
  border-color: #efc3d1;
  background: var(--brand-soft, #fdf0f4);
  color: var(--brand-strong, #bd5a7d);
}

.offline-btn--danger {
  color: #b91c1c;
  border-color: #f3c4c4;
}

@media (max-width: 768px) {
  .offline-banner {
    top: 70px;
  }

  .offline-panel {
    top: 104px;
  }
}
</style>
