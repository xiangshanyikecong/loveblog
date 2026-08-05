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
  <div class="content-section cottage-period">
    <div class="pd-header">
      <h2>{{ t('cottagePeriod.title') }}</h2>
      <span class="pd-sub">{{ t('cottagePeriod.subtitle') }}</span>
    </div>

    <!-- 预测概览 -->
    <section class="glass-card section-block pd-summary" :class="phaseClass">
      <div class="pd-phase">
        <span class="pd-phase-emoji">{{ phaseEmoji }}</span>
        <div>
          <p class="pd-phase-label">{{ phaseLabel }}</p>
          <p class="pd-phase-sub">{{ phaseSub }}</p>
        </div>
      </div>
      <div class="pd-stats">
        <div class="pd-stat">
          <span class="pd-stat-num">{{ summary.avg_cycle_days ?? "—" }}</span>
          <span class="pd-stat-lbl">{{ t('cottagePeriod.avgCycleLabel') }}</span>
        </div>
        <div class="pd-stat">
          <span class="pd-stat-num">{{ summary.avg_period_days ?? "-" }}</span>
          <span class="pd-stat-lbl">{{ t('cottagePeriod.avgPeriodLabel') }}</span>
        </div>
        <div class="pd-stat">
          <span class="pd-stat-num">{{ summary.predicted_next_start ? formatDate(summary.predicted_next_start) : "-" }}</span>
          <span class="pd-stat-lbl">{{ t('cottagePeriod.predictedNextLabel') }}</span>
        </div>
      </div>
    </section>

    <!-- 记录 -->
    <section class="glass-card section-block">
      <form class="pd-form" @submit.prevent="submitCreate">
        <div class="pd-form-row">
          <label class="pd-field">
            <span>{{ t('cottagePeriod.startDateLabel') }}</span>
            <input v-model="form.start_date" type="date" class="input" required />
          </label>
          <label class="pd-field">
            <span>{{ t('cottagePeriod.endDateLabel') }}</span>
            <input v-model="form.end_date" type="date" class="input" />
          </label>
        </div>
        <textarea v-model="form.note" class="input min-h-16" maxlength="2000" :placeholder="t('cottagePeriod.notePlaceholder')"></textarea>
        <button type="submit" class="btn" :disabled="busy || !form.start_date">
          {{ busy ? t('cottagePeriod.saving') : t('cottagePeriod.submit') }}
        </button>
      </form>
    </section>

    <!-- 历史 -->
    <section class="pd-list">
      <p v-if="loading" class="pd-empty">{{ t('cottagePeriod.loading') }}</p>
      <p v-else-if="!cycles.length" class="pd-empty">{{ t('cottagePeriod.empty') }}</p>

      <article v-for="c in cycles" :key="c.pcid" class="pd-item glass-card">
        <div class="pd-item-main">
          <p class="pd-item-date">
            {{ formatDate(c.start_date) }}
            <template v-if="c.end_date"> – {{ formatDate(c.end_date) }}</template>
            <span v-if="c.length_days" class="pd-item-len">{{ t('cottagePeriod.daysCount', { n: c.length_days }) }}</span>
          </p>
          <p v-if="c.note" class="pd-item-note">{{ c.note }}</p>
          <p class="pd-item-by">{{ t('cottagePeriod.recordedBy', { name: c.author_nickname }) }}</p>
        </div>
        <button class="pd-link pd-link--danger" @click="remove(c)">{{ t('cottagePeriod.delete') }}</button>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  fetchPeriods,
  fetchPeriodSummary,
  createPeriod,
  deletePeriod,
} from "../../../lib/api";
import { parseError } from "../../../utils/helpers";
import { formatLocalDate as formatDate, localDateKey } from "../../../utils/date";

const showMessage = inject("showMessage", () => {});
const { t } = useI18n();

const cycles = ref([]);
const summary = reactive({
  cycle_count: 0,
  avg_cycle_days: null,
  avg_period_days: null,
  predicted_next_start: null,
  predicted_days_until: null,
  phase: "unknown",
});
const loading = ref(true);
const busy = ref(false);

const form = reactive({ start_date: localDateKey(), end_date: "", note: "" });

const PHASES = {
  in_period: { labelKey: "cottagePeriod.phaseInPeriod", emoji: "🌷", cls: "phase-in" },
  due_soon: { labelKey: "cottagePeriod.phaseDueSoon", emoji: "💗", cls: "phase-soon" },
  overdue: { labelKey: "cottagePeriod.phaseOverdue", emoji: "🫧", cls: "phase-over" },
  normal: { labelKey: "cottagePeriod.phaseNormal", emoji: "🌿", cls: "phase-normal" },
  unknown: { labelKey: "cottagePeriod.phaseUnknown", emoji: "📝", cls: "phase-normal" },
};

