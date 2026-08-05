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
  <div class="content-section cottage-ledger">
    <div class="lg-header">
      <h2>{{ t('cottageLedger.title') }}</h2>
      <input v-model="month" type="month" class="input lg-month" @change="loadAll" />
    </div>

    <!-- 汇总 -->
    <section class="glass-card section-block lg-summary">
      <div class="lg-summary-top">
        <div class="lg-total">
          <span class="lg-total-label">{{ t('cottageLedger.totalLabel') }}</span>
          <span class="lg-total-value">¥{{ yuan(summary.total_spent_cents) }}</span>
          <span class="lg-total-count">{{ t('cottageLedger.entryCount', { n: summary.entry_count }) }}</span>
        </div>
        <div class="lg-balance" :class="{ settled: summary.balance.settled }">
          <template v-if="summary.balance.settled">{{ t("cottageLedger.settled") }}</template>
          <template v-else>
            {{ t("cottageLedger.owes", { debtor: summary.balance.debtor_nickname, creditor: summary.balance.creditor_nickname }) }}
            <strong>¥{{ yuan(summary.balance.amount_cents) }}</strong>
          </template>
        </div>
      </div>

      <div v-if="summary.by_category.length" class="lg-cats">
        <div v-for="c in summary.by_category" :key="c.category" class="lg-cat-row">
          <span class="lg-cat-name">{{ c.category }}</span>
          <div class="lg-cat-bar">
            <div class="lg-cat-fill" :style="{ width: barWidth(c.amount_cents) + '%' }"></div>
          </div>
          <span class="lg-cat-amt">¥{{ yuan(c.amount_cents) }}</span>
        </div>
      </div>
    </section>

    <!-- 记一笔 -->
    <section class="glass-card section-block">
      <form class="lg-form" @submit.prevent="submitCreate">
        <div class="lg-form-row">
          <input v-model="form.title" class="input" maxlength="160" :placeholder="t('cottageLedger.titlePlaceholder')" required />
          <input
            v-model="form.amount"
            class="input lg-amount"
            type="number"
            min="0.01"
            step="0.01"
            :placeholder="t('cottageLedger.amountPlaceholder')"
            required
          />
        </div>
        <div class="lg-form-row">
          <select v-model="form.category" class="input">
            <option value="">{{ t('cottageLedger.noCategory') }}</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
          <select v-model="form.payer" class="input">
            <option value="me">{{ t('cottageLedger.paidByMe') }}</option>
            <option value="partner">{{ t('cottageLedger.paidByPartner') }}</option>
          </select>
          <select v-model="form.split_type" class="input">
            <option value="aa">{{ t('cottageLedger.splitAA') }}</option>
            <option value="treat">{{ t('cottageLedger.splitTreat') }}</option>
            <option value="owed_full">{{ t('cottageLedger.splitOwedFull') }}</option>
          </select>
        </div>
        <div class="lg-form-row">
          <input v-model="form.spent_on" type="date" class="input" />
          <button type="submit" class="btn" :disabled="busy || !canSubmit">
            {{ busy ? t('cottageLedger.busy') : t('cottageLedger.submit') }}
          </button>
        </div>
      </form>
    </section>

    <!-- 明细 -->
    <section class="lg-list">
      <p v-if="loading" class="lg-empty">{{ t('cottageLedger.loading') }}</p>
      <p v-else-if="!entries.length" class="lg-empty">{{ t('cottageLedger.empty') }}</p>

      <article v-for="e in entries" :key="e.leid" class="lg-item glass-card">
        <div class="lg-item-main">
          <p class="lg-item-title">{{ e.title }}</p>
          <div class="lg-item-meta">
            <span v-if="e.category" class="lg-pill">{{ e.category }}</span>
            <span>{{ t('cottageLedger.paidBy', { name: e.payer_nickname }) }}</span>
            <span class="lg-split">{{ splitLabel(e.split_type) }}</span>
            <span>{{ formatDate(e.spent_on) }}</span>
          </div>
          <p v-if="e.note" class="lg-item-note">{{ e.note }}</p>
        </div>
        <div class="lg-item-side">
          <span class="lg-item-amt">¥{{ yuan(e.amount_cents) }}</span>
          <button class="lg-link lg-link--danger" @click="remove(e)">{{ t('cottageLedger.delete') }}</button>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  fetchLedger,
  fetchLedgerSummary,
  createLedgerEntry,
  deleteLedgerEntry,
} from "../../../lib/api";
import { parseError } from "../../../utils/helpers";
import {
  formatLocalDate as formatDate,
  localDateKey,
  localMonthKey,
} from "../../../utils/date";

const showMessage = inject("showMessage", () => {});
const { t } = useI18n();

const categories = ["餐饮", "交通", "购物", "娱乐", "居家", "旅行", "礼物", "其他"];

const month = ref(localMonthKey());
const entries = ref([]);
const summary = reactive({
  total_spent_cents: 0,
  entry_count: 0,
  by_category: [],
  balance: { settled: true },
});
const loading = ref(true);
const busy = ref(false);

const form = reactive({
  title: "",
  amount: "",
  category: "",
  payer: "me",
  split_type: "aa",
  spent_on: localDateKey(),
});

const canSubmit = computed(() => form.title.trim() && Number(form.amount) > 0);

