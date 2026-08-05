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
  <div class="content-section history">
    <div class="history-header">
      <h2>{{ t('cottageCheckInHistory.title') }}</h2>
      <router-link to="/cottage/check-in" class="history-back">{{ t('cottageCheckInHistory.back') }}</router-link>
    </div>

    <p v-if="loading && !items.length" class="history-empty">{{ t('cottageCheckInHistory.loading') }}</p>
    <p v-else-if="!items.length" class="history-empty">{{ t('cottageCheckInHistory.partnerEmpty') }}</p>

    <div v-else class="history-list">
      <CheckInLatestCard
        v-for="record in items"
        :key="record.cid"
        :item="record"
        :loading="false"
      />
    </div>

    <div v-if="hasNext" class="history-actions">
      <button
        type="button"
        class="history-load-more"
        :disabled="loading"
        @click="loadMore"
      >
        {{ loading ? t('cottageCheckInHistory.loadingMore') : t('cottageCheckInHistory.loadMore') }}
      </button>
    </div>

    <p v-if="errorMsg" class="history-error">{{ errorMsg }}</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { fetchCheckins } from "../../lib/api";
import CheckInLatestCard from "./checkin/CheckInLatestCard.vue";

const { t } = useI18n();

const items = ref([]);
const page = ref(0);
const pageSize = 20;
const hasNext = ref(false);
const loading = ref(false);
const errorMsg = ref("");

async function loadPage(targetPage) {
  loading.value = true;
  errorMsg.value = "";
  try {
    const data = await fetchCheckins({
      page: targetPage,
      page_size: pageSize
    });
    if (targetPage === 1) {
      items.value = data.items || [];
    } else {
      items.value = items.value.concat(data.items || []);
    }
    page.value = data.page;
    hasNext.value = !!data.has_next;
  } catch (e) {
    errorMsg.value = e?.response?.data?.detail || t("cottageCheckInHistory.loadFailed");
  } finally {
    loading.value = false;
  }
}

function loadMore() {
  if (loading.value || !hasNext.value) return;
  loadPage(page.value + 1);
}

onMounted(() => loadPage(1));
</script>

<style scoped>
.history {
  display: grid;
  gap: 1rem;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.2rem 0.2rem 0;
}

.history-header h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #2f3754;
}

.history-back {
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
}

.history-back:hover {
  border-color: rgba(143, 155, 255, 0.6);
  color: #2f3754;
}

.history-list {
  display: grid;
  gap: 0.75rem;
}

.history-empty {
  margin: 0;
  text-align: center;
  color: #94a3b8;
  font-size: 0.92rem;
  padding: 1.2rem 0;
}

.history-actions {
  display: flex;
  justify-content: center;
}

.history-load-more {
  min-height: 44px;
  padding: 0.55rem 1.4rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.5);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  font-size: 0.86rem;
  cursor: pointer;
}

.history-load-more:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.history-error {
  margin: 0;
  text-align: center;
  font-size: 0.84rem;
  color: #dc2626;
}
</style>
