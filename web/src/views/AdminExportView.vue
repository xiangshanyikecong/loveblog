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
  <div class="content-section backup-root">
    <section class="glass-card section-block">
      <div class="section-header">
        <div>
          <h2>{{ t("adminExport.title") }}</h2>
          <p class="section-subtitle">{{ t("adminExport.subtitle") }}</p>
        </div>
        <div class="header-actions">
          <button class="ghost-btn" :disabled="preflightLoading" @click="loadPreflight">
            {{ preflightLoading ? t("adminExport.checking") : t("adminExport.refreshSnapshot") }}
          </button>
          <button class="primary-btn" :disabled="exporting" @click="doExport">
            {{ exporting ? t("adminExport.packing") : t("adminExport.downloadBackup") }}
          </button>
        </div>
      </div>

      <div v-if="preflight" class="snapshot-grid">
        <div v-for="(value, key) in preflight.counts" :key="key" class="snap-card">
          <span class="snap-label">{{ labelMap[key] || key }}</span>
          <span class="snap-val">{{ value }}</span>
        </div>
        <div class="snap-card snap-wide">
          <span class="snap-label">{{ t("adminExport.uploads") }}</span>
          <span class="snap-val">{{ preflight.uploads.file_count }} {{ t("adminExport.uploadsCount", { count: preflight.uploads.file_count, size: formatFileSize(preflight.uploads.size_bytes) }) }}</span>
        </div>
        <div class="snap-card snap-wide">
          <span class="snap-label">{{ t("adminExport.backupVersion") }}</span>
          <span class="snap-val version-badge">{{ preflight.schema_version }}</span>
        </div>
      </div>
      <p v-else class="muted-tip">{{ t("adminExport.snapshotTip") }}</p>

      <p class="export-desc">
        {{ t("adminExport.exportDesc") }}
      </p>
    </section>

    <section class="glass-card section-block">
      <div class="section-header">
        <div>
          <h2>{{ t("adminExport.autoBackupSchedule") }}</h2>
          <p class="section-subtitle">{{ t("adminExport.autoBackupSubtitle") }}</p>
        </div>
        <button class="primary-btn" :disabled="autoRunning" @click="runAutoBackup">
          {{ autoRunning ? t("adminExport.running") : t("adminExport.runNow") }}
        </button>
      </div>

      <form class="schedule-grid" @submit.prevent="saveSchedule">
        <label class="toggle-row">
          <input v-model="schedule.enabled" type="checkbox" />
          <span>{{ t("adminExport.enableAutoBackup") }}</span>
        </label>
        <label class="field-label">
          {{ t("adminExport.intervalHours") }}
          <input v-model.number="schedule.interval_hours" class="input" type="number" min="1" max="168" />
        </label>
        <label class="field-label">
          {{ t("adminExport.keepLast") }}
          <input v-model.number="schedule.keep_last" class="input" type="number" min="1" max="30" />
        </label>
        <label class="field-label">
          {{ t("adminExport.backupDir") }}
          <input v-model="schedule.backup_dir" class="input" maxlength="120" />
        </label>
        <div class="schedule-actions">
          <button class="ghost-btn" type="button" @click="loadSchedule">{{ t("adminExport.reload") }}</button>
          <button class="primary-btn" type="submit" :disabled="scheduleSaving">
            {{ scheduleSaving ? t("adminExport.saving") : t("adminExport.saveSchedule") }}
          </button>
        </div>
      </form>

      <div v-if="scheduleLoaded" class="schedule-meta">
        <span>{{ t("adminExport.lastRun", { date: formatDate(schedule.last_run_at) }) }}</span>
        <span>{{ t("adminExport.nextRun", { date: formatDate(schedule.next_run_at) }) }}</span>
        <span :class="['version-badge', schedule.last_status === 'failed' ? 'version-badge--danger' : '']">
          {{ schedule.last_status || t("adminExport.notRun") }}
        </span>
      </div>
      <p v-if="schedule.last_error" class="error-text">{{ schedule.last_error }}</p>
    </section>

    <section class="glass-card section-block restore-card">
      <div class="section-header">
        <div>
          <h2>{{ t("adminExport.restoreBackup") }}</h2>
          <p class="section-subtitle">{{ t("adminExport.restoreSubtitle") }}</p>
        </div>
      </div>

      <div
        class="restore-zone"
        :class="{ 'restore-zone--drag': dragging }"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
      >
        <div class="restore-zone-inner">
          <span class="restore-icon">ZIP</span>
          <p>{{ t("adminExport.dropZoneHint") }}</p>
          <label class="file-pick-btn">
            {{ t("adminExport.selectFile") }}
            <input type="file" accept=".zip" @change="onFileChange" />
          </label>
          <p v-if="restoreFile" class="file-name">{{ restoreFile.name }} · {{ formatFileSize(restoreFile.size) }}</p>
        </div>
      </div>

      <div v-if="restoreFile" class="restore-actions">
        <button class="ghost-btn" :disabled="restoreChecking" @click="runRestorePreflight">
          {{ restoreChecking ? t("adminExport.preflightChecking") : t("adminExport.preflightCheck") }}
        </button>
        <button class="danger-btn" :disabled="restoring || !restorePassed" @click="doRestore">
          {{ restoring ? t("adminExport.restoring") : t("adminExport.executeRestore") }}
        </button>
      </div>

      <div v-if="restoreReport" class="preflight-report" :class="restoreReport.ok ? 'report-ok' : 'report-fail'">
        <p class="report-title">{{ restoreReport.ok ? t("adminExport.preflightPassed") : t("adminExport.preflightFailed") }}</p>
        <ul v-if="restoreReport.errors?.length">
          <li v-for="error in restoreReport.errors" :key="error" class="err-item">{{ error }}</li>
        </ul>
        <ul v-if="restoreReport.warnings?.length">
          <li v-for="warning in restoreReport.warnings" :key="warning" class="warn-item">{{ warning }}</li>
        </ul>
      </div>

      <div v-if="restoreResult" class="restore-result" :class="{ 'restore-result--fail': restoreResult.database_error }">
        <p :class="restoreResult.database_error ? 'result-fail' : 'result-ok'">{{ restoreResult.message }}</p>
        <div v-if="restoreResult.database_import" class="import-breakdown">
          <p class="import-breakdown-title">{{ t("adminExport.importBreakdownTitle") }}</p>
          <ul>
            <li v-for="row in importRows(restoreResult.database_import)" :key="row.key">
              <span class="import-label">{{ row.label }}</span>
              <span class="import-nums">
                <span class="import-created">+{{ row.created }}</span>
                <span v-if="row.skipped !== null" class="import-skipped">{{ t("adminExport.skipped", { n: row.skipped }) }}</span>
              </span>
            </li>
          </ul>
          <p v-if="restoreResult.database_import.skipped_sections?.length" class="import-note">
            {{ t("adminExport.notImported", { sections: restoreResult.database_import.skipped_sections.join("、") }) }}
          </p>
        </div>
      </div>
    </section>

    <section class="glass-card section-block">
      <div class="section-header">
        <div>
          <h2>{{ t("adminExport.operationHistory") }}</h2>
          <p class="section-subtitle">{{ t("adminExport.historySubtitle") }}</p>
        </div>
        <button class="ghost-btn" @click="loadHistory">{{ t("adminExport.refresh") }}</button>
      </div>

      <div v-if="history.length === 0" class="muted-tip">{{ t("adminExport.noHistory") }}</div>
      <div v-else class="history-list">
        <article v-for="item in history" :key="historyKey(item)" class="history-item">
          <span class="history-badge" :class="item.action === 'restore' ? 'badge-restore' : 'badge-backup'">
            {{ actionLabel(item) }}
          </span>
          <div class="history-body">
            <p class="history-filename">{{ item.file_name || t("adminExport.unnamedBackup") }}</p>
            <p class="history-meta">
              {{ formatDate(item.created_at || item.restored_at) }} · {{ item.operator_nickname || item.operator_uid || t("adminSecurity.system") }}
              <span v-if="item.schema_version" class="version-badge small">{{ item.schema_version }}</span>
            </p>
            <p v-if="item.counts" class="history-counts">
              <span v-for="(value, key) in item.counts" :key="key">{{ labelMap[key] || key }}: {{ value }}</span>
            </p>
            <p v-if="item.archive_size_bytes" class="history-meta">ZIP: {{ formatFileSize(item.archive_size_bytes) }}</p>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { inject, onMounted, reactive, ref, computed } from "vue";