const phaseLabel = computed(() => t((PHASES[summary.phase] || PHASES.unknown).labelKey));
const phaseEmoji = computed(() => (PHASES[summary.phase] || PHASES.unknown).emoji);
const phaseClass = computed(() => (PHASES[summary.phase] || PHASES.unknown).cls);
const phaseSub = computed(() => {
  const d = summary.predicted_days_until;
  if (summary.phase === "in_period") return t("cottagePeriod.phaseSubInPeriod");
  if (summary.phase === "unknown") return t("cottagePeriod.phaseSubUnknown");
  if (d === null || d === undefined) return "";
  if (d > 0) return t("cottagePeriod.phaseSubDaysUntil", { n: d });
  if (d === 0) return t("cottagePeriod.phaseSubToday");
  return t("cottagePeriod.phaseSubOverdue", { n: -d });
});

async function loadAll() {
  loading.value = true;
  try {
    const [list, sum] = await Promise.all([fetchPeriods(), fetchPeriodSummary()]);
    cycles.value = list.items || [];
    Object.assign(summary, sum);
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

async function submitCreate() {
  if (!form.start_date || busy.value) return;
  busy.value = true;
  try {
    await createPeriod({
      start_date: form.start_date,
      end_date: form.end_date || null,
      note: form.note.trim() || null,
    });
    form.end_date = "";
    form.note = "";
    await loadAll();
    showMessage(t('cottagePeriod.createdToast'));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function remove(c) {
  if (!window.confirm(t('cottagePeriod.confirmDelete'))) return;
  try {
    await deletePeriod(c.pcid);
    await loadAll();
    showMessage(t('cottagePeriod.deletedToast'));
  } catch (error) {
    showMessage(parseError(error));
  }
}

onMounted(loadAll);
</script>

<style scoped>
.cottage-period { display: grid; gap: 1rem; }
.pd-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.6rem;
  padding: 0.2rem 0.2rem 0;
}
.pd-header h2 { margin: 0; font-size: 1.4rem; color: #2f3754; }
.pd-sub { font-size: 0.82rem; color: var(--text-soft); }

.pd-summary { display: grid; gap: 1rem; }
.pd-summary.phase-in { background: linear-gradient(135deg, rgba(255, 182, 193, 0.28), rgba(255, 255, 255, 0.6)); }
.pd-summary.phase-soon { background: linear-gradient(135deg, rgba(167, 139, 250, 0.22), rgba(255, 255, 255, 0.6)); }
.pd-summary.phase-over { background: linear-gradient(135deg, rgba(251, 191, 36, 0.2), rgba(255, 255, 255, 0.6)); }

.pd-phase { display: flex; align-items: center; gap: 0.8rem; }
.pd-phase-emoji { font-size: 2.2rem; }
.pd-phase-label { margin: 0; font-size: 1.1rem; font-weight: 700; color: #2f3754; }
.pd-phase-sub { margin: 0; font-size: 0.84rem; color: var(--text-soft); }

.pd-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.6rem; }
.pd-stat {
  display: grid;
  gap: 0.2rem;
  justify-items: center;
  padding: 0.6rem 0.4rem;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.55);
}
.pd-stat-num { font-size: 1rem; font-weight: 700; color: #2f3754; text-align: center; }
.pd-stat-lbl { font-size: 0.72rem; color: var(--text-soft); }

.pd-form { display: grid; gap: 0.6rem; }
.pd-form-row { display: flex; gap: 0.6rem; flex-wrap: wrap; }
.pd-field { flex: 1 1 auto; min-width: 130px; display: grid; gap: 0.25rem; font-size: 0.78rem; color: var(--text-soft); }
.min-h-16 { min-height: 4rem; resize: vertical; }

.pd-list { display: grid; gap: 0.7rem; }
.pd-empty { text-align: center; color: var(--text-soft); font-size: 0.9rem; padding: 1.5rem 0; }

.pd-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.85rem 1.05rem;
  border-radius: 14px;
}
.pd-item-main { min-width: 0; display: grid; gap: 0.25rem; }
.pd-item-date { margin: 0; font-size: 0.96rem; font-weight: 600; color: #2f3754; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.pd-item-len {
  font-size: 0.72rem;
  font-weight: 600;
  color: #be185d;
  background: rgba(244, 114, 182, 0.16);
  border-radius: 999px;
  padding: 0.05rem 0.5rem;
}
.pd-item-note { margin: 0; font-size: 0.84rem; color: var(--text-soft); white-space: pre-wrap; }
.pd-item-by { margin: 0; font-size: 0.74rem; color: var(--text-soft); }
.pd-link { background: none; border: none; padding: 0; font-size: 0.76rem; color: #6d77a8; cursor: pointer; flex: 0 0 auto; }
.pd-link--danger { color: #e2698f; }
.pd-link--danger:hover { color: #d6336c; }

@media (max-width: 768px) {
  .pd-form-row { flex-direction: column; }
}
</style>
