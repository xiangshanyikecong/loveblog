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
  <div class="content-section storage-root">
    <section class="glass-card section-block">
      <div class="section-header">
        <div>
          <h2>{{ t("adminStorage.title") }}</h2>
          <p class="section-subtitle">{{ t("adminStorage.subtitle") }}</p>
        </div>
        <button class="primary-btn" :disabled="loading" @click="load">
          {{ loading ? t("adminStorage.loading") : t("adminStorage.refresh") }}
        </button>
      </div>

      <p v-if="loadError" class="error-text">{{ t("adminStorage.loadFailed") }}</p>

      <template v-if="usage">
        <div class="storage-grid">
          <!-- 磁盘 -->
          <div class="storage-card">
            <h3 class="card-title">{{ t("adminStorage.diskTitle") }}</h3>
            <div class="disk-bar">
              <div class="disk-bar-fill" :style="{ width: `${diskPercent}%` }"></div>
            </div>
            <p class="disk-percent">{{ diskPercent.toFixed(1) }}%</p>
            <ul class="stat-list">
              <li>
                <span>{{ t("adminStorage.used") }}</span>
                <span class="mono">{{ formatBytes(usage.disk?.used_bytes) }}</span>
              </li>
              <li>
                <span>{{ t("adminStorage.total") }}</span>
                <span class="mono">{{ formatBytes(usage.disk?.total_bytes) }}</span>
              </li>
              <li>
                <span>{{ t("adminStorage.free") }}</span>
                <span class="mono">{{ formatBytes(usage.disk?.free_bytes) }}</span>
              </li>
            </ul>
          </div>

          <!-- 上传文件 -->
          <div class="storage-card">
            <h3 class="card-title">{{ t("adminStorage.uploadsTitle") }}</h3>
            <p class="big-stat mono">{{ formatBytes(usage.uploads?.total_bytes) }}</p>
            <p class="stat-sub">
              {{ t("adminStorage.files", { count: usage.uploads?.file_count ?? 0 }) }}
            </p>
          </div>

          <!-- 数据库 -->
          <div class="storage-card">
            <h3 class="card-title">{{ t("adminStorage.dbTitle") }}</h3>
            <p class="big-stat mono">{{ databaseSizeLabel }}</p>
          </div>
        </div>

        <!-- 分类占用 -->
        <div class="breakdown">
          <h3 class="card-title">{{ t("adminStorage.breakdownTitle") }}</h3>
          <table class="breakdown-table">
            <thead>
              <tr>
                <th>{{ t("adminStorage.category") }}</th>
                <th>{{ t("adminStorage.size") }}</th>
                <th>{{ t("adminStorage.count") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!sortedBreakdown.length">
                <td colspan="3" class="muted-tip">{{ t("common.noData") }}</td>
              </tr>
              <tr v-for="row in sortedBreakdown" :key="row.category">
                <td>{{ row.category }}</td>
                <td class="mono">{{ formatBytes(row.bytes) }}</td>
                <td>{{ row.file_count ?? 0 }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <p v-else-if="!loading && !loadError" class="muted-tip">{{ t("adminStorage.loadFailed") }}</p>
    </section>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { fetchStorageUsage } from "../lib/api";
import { t } from "../locales";
import { parseError } from "../utils/helpers";

const showMessage = inject("showMessage", () => {});

const usage = ref(null);
const loading = ref(false);
const loadError = ref(false);

const diskPercent = computed(() => {
  const disk = usage.value?.disk;
  if (!disk) return 0;
  if (typeof disk.percent === "number") return disk.percent;
  const total = Number(disk.total_bytes) || 0;
  const used = Number(disk.used_bytes) || 0;
  return total > 0 ? (used / total) * 100 : 0;
});

const databaseSizeLabel = computed(() => {
  const size = usage.value?.database?.size_bytes;
  return size != null ? formatBytes(size) : t("adminStorage.unknown");
});

const sortedBreakdown = computed(() =>
  [...(usage.value?.breakdown || [])].sort((a, b) => (Number(b.bytes) || 0) - (Number(a.bytes) || 0))
);

function formatBytes(bytes) {
  const n = Number(bytes);
  if (!Number.isFinite(n) || n <= 0) return "0 B";
  if (n < 1024) return `${Math.round(n)} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = n / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
}

async function load() {
  loading.value = true;
  loadError.value = false;
  try {
    usage.value = await fetchStorageUsage();
  } catch (error) {
    loadError.value = true;
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.storage-root {
  display: grid;
  gap: 1.5rem;
}

.section-subtitle {
  margin: 0.25rem 0 0;
  color: #64748b;
  font-size: 0.86rem;
  line-height: 1.55;
}

.primary-btn {
  border: none;
  border-radius: 999px;
  color: #fff;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 700;
  padding: 0.48rem 1rem;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  box-shadow: 0 10px 18px rgb(143 155 255 / 0.22);
  transition: opacity 0.2s, transform 0.15s;
}

.primary-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.storage-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.9rem;
}

.storage-card {
  display: grid;
  align-content: start;
  gap: 0.5rem;
  background: rgb(248 250 255 / 0.85);
  border: 1px solid rgb(148 163 184 / 0.3);
  border-radius: 14px;
  padding: 0.95rem 1.1rem;
}

.card-title {
  margin: 0;
  color: #2f3754;
  font-size: 0.92rem;
  font-weight: 800;
}

.disk-bar {
  height: 10px;
  border-radius: 999px;
  background: rgb(148 163 184 / 0.25);
  overflow: hidden;
}

.disk-bar-fill {
  height: 100%;
  min-width: 2px;
  border-radius: 999px;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  transition: width 0.3s ease;
}

.disk-percent {
  margin: 0;
  color: #dc4b78;
  font-size: 0.95rem;
  font-weight: 800;
}

.stat-list {
  display: grid;
  gap: 0.3rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.stat-list li {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.6rem;
  font-size: 0.82rem;
  color: #475569;
}

.stat-list .mono {
  color: #2f3754;
  font-weight: 700;
}

.big-stat {
  margin: 0;
  color: #2f3754;
  font-size: 1.35rem;
  font-weight: 800;
}

.stat-sub {
  margin: 0;
  color: #64748b;
  font-size: 0.8rem;
}

.breakdown {
  margin-top: 1.2rem;
  display: grid;
  gap: 0.55rem;
}

.breakdown-table {
  width: 100%;
  border-collapse: collapse;
  background: rgb(248 250 255 / 0.8);
  border: 1px solid rgb(148 163 184 / 0.25);
  border-radius: 12px;
  overflow: hidden;
  font-size: 0.84rem;
}

.breakdown-table th,
.breakdown-table td {
  padding: 0.55rem 0.85rem;
  text-align: left;
}

.breakdown-table th {
  background: rgb(143 155 255 / 0.12);
  color: #4f5ecf;
  font-size: 0.78rem;
  font-weight: 800;
}

.breakdown-table tbody tr + tr {
  border-top: 1px solid rgb(148 163 184 / 0.18);
}

.breakdown-table td {
  color: #334155;
}

.error-text {
  color: #dc2626;
  font-size: 0.82rem;
  margin: 0.5rem 0;
}

.muted-tip {
  color: #94a3b8;
  font-size: 0.85rem;
  margin: 0.5rem 0;
}

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