import {
  exportBackupArchive,
  fetchBackupHistory,
  fetchBackupPreflight,
  fetchBackupSchedule,
  restoreBackup,
  restorePreflight,
  runAutoBackupNow,
  updateBackupSchedule,
} from "../lib/api";
import { confirmDialog } from "../lib/dialog";
import { t } from "../locales";
import { formatFileSize, parseError } from "../utils/helpers";

const showMessage = inject("showMessage");

const labelMap = computed(() => ({
  users: t("adminExport.labelUsers"),
  articles: t("adminExport.labelArticles"),
  albums: t("adminExport.labelAlbums"),
  events: t("adminExport.labelEvents"),
  moments: t("adminExport.labelMoments"),
  messages: t("adminExport.labelMessages"),
  capsules: t("adminExport.labelCapsules"),
  versions: t("adminExport.labelVersions"),
  notifications: t("adminExport.labelNotifications"),
}));

const preflight = ref(null);
const preflightLoading = ref(false);
const exporting = ref(false);
const history = ref([]);

const scheduleLoaded = ref(false);
const scheduleSaving = ref(false);
const autoRunning = ref(false);
const schedule = reactive({
  enabled: false,
  interval_hours: 24,
  keep_last: 7,
  backup_dir: "backups",
  last_run_at: null,
  next_run_at: null,
  last_status: null,
  last_error: null,
});

