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
  <div class="content-section cottage-reports">
    <header class="reports-header">
      <div>
        <h2>{{ t('cottageReports.title') }}</h2>
        <p>{{ t('cottageReports.subtitle') }}</p>
      </div>
      <div class="reports-header-actions">
        <button
          v-if="aiReportEnabled"
          class="ai-report-btn"
          type="button"
          :disabled="aiBusy"
          @click="runAiReport"
        >
          {{ aiBusy ? t('cottageReports.aiGenerating') : t('cottageReports.aiNarrative') }}
        </button>
        <router-link to="/cottage" class="reports-back">{{ t('cottageReports.back') }}</router-link>
      </div>
    </header>

    <section class="glass-card section-block report-controls">
      <button class="month-btn" type="button" :aria-label="t('cottageReports.prevMonth')" @click="shiftMonth(-1)">‹</button>
      <input v-model="monthInput" type="month" class="input month-input" @change="load" />
      <button class="month-btn" type="button" :aria-label="t('cottageReports.nextMonth')" @click="shiftMonth(1)">›</button>
    </section>

    <section v-if="loading" class="glass-card section-block empty-text">{{ t('cottageReports.loading') }}</section>

    <template v-else-if="report">
      <!-- AI 月报文案：引用块展示，可复制 -->
      <section v-if="aiText" class="glass-card section-block ai-narrative">
        <div class="ai-narrative-head">
          <span class="ai-narrative-badge">✨ {{ t('cottageReports.aiNarrative') }}</span>
          <button class="ghost-btn" type="button" @click="copyAiText">{{ t('common.copy') }}</button>
        </div>
        <blockquote class="ai-narrative-quote">{{ aiText }}</blockquote>
      </section>

      <section class="report-summary">
        <article v-for="card in statCards" :key="card.key" class="glass-card report-stat">
          <span>{{ card.value }}</span>
          <p>{{ card.label }}</p>
        </article>
      </section>

      <section class="report-grid">
        <article class="glass-card section-block">
          <h3>{{ t('cottageReports.moodTop') }}</h3>
          <div v-if="report.top_moods.length" class="mood-list">
            <div v-for="mood in report.top_moods" :key="`${mood.mood}-${mood.emoji}`" class="mood-row">
              <span class="mood-emoji">{{ mood.emoji || "·" }}</span>
              <span>{{ mood.mood }}</span>
              <strong>{{ mood.count }}</strong>
            </div>
          </div>
          <p v-else class="empty-text">{{ t('cottageReports.emptyMoods') }}</p>
        </article>

        <article class="glass-card section-block">
          <h3>{{ t('cottageReports.highlights') }}</h3>
          <div v-if="report.highlights.length" class="highlight-list">
            <div v-for="item in report.highlights" :key="`${item.kind}-${item.title}`" class="highlight-row">
              <span class="kind-pill">{{ kindLabel(item.kind) }}</span>
              <div>
                <p>{{ item.title }}</p>
                <small>{{ item.subtitle }}<template v-if="item.occurred_at"> · {{ formatDate(item.occurred_at) }}</template></small>
              </div>
            </div>
          </div>
          <p v-else class="empty-text">{{ t('cottageReports.emptyHighlights') }}</p>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { aiMonthlyReport, fetchAiStatus, fetchCottageMonthlyReport } from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

