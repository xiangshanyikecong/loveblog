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
  <div class="content-section cottage-plans">
    <header class="plans-header">
      <div>
        <h2>{{ t('cottagePlans.title') }}</h2>
        <p>{{ t('cottagePlans.desc') }}</p>
      </div>
      <router-link to="/cottage" class="plans-back">{{ t('cottagePlans.back') }}</router-link>
    </header>

    <section class="glass-card section-block">
      <form class="plan-form" @submit.prevent="submitCreate">
        <input v-model="form.title" class="input" maxlength="160" :placeholder="t('cottagePlans.titlePlaceholder')" required />
        <textarea v-model="form.description" class="input" maxlength="2000" :placeholder="t('cottagePlans.descPlaceholder')"></textarea>
        <div class="plan-row">
          <input v-model="form.plan_date" type="date" class="input" />
          <input v-model="form.location" class="input" maxlength="160" :placeholder="t('cottagePlans.locationPlaceholder')" />
          <button class="btn" type="submit" :disabled="busy || !form.title.trim()">
            {{ busy ? t('cottagePlans.saving') : t('cottagePlans.submit') }}
          </button>
        </div>
        <div class="checklist-editor">
          <div v-for="(item, index) in form.checklist" :key="item.key" class="checklist-edit-row">
            <input v-model="item.text" class="input" maxlength="160" :placeholder="t('cottagePlans.checklistPlaceholder')" />
            <button type="button" class="icon-btn" :aria-label="t('cottagePlans.removeChecklist')" @click="removeChecklistItem(index)">×</button>
          </div>
          <button type="button" class="text-action" @click="addChecklistItem">{{ t('cottagePlans.addChecklist') }}</button>
        </div>
      </form>
    </section>

    <section class="plan-stats">
      <div class="glass-card stat-tile">
        <span>{{ counts.active }}</span>
        <p>{{ t('cottagePlans.statActive') }}</p>
      </div>
      <div class="glass-card stat-tile">
        <span>{{ counts.completed }}</span>
        <p>{{ t('cottagePlans.statCompleted') }}</p>
      </div>
      <div class="glass-card stat-tile">
        <span>{{ counts.total }}</span>
        <p>{{ t('cottagePlans.statTotal') }}</p>
      </div>
    </section>

    <section class="plan-tabs" :aria-label="t('cottagePlans.filterAria')">
      <button
        v-for="tab in tabs"
        :key="tab.value"
        :class="['plan-tab', { active: filter === tab.value }]"
        @click="setFilter(tab.value)"
      >
        {{ tab.label }}
      </button>
    </section>

    <section class="plan-list">
      <p v-if="loading" class="empty-text">{{ t('cottagePlans.loading') }}</p>
      <p v-else-if="!plans.length" class="empty-text">{{ t('cottagePlans.empty') }}</p>

      <article
        v-for="plan in plans"
        :key="plan.pid"
        class="glass-card plan-card"
        :class="{ done: plan.status === 'done' }"
      >
        <button
          class="plan-check"
          :class="{ checked: plan.status === 'done' }"
          :aria-label="plan.status === 'done' ? t('cottagePlans.reopenPlan') : t('cottagePlans.completePlan')"
          @click="toggleComplete(plan)"
        >
          <span v-if="plan.status === 'done'">✓</span>
        </button>

        <div class="plan-body">
          <div class="plan-title-row">
            <h3>{{ plan.title }}</h3>
            <span class="status-pill">{{ statusLabel(plan.status) }}</span>
          </div>
          <p v-if="plan.description" class="plan-desc">{{ plan.description }}</p>
          <div class="plan-meta">
            <span v-if="plan.plan_date">{{ t('cottagePlans.dateLabel') }} {{ formatDate(plan.plan_date) }}</span>
            <span v-if="plan.location">{{ t('cottagePlans.locationLabel') }} {{ plan.location }}</span>
            <span>{{ t('cottagePlans.authorLabel', { name: plan.author_nickname }) }}</span>
          </div>

          <div v-if="plan.checklist?.length" class="checklist">
            <label v-for="item in plan.checklist" :key="item.key" class="check-item">
              <input type="checkbox" :checked="item.done" @change="toggleChecklist(plan, item.key)" />
              <span :class="{ complete: item.done }">{{ item.text }}</span>
            </label>
          </div>

          <div class="plan-actions">
            <button class="text-action" @click="startEdit(plan)">{{ t('cottagePlans.edit') }}</button>
            <button class="text-action" @click="togglePin(plan)">{{ plan.priority > 0 ? t('cottagePlans.unpin') : t('cottagePlans.pin') }}</button>
            <button class="text-action danger" @click="remove(plan)">{{ t('cottagePlans.delete') }}</button>
          </div>

          <form v-if="editingPid === plan.pid" class="inline-edit" @submit.prevent="saveEdit(plan)">
            <input v-model="editForm.title" class="input" maxlength="160" />
            <textarea v-model="editForm.description" class="input" maxlength="2000"></textarea>
            <div class="plan-row">
              <input v-model="editForm.plan_date" type="date" class="input" />
              <input v-model="editForm.location" class="input" maxlength="160" />
            </div>
            <div class="plan-actions">
              <button class="btn-small" type="submit" :disabled="busy || !editForm.title.trim()">{{ t('cottagePlans.save') }}</button>
              <button class="btn-small ghost" type="button" @click="cancelEdit">{{ t('cottagePlans.cancel') }}</button>
            </div>
          </form>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  completeCottagePlan,
  createCottagePlan,
  deleteCottagePlan,
  fetchCottagePlans,
  reopenCottagePlan,
  updateCottagePlan,
} from "../../../lib/api";
import { parseError } from "../../../utils/helpers";
import { formatLocalDate as formatDate } from "../../../utils/date";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