const restoreFile = ref(null);
const dragging = ref(false);
const restoreChecking = ref(false);
const restoreReport = ref(null);
const restorePassed = ref(false);
const restoring = ref(false);
const restoreResult = ref(null);

function formatDate(raw) {
  if (!raw) return t("adminExport.noDate");
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? raw : date.toLocaleString("zh-CN", { hour12: false });
}

function assignSchedule(data) {
  Object.assign(schedule, {
    enabled: data.enabled,
    interval_hours: data.interval_hours,
    keep_last: data.keep_last,
    backup_dir: data.backup_dir,
    last_run_at: data.last_run_at,
    next_run_at: data.next_run_at,
    last_status: data.last_status,
    last_error: data.last_error,
  });
  scheduleLoaded.value = true;
}

function historyKey(item) {
  return `${item.action || "backup"}:${item.backup_id}:${item.created_at || item.restored_at}`;
}

function actionLabel(item) {
  if (item.action === "restore") return t("adminExport.restore");
  if (item.action === "auto_backup") return t("adminExport.autoBackup");
  return t("adminExport.manualBackup");
}

const importLabelMap = computed(() => ({
  users: t("adminExport.labelUsers"),
  articles: t("adminExport.labelArticles"),
  albums: t("adminExport.labelAlbums"),
  events: t("adminExport.labelEvents"),
  moments: t("adminExport.labelMoments"),
  comments: t("adminExport.labelComments"),
  messages: t("adminExport.labelMessages"),
  capsules: t("adminExport.labelCapsules"),
}));

function importRows(imp) {
  if (!imp || typeof imp !== "object") return [];
  const order = ["users", "articles", "albums", "events", "moments", "comments", "messages", "capsules"];
  const rows = [];
  for (const key of order) {
    const value = imp[key];
    if (!value || typeof value !== "object") continue;
    const created = value.created ?? 0;
    // users reports "matched" (existing reused); others report "skipped".
    const skipped = key === "users" ? (value.matched ?? null) : (value.skipped ?? null);
    rows.push({ key, label: importLabelMap.value[key] || key, created, skipped });
  }
  return rows;
}

async function loadPreflight() {
  preflightLoading.value = true;
  try {
    preflight.value = await fetchBackupPreflight();
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    preflightLoading.value = false;
  }
}

async function doExport() {
  exporting.value = true;
  try {
    const response = await exportBackupArchive();
    const blob = new Blob([response.data], { type: "application/zip" });
    const cd = response.headers["content-disposition"] || "";
    const match = cd.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
    const fileName = decodeURIComponent(match?.[1] || match?.[2] || "love-backup.zip");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
    showMessage?.(t("adminExport.backupDownloadStarted"));
    await loadHistory();
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    exporting.value = false;
  }
}

