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
  <div class="content-section cottage-checkin">
    <div class="cottage-checkin-header">
      <h2>{{ t('cottageCheckIn.title') }}</h2>
      <router-link to="/cottage/check-in/history" class="cottage-checkin-history">
        {{ t('cottageCheckIn.history') }}
      </router-link>
    </div>

    <CheckInLatestCard :item="latest" :loading="loading" />

    <CheckInComposer @submitted="handleSubmitted" />
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { fetchLatestCheckin } from "../../../lib/api";
import CheckInLatestCard from "./CheckInLatestCard.vue";
import CheckInComposer from "./CheckInComposer.vue";

const { t } = useI18n();

const latest = ref(null);
const loading = ref(true);

async function loadLatest() {
  loading.value = true;
  try {
    const data = await fetchLatestCheckin();
    latest.value = data?.item ?? null;
  } catch (_error) {
    // Network failure leaves the card in empty state.
    latest.value = null;
  } finally {
    loading.value = false;
  }
}

function handleSubmitted() {
  // After self-submit, the latest endpoint still returns the counterpart's
  // newest record (server filter `author_id != current_user.id`). Refresh
  // anyway so the card reflects the post-submit state truthfully.
  loadLatest();
}

onMounted(loadLatest);
</script>

<style scoped>
.cottage-checkin {
  display: grid;
  gap: 1rem;
}

.cottage-checkin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.2rem 0.2rem 0;
}

.cottage-checkin-header h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #2f3754;
}

.cottage-checkin-history {
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

.cottage-checkin-history:hover {
  border-color: rgba(143, 155, 255, 0.6);
  color: #2f3754;
}
</style>