const plans = ref([]);
const counts = reactive({ total: 0, active: 0, completed: 0, cancelled: 0 });
const loading = ref(true);
const busy = ref(false);
const filter = ref("active");
const editingPid = ref(null);

const form = reactive({
  title: "",
  description: "",
  location: "",
  plan_date: "",
  checklist: [],
});

const editForm = reactive({
  title: "",
  description: "",
  location: "",
  plan_date: "",
});

const tabs = computed(() => [
  { value: "active", label: t("cottagePlans.tabActive", { n: counts.active }) },
  { value: "done", label: t("cottagePlans.tabDone", { n: counts.completed }) },
  { value: "all", label: t("cottagePlans.tabAll", { n: counts.total }) },
]);

function statusLabel(status) {
  const map = {
    planned: "cottagePlans.statusPlanned",
    in_progress: "cottagePlans.statusInProgress",
    done: "cottagePlans.statusDone",
    cancelled: "cottagePlans.statusCancelled",
  };
  return map[status] ? t(map[status]) : status;
}

function addChecklistItem() {
  form.checklist.push({ key: `${Date.now()}-${form.checklist.length}`, text: "", done: false });
}

function removeChecklistItem(index) {
  form.checklist.splice(index, 1);
}

function normalizedChecklist(items) {
  return (items || [])
    .map((item) => ({ key: item.key || null, text: String(item.text || "").trim(), done: !!item.done }))
    .filter((item) => item.text);
}