const now = new Date();
const monthInput = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`);
const report = ref(null);
const loading = ref(true);

// AI 月报文案（按 /ai/status 显隐）
const aiReportEnabled = ref(false);
const aiBusy = ref(false);
const aiText = ref("");

const statCards = computed(() => {
  const stats = report.value?.stats || {};
  return [
    { key: "chat_messages", label: t('cottageReports.statChatMessages'), value: stats.chat_messages || 0 },
    { key: "checkins", label: t('cottageReports.statCheckins'), value: stats.checkins || 0 },
    { key: "moods", label: t('cottageReports.statMoods'), value: stats.moods || 0 },
    { key: "questions", label: t('cottageReports.statQuestions'), value: stats.questions || 0 },
    { key: "plans_completed", label: t('cottageReports.statPlansCompleted'), value: stats.plans_completed || 0 },
    { key: "wishes_completed", label: t('cottageReports.statWishesCompleted'), value: stats.wishes_completed || 0 },
  ];
});

function parseMonth() {
  const [year, month] = String(monthInput.value).split("-").map((part) => Number(part));
  return { year, month };
}

function shiftMonth(delta) {
  const { year, month } = parseMonth();
  const date = new Date(year, month - 1 + delta, 1);
  monthInput.value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  load();
}

function formatDate(raw) {
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? String(raw).slice(0, 10) : date.toLocaleDateString("zh-CN");
}

function kindLabel(kind) {
  const map = {
    wish: "cottageReports.kindWish",
    plan: "cottageReports.kindPlan",
    question: "cottageReports.kindQuestion",
  };
  return map[kind] ? t(map[kind]) : kind;
}

async function load() {
  const { year, month } = parseMonth();
  if (!year || !month) return;
  loading.value = true;
  aiText.value = "";
  try {
    report.value = await fetchCottageMonthlyReport(year, month);
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

// ── AI 月报文案 ───────────────────────────────────────────────────────────
async function loadAiStatus() {
  try {
    const status = await fetchAiStatus();
    aiReportEnabled.value = Boolean(
      status?.enabled && (status?.features || []).includes("monthly_report")
    );
  } catch (_) {
    // AI 未配置或网络失败 → 隐藏入口
    aiReportEnabled.value = false;
  }
}

async function runAiReport() {
  if (aiBusy.value) return;
  const { year, month } = parseMonth();
  if (!year || !month) return;
  aiBusy.value = true;
  aiText.value = "";
  try {
    const data = await aiMonthlyReport(year, month);
    aiText.value = (data.text || "").trim();
    if (!aiText.value) {
      showMessage(t("aiFeature.unavailable"));
    }
  } catch (error) {
    const status = error?.response?.status;
    showMessage(!status || status === 503 ? t("aiFeature.unavailable") : parseError(error));
  } finally {
    aiBusy.value = false;
  }
}

async function copyAiText() {
  if (!aiText.value) return;
  try {
    await navigator.clipboard.writeText(aiText.value);
    showMessage(t("common.copied"));
  } catch (_) {
    showMessage(t("privacyCenter.clipboardDenied"));
  }
}

onMounted(() => {
  load();
  loadAiStatus();
});
</script>

<style scoped>
.cottage-reports { display: grid; gap: 1rem; }
.reports-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.reports-header h2 { margin: 0; font-size: 1.4rem; color: #2f3754; }
.reports-header p { margin: 0.35rem 0 0; color: var(--text-soft); font-size: 0.9rem; }
.reports-back {
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
  white-space: nowrap;
}
.report-controls {
  display: grid;
  grid-template-columns: 42px minmax(180px, 260px) 42px;
  gap: 0.65rem;
  align-items: center;
  justify-content: center;
}

/* 头部操作区 + AI 文案按钮 */
.reports-header-actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.ai-report-btn {
  min-height: 36px;
  padding: 0.4rem 0.95rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 182, 205, 0.55);
  background: linear-gradient(120deg, #ffe0ee, #e8eaff);
  color: #2f3754;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.ai-report-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 8px 16px rgba(255, 138, 181, 0.25);
}
.ai-report-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* AI 文案引用块 */
.ai-narrative {
  display: grid;
  gap: 0.7rem;
}
.ai-narrative-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}
.ai-narrative-badge {
  border-radius: 999px;
  padding: 0.22rem 0.7rem;
  background: linear-gradient(120deg, rgba(255, 138, 181, 0.18), rgba(143, 155, 255, 0.18));
  color: #8a6b7c;
  font-size: 0.76rem;
  font-weight: 700;
}
.ai-narrative-quote {
  margin: 0;
  padding: 0.9rem 1.1rem;
  border-left: 4px solid #ff8ab5;
  border-radius: 0 14px 14px 0;
  background: linear-gradient(135deg, rgba(255, 224, 238, 0.6), rgba(232, 234, 255, 0.5));
  color: #3d4665;
  font-size: 0.92rem;
  line-height: 1.85;
  white-space: pre-wrap;
  word-break: break-word;
}
.month-btn {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.38);
  background: rgba(255, 255, 255, 0.76);
  color: #3d4665;
  font-size: 1.35rem;
  cursor: pointer;
}
.month-input { text-align: center; }
.report-summary {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0.75rem;
}
.report-stat {
  border-radius: 16px;
  padding: 0.9rem;
}
.report-stat span {
  display: block;
  color: #2f3754;
  font-size: 1.55rem;
  font-weight: 800;
}
.report-stat p { margin: 0.18rem 0 0; color: var(--text-soft); font-size: 0.78rem; }
.report-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}
.report-grid h3 {
  margin: 0 0 0.8rem;
  color: #2f3754;
}
.mood-list,
.highlight-list {
  display: grid;
  gap: 0.55rem;
}
.mood-row,
.highlight-row {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(203, 213, 225, 0.45);
  padding: 0.65rem 0.7rem;
}
.mood-emoji {
  width: 28px;
  height: 28px;
  border-radius: 10px;
  display: inline-grid;
  place-items: center;
  background: rgba(20, 184, 166, 0.12);
}
.mood-row strong {
  margin-left: auto;
  color: #0f766e;
}
.kind-pill {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 0.18rem 0.55rem;
  background: rgba(220, 75, 120, 0.12);
  color: #dc4b78;
  font-size: 0.72rem;
}
.highlight-row p {
  margin: 0;
  color: #2f3754;
  overflow-wrap: anywhere;
}
.highlight-row small {
  display: block;
  margin-top: 0.18rem;
  color: var(--text-soft);
}
@media (max-width: 960px) {
  .report-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .report-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .reports-header { flex-direction: column; }
  .reports-back { width: 100%; justify-content: center; }
  .report-controls { grid-template-columns: 42px 1fr 42px; }
  .report-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