async function loadSchedule() {
  try {
    assignSchedule(await fetchBackupSchedule());
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

async function saveSchedule() {
  scheduleSaving.value = true;
  try {
    const data = await updateBackupSchedule({
      enabled: schedule.enabled,
      interval_hours: schedule.interval_hours,
      keep_last: schedule.keep_last,
      backup_dir: schedule.backup_dir,
    });
    assignSchedule(data);
    showMessage?.(t("adminExport.scheduleSaved"));
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    scheduleSaving.value = false;
  }
}

async function runAutoBackup() {
  autoRunning.value = true;
  try {
    await runAutoBackupNow();
    showMessage?.(t("adminExport.autoBackupDone"));
    await Promise.all([loadSchedule(), loadHistory()]);
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    autoRunning.value = false;
  }
}

function resetRestoreState() {
  restoreReport.value = null;
  restorePassed.value = false;
  restoreResult.value = null;
}

function onFileChange(event) {
  restoreFile.value = event.target.files?.[0] || null;
  resetRestoreState();
}

function onDrop(event) {
  dragging.value = false;
  restoreFile.value = event.dataTransfer.files?.[0] || null;
  resetRestoreState();
}

async function runRestorePreflight() {
  if (!restoreFile.value) return;
  restoreChecking.value = true;
  try {
    const report = await restorePreflight(restoreFile.value);
    restoreReport.value = report;
    restorePassed.value = !!report.ok;
  } catch (error) {
    restoreReport.value = error?.response?.data || null;
    restorePassed.value = false;
    if (!restoreReport.value) showMessage?.(parseError(error));
  } finally {
    restoreChecking.value = false;
  }
}

async function doRestore() {
  if (!restoreFile.value || !restorePassed.value) return;
  if (!(await confirmDialog(t("adminExport.confirmRestore"), { danger: true }))) return;
  restoring.value = true;
  try {
    restoreResult.value = await restoreBackup(restoreFile.value);
    showMessage?.(t("adminExport.restoreDone"));
    await loadHistory();
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    restoring.value = false;
  }
}

async function loadHistory() {
  try {
    const data = await fetchBackupHistory();
    history.value = data.items || [];
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

onMounted(() => {
  loadPreflight();
  loadSchedule();
  loadHistory();
});
</script>

<style scoped>
.backup-root {
  display: grid;
  gap: 1.5rem;
}

.section-subtitle {
  margin: 0.25rem 0 0;
  color: #64748b;
  font-size: 0.86rem;
  line-height: 1.55;
}

.header-actions,
.restore-actions,
.schedule-actions {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
  align-items: center;
}

.primary-btn,
.danger-btn {
  border: none;
  border-radius: 999px;
  color: #fff;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 700;
  padding: 0.48rem 1rem;
  transition: opacity 0.2s, transform 0.15s;
}

.primary-btn {
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  box-shadow: 0 10px 18px rgb(143 155 255 / 0.22);
}

.danger-btn {
  background: linear-gradient(120deg, #ff6b6b, #ff9a5c);
}

.primary-btn:hover:not(:disabled),
.danger-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.snapshot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.snap-card {
  background: rgb(248 250 255 / 0.85);
  border: 1px solid rgb(148 163 184 / 0.3);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-height: 78px;
  padding: 0.75rem 1rem;
}

.snap-wide {
  grid-column: span 2;
}

.snap-label {
  color: #64748b;
  font-size: 0.72rem;
}

.snap-val {
  color: #2f3754;
  font-size: 1.12rem;
  font-weight: 800;
}

.version-badge {
  align-self: flex-start;
  background: rgb(143 155 255 / 0.18);
  border-radius: 999px;
  color: #4f5ecf;
  display: inline-block;
  font-size: 0.78rem;
  font-weight: 800;
  padding: 0.16rem 0.62rem;
}

.version-badge.small {
  font-size: 0.68rem;
  padding: 0.1rem 0.45rem;
}

.version-badge--danger {
  background: rgb(254 226 226 / 0.92);
  color: #b91c1c;
}

.export-desc {
  color: #475569;
  font-size: 0.88rem;
  line-height: 1.7;
  margin: 0;
}

.schedule-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.8rem;
}

.field-label {
  color: #475569;
  display: grid;
  font-size: 0.8rem;
  font-weight: 700;
  gap: 0.35rem;
}

.toggle-row {
  align-items: center;
  background: rgb(248 250 255 / 0.75);
  border: 1px solid rgb(148 163 184 / 0.26);
  border-radius: 12px;
  color: #334155;
  display: flex;
  font-size: 0.86rem;
  font-weight: 700;
  gap: 0.5rem;
  padding: 0.75rem 0.85rem;
}

.schedule-meta {
  color: #64748b;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.9rem;
  font-size: 0.82rem;
}

.restore-card {
  display: grid;
  gap: 1rem;
}

.restore-zone {
  border: 2px dashed rgb(148 163 184 / 0.5);
  border-radius: 14px;
  padding: 1.8rem 1rem;
  text-align: center;
  transition: border-color 0.2s, background 0.2s;
}

.restore-zone--drag {
  background: rgb(143 155 255 / 0.07);
  border-color: #8f9bff;
}

.restore-zone-inner {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.restore-icon {
  border: 1px solid rgb(143 155 255 / 0.34);
  border-radius: 999px;
  color: #4f5ecf;
  font-size: 0.74rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  padding: 0.34rem 0.58rem;
}

.restore-zone p {
  color: #64748b;
  font-size: 0.85rem;
  margin: 0;
}

.file-pick-btn {
  background: rgb(143 155 255 / 0.15);
  border: 1px solid rgb(143 155 255 / 0.4);
  border-radius: 999px;
  color: #4f5ecf;
  cursor: pointer;
  font-size: 0.8rem;
  padding: 0.4rem 1rem;
}

.file-pick-btn input {
  display: none;
}

.file-name {
  color: #3d4665;
  font-size: 0.78rem;
  font-weight: 700;
}

.preflight-report,
.restore-result {
  border-radius: 12px;
  display: grid;
  gap: 0.45rem;
  padding: 1rem 1.1rem;
}

.report-ok {
  background: rgb(236 253 245 / 0.9);
  border: 1px solid #6ee7b7;
}

.report-fail {
  background: rgb(254 242 242 / 0.9);
  border: 1px solid #fca5a5;
}

.report-title,
.result-ok {
  font-size: 0.9rem;
  font-weight: 800;
  margin: 0;
}

.restore-result--fail {
  background: rgb(254 242 242 / 0.9);
  border: 1px solid #fca5a5;
}

.result-fail {
  color: #b91c1c;
  font-size: 0.9rem;
  font-weight: 800;
  margin: 0;
}

.import-breakdown {
  border-top: 1px dashed #d1d5db;
  padding-top: 0.5rem;
}

.import-breakdown-title {
  color: #475569;
  font-size: 0.78rem;
  font-weight: 700;
  margin: 0 0 0.4rem;
}

.import-breakdown ul {
  display: grid;
  gap: 0.25rem;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  list-style: none;
  margin: 0;
  padding: 0;
}

.import-breakdown li {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 0.82rem;
  gap: 0.5rem;
}

.import-label {
  color: #334155;
}

.import-nums {
  display: inline-flex;
  gap: 0.5rem;
}

.import-created {
  color: #047857;
  font-weight: 700;
}

.import-skipped {
  color: #94a3b8;
}

.import-note {
  color: #94a3b8;
  font-size: 0.76rem;
  margin: 0.45rem 0 0;
}

.err-item,
.error-text {
  color: #dc2626;
  font-size: 0.82rem;
}

.warn-item {
  color: #b45309;
  font-size: 0.82rem;
}

.history-list {
  display: grid;
  gap: 0.7rem;
}

.history-item {
  align-items: flex-start;
  background: rgb(248 250 255 / 0.8);
  border: 1px solid rgb(148 163 184 / 0.25);
  border-radius: 12px;
  display: flex;
  gap: 0.85rem;
  padding: 0.75rem 1rem;
}

.history-badge {
  border-radius: 999px;
  flex-shrink: 0;
  font-size: 0.7rem;
  font-weight: 800;
  padding: 0.2rem 0.65rem;
  white-space: nowrap;
}

.badge-backup {
  background: rgb(143 155 255 / 0.18);
  color: #4f5ecf;
}

.badge-restore {
  background: rgb(251 146 60 / 0.18);
  color: #c2410c;
}

.history-body {
  display: grid;
  gap: 0.15rem;
  min-width: 0;
}

.history-filename {
  color: #1e293b;
  font-size: 0.85rem;
  font-weight: 800;
  margin: 0;
}

.history-meta,
.history-counts {
  color: #64748b;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0;
}

.history-meta {
  font-size: 0.75rem;
}

.history-counts {
  font-size: 0.73rem;
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

  .snap-wide {
    grid-column: span 1;
  }
}
</style>