async function load() {
  loading.value = true;
  try {
    const params = filter.value === "all" || filter.value === "active" ? {} : { status: filter.value };
    const data = await fetchCottagePlans(params);
    plans.value = filter.value === "active"
      ? (data.items || []).filter((item) => !["done", "cancelled"].includes(item.status))
      : (data.items || []);
    counts.total = data.total ?? 0;
    counts.active = data.active ?? 0;
    counts.completed = data.completed ?? 0;
    counts.cancelled = data.cancelled ?? 0;
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

function setFilter(value) {
  filter.value = value;
  load();
}

async function submitCreate() {
  if (!form.title.trim() || busy.value) return;
  busy.value = true;
  try {
    await createCottagePlan({
      title: form.title.trim(),
      description: form.description.trim() || null,
      location: form.location.trim() || null,
      plan_date: form.plan_date || null,
      checklist: normalizedChecklist(form.checklist),
    });
    form.title = "";
    form.description = "";
    form.location = "";
    form.plan_date = "";
    form.checklist = [];
    await load();
    showMessage(t("cottagePlans.createdToast"));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function toggleComplete(plan) {
  try {
    if (plan.status === "done") {
      await reopenCottagePlan(plan.pid);
    } else {
      await completeCottagePlan(plan.pid);
    }
    await load();
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function toggleChecklist(plan, key) {
  const checklist = (plan.checklist || []).map((item) =>
    item.key === key ? { ...item, done: !item.done } : item
  );
  try {
    await updateCottagePlan(plan.pid, { checklist });
    await load();
  } catch (error) {
    showMessage(parseError(error));
  }
}

function startEdit(plan) {
  editingPid.value = plan.pid;
  editForm.title = plan.title;
  editForm.description = plan.description || "";
  editForm.location = plan.location || "";
  editForm.plan_date = plan.plan_date ? String(plan.plan_date).slice(0, 10) : "";
}

function cancelEdit() {
  editingPid.value = null;
}

async function saveEdit(plan) {
  if (!editForm.title.trim() || busy.value) return;
  busy.value = true;
  try {
    await updateCottagePlan(plan.pid, {
      title: editForm.title.trim(),
      description: editForm.description.trim() || null,
      location: editForm.location.trim() || null,
      plan_date: editForm.plan_date || null,
    });
    editingPid.value = null;
    await load();
    showMessage(t("cottagePlans.savedToast"));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function togglePin(plan) {
  try {
    await updateCottagePlan(plan.pid, { priority: plan.priority > 0 ? 0 : 1 });
    await load();
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function remove(plan) {
  if (!window.confirm(t("cottagePlans.confirmDelete", { title: plan.title }))) return;
  try {
    await deleteCottagePlan(plan.pid);
    await load();
    showMessage(t("cottagePlans.deletedToast"));
  } catch (error) {
    showMessage(parseError(error));
  }
}

onMounted(load);
</script>

<style scoped>
.cottage-plans { display: grid; gap: 1rem; }
.plans-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.plans-header h2 { margin: 0; font-size: 1.4rem; color: #2f3754; }
.plans-header p { margin: 0.35rem 0 0; color: var(--text-soft); font-size: 0.9rem; }
.plans-back {
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
.plan-form,
.inline-edit {
  display: grid;
  gap: 0.7rem;
}
.plan-form textarea,
.inline-edit textarea {
  min-height: 5.5rem;
  resize: vertical;
}
.btn {
  border: 0;
  border-radius: 12px;
  padding: 0.62rem 0.95rem;
  background: linear-gradient(120deg, #14b8a6, #5fa8ff);
  color: #fff;
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
}
.btn:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}
.plan-row {
  display: grid;
  grid-template-columns: minmax(140px, 190px) 1fr auto;
  gap: 0.6rem;
}
.checklist-editor { display: grid; gap: 0.45rem; }
.checklist-edit-row {
  display: grid;
  grid-template-columns: 1fr 36px;
  gap: 0.45rem;
}
.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.36);
  background: rgba(255, 255, 255, 0.75);
  color: #64748b;
  cursor: pointer;
}
.plan-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
}
.stat-tile {
  border-radius: 16px;
  padding: 0.9rem 1rem;
}
.stat-tile span {
  display: block;
  color: #2f3754;
  font-size: 1.45rem;
  font-weight: 800;
}
.stat-tile p { margin: 0.2rem 0 0; color: var(--text-soft); font-size: 0.82rem; }
.plan-tabs { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.plan-tab {
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  border-radius: 999px;
  padding: 0.4rem 0.9rem;
  cursor: pointer;
}
.plan-tab.active {
  border-color: rgba(20, 184, 166, 0.5);
  background: rgba(20, 184, 166, 0.14);
  color: #0f766e;
  font-weight: 700;
}
.plan-list { display: grid; gap: 0.8rem; }
.plan-card {
  display: flex;
  gap: 0.8rem;
  padding: 1rem;
  border-radius: 16px;
}
.plan-card.done { opacity: 0.74; }
.plan-check {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid rgba(148, 163, 184, 0.7);
  background: transparent;
  color: #fff;
  cursor: pointer;
}
.plan-check.checked { background: #14b8a6; border-color: #14b8a6; }
.plan-body { flex: 1; min-width: 0; display: grid; gap: 0.45rem; }
.plan-title-row {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: flex-start;
}
.plan-title-row h3 {
  margin: 0;
  color: #2f3754;
  font-size: 1rem;
  overflow-wrap: anywhere;
}
.status-pill {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 0.2rem 0.6rem;
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
  font-size: 0.72rem;
}
.plan-desc {
  margin: 0;
  color: var(--text-soft);
  font-size: 0.86rem;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.plan-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  color: var(--text-soft);
  font-size: 0.78rem;
}
.checklist {
  display: grid;
  gap: 0.35rem;
  margin-top: 0.2rem;
}
.check-item {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  color: #3d4665;
  font-size: 0.84rem;
}
.check-item span.complete {
  text-decoration: line-through;
  color: var(--text-soft);
}
.plan-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}
.text-action {
  border: 0;
  background: transparent;
  color: #5b68a5;
  cursor: pointer;
  padding: 0;
  font-size: 0.82rem;
}
.text-action.danger { color: #dc4b78; }
.btn-small {
  border: 0;
  border-radius: 10px;
  padding: 0.42rem 0.9rem;
  background: #14b8a6;
  color: #fff;
  cursor: pointer;
}
.btn-small.ghost { background: rgba(148, 163, 184, 0.18); color: #334155; }
@media (max-width: 768px) {
  .plans-header,
  .plan-title-row { flex-direction: column; }
  .plans-back { width: 100%; justify-content: center; }
  .plan-row,
  .plan-stats { grid-template-columns: 1fr; }
}
</style>