function yuan(cents) {
  return ((cents || 0) / 100).toFixed(2);
}
function barWidth(cents) {
  const max = summary.by_category.reduce((m, c) => Math.max(m, c.amount_cents), 0);
  return max > 0 ? Math.max(4, Math.round((cents / max) * 100)) : 0;
}
function splitLabel(type) {
  return { aa: t('cottageLedger.splitLabels.aa'), treat: t('cottageLedger.splitLabels.treat'), owed_full: t('cottageLedger.splitLabels.owed_full') }[type] || type;
}
async function loadAll() {
  loading.value = true;
  try {
    const [list, sum] = await Promise.all([
      fetchLedger({ month: month.value, page_size: 100 }),
      fetchLedgerSummary({ month: month.value }),
    ]);
    entries.value = list.items || [];
    summary.total_spent_cents = sum.total_spent_cents || 0;
    summary.entry_count = sum.entry_count || 0;
    summary.by_category = sum.by_category || [];
    summary.balance = sum.balance || { settled: true };
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

async function submitCreate() {
  if (!canSubmit.value || busy.value) return;
  busy.value = true;
  try {
    await createLedgerEntry({
      title: form.title.trim(),
      amount_cents: Math.round(Number(form.amount) * 100),
      category: form.category || null,
      payer: form.payer,
      split_type: form.split_type,
      spent_on: form.spent_on || localDateKey(),
    });
    form.title = "";
    form.amount = "";
    form.category = "";
    await loadAll();
    showMessage(t("cottageLedger.createdToast"));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function remove(e) {
  if (!window.confirm(t('cottageLedger.confirmDelete', { title: e.title }))) return;
  try {
    await deleteLedgerEntry(e.leid);
    await loadAll();
    showMessage(t('cottageLedger.deletedToast'));
  } catch (error) {
    showMessage(parseError(error));
  }
}

onMounted(loadAll);
</script>

<style scoped>
.cottage-ledger { display: grid; gap: 1rem; }
.lg-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  padding: 0.2rem 0.2rem 0;
}
.lg-header h2 { margin: 0; font-size: 1.4rem; color: #2f3754; }
.lg-month { width: auto; max-width: 170px; }

.lg-summary { display: grid; gap: 0.9rem; }
.lg-summary-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  flex-wrap: wrap;
}
.lg-total { display: flex; align-items: baseline; gap: 0.5rem; }
.lg-total-label { font-size: 0.84rem; color: var(--text-soft); }
.lg-total-value { font-size: 1.5rem; font-weight: 700; color: #2f3754; }
.lg-total-count { font-size: 0.78rem; color: var(--text-soft); }
.lg-balance {
  font-size: 0.86rem;
  color: #b45309;
  background: rgba(251, 191, 36, 0.15);
  border-radius: 999px;
  padding: 0.35rem 0.9rem;
}
.lg-balance.settled { color: #16a34a; background: rgba(34, 197, 94, 0.14); }
.lg-balance strong { font-size: 0.95rem; }

.lg-cats { display: grid; gap: 0.45rem; }
.lg-cat-row { display: flex; align-items: center; gap: 0.6rem; }
.lg-cat-name { flex: 0 0 56px; font-size: 0.8rem; color: #3d4665; }
.lg-cat-bar {
  flex: 1 1 auto;
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.22);
  overflow: hidden;
}
.lg-cat-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #f9a8d4, #a78bfa); }
.lg-cat-amt { flex: 0 0 auto; font-size: 0.8rem; color: var(--text-soft); }

.lg-form { display: grid; gap: 0.6rem; }
.lg-form-row { display: flex; gap: 0.6rem; flex-wrap: wrap; }
.lg-form-row .input { flex: 1 1 auto; min-width: 110px; }
.lg-amount { max-width: 140px; }

.lg-list { display: grid; gap: 0.7rem; }
.lg-empty { text-align: center; color: var(--text-soft); font-size: 0.9rem; padding: 1.5rem 0; }

.lg-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.85rem 1.05rem;
  border-radius: 14px;
}
.lg-item-main { min-width: 0; display: grid; gap: 0.3rem; }
.lg-item-title { margin: 0; font-size: 0.96rem; font-weight: 600; color: #2f3754; word-break: break-word; }
.lg-item-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.76rem;
  color: var(--text-soft);
}
.lg-pill {
  padding: 0.05rem 0.5rem;
  border-radius: 999px;
  background: rgba(167, 139, 250, 0.16);
  color: #7c3aed;
}
.lg-split {
  padding: 0.05rem 0.5rem;
  border-radius: 999px;
  background: rgba(96, 165, 250, 0.16);
  color: #2563eb;
}
.lg-item-note { margin: 0; font-size: 0.82rem; color: var(--text-soft); white-space: pre-wrap; }
.lg-item-side { flex: 0 0 auto; display: flex; flex-direction: column; align-items: flex-end; gap: 0.35rem; }
.lg-item-amt { font-size: 1.02rem; font-weight: 700; color: #2f3754; }
.lg-link { background: none; border: none; padding: 0; font-size: 0.76rem; color: #6d77a8; cursor: pointer; }
.lg-link--danger { color: #e2698f; }
.lg-link--danger:hover { color: #d6336c; }

@media (max-width: 768px) {
  .lg-form-row { flex-direction: column; }
  .lg-amount { max-width: none; }
}
</style>
