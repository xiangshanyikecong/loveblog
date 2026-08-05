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
  <div class="content-section cottage-reminders">
    <header class="reminders-header">
      <div>
        <h2>{{ t('cottageReminders.title') }}</h2>
        <p>{{ t('cottageReminders.subtitle') }}</p>
      </div>
      <router-link to="/cottage" class="reminders-back">{{ t('cottageReminders.back') }}</router-link>
    </header>

    <section class="glass-card section-block">
      <form class="reminder-form" @submit.prevent="submitCreate">
        <input v-model="form.title" class="input" maxlength="160" :placeholder="t('cottageReminders.titlePlaceholder')" required />
        <textarea v-model="form.note" class="input" maxlength="1000" :placeholder="t('cottageReminders.notePlaceholder')"></textarea>
        <div class="reminder-row">
          <input v-model="form.remind_at" type="datetime-local" class="input" required />
          <select v-model="form.audience" class="input">
            <option value="both">{{ t('cottageReminders.audienceBoth') }}</option>
            <option value="me">{{ t('cottageReminders.audienceMe') }}</option>
            <option value="partner">{{ t('cottageReminders.audiencePartner') }}</option>
          </select>
          <button class="btn" type="submit" :disabled="busy || !form.title.trim() || !form.remind_at">
            {{ busy ? t('cottageReminders.saving') : t('cottageReminders.submit') }}
          </button>
        </div>
      </form>
    </section>

    <section class="reminder-toolbar">
      <div class="glass-card reminder-counts">
        <span>{{ counts.due }}</span>
        <p>已到时间</p>
      </div>
      <label class="include-done">
        <input v-model="includeDone" type="checkbox" @change="load" />
        {{ t('cottageReminders.showDone') }}
      </label>
    </section>

    <section class="reminder-list">
      <p v-if="loading" class="empty-text">{{ t('cottageReminders.loading') }}</p>
      <p v-else-if="!reminders.length" class="empty-text">{{ t('cottageReminders.empty') }}</p>

      <article
        v-for="item in reminders"
        :key="item.rid"
        class="glass-card reminder-card"
        :class="{ due: item.is_due, done: item.is_done }"
      >
        <div class="reminder-main">
          <div class="reminder-head">
            <h3>{{ item.title }}</h3>
            <span class="audience-pill">{{ audienceLabel(item.audience) }}</span>
          </div>
          <p v-if="item.note" class="reminder-note">{{ item.note }}</p>
          <div class="reminder-meta">
            <span>{{ formatDateTime(item.remind_at) }}</span>
            <span>{{ t('cottageReminders.createdBy', { name: item.author_nickname }) }}</span>
            <span v-if="item.is_due && !item.is_done" class="due-text">{{ t('cottageReminders.dueText') }}</span>
          </div>
        </div>
        <div class="reminder-actions">
          <button class="btn-small" @click="toggleDone(item)">
            {{ item.is_done ? t('cottageReminders.reopen') : t('cottageReminders.complete') }}
          </button>
          <button class="text-action danger" @click="remove(item)">{{ t('cottageReminders.delete') }}</button>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  createCottageReminder,
  deleteCottageReminder,
  fetchCottageReminders,
  markCottageReminderDone,
  reopenCottageReminder,
} from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

const reminders = ref([]);
const counts = reactive({ total: 0, active: 0, done: 0, due: 0 });
const loading = ref(true);
const busy = ref(false);
const includeDone = ref(false);
const form = reactive({
  title: "",
  note: "",
  remind_at: "",
  audience: "both",
});

function audienceLabel(value) {
  const map = {
    both: "cottageReminders.audienceBothShort",
    me: "cottageReminders.audienceMe",
    partner: "cottageReminders.audiencePartner",
  };
  return map[value] ? t(map[value]) : value;
}

function localDatetimeValueToIso(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toISOString();
}

function formatDateTime(raw) {
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return String(raw);
  return date.toLocaleString("zh-CN", { month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

async function load() {
  loading.value = true;
  try {
    const data = await fetchCottageReminders({ include_done: includeDone.value });
    reminders.value = data.items || [];
    counts.total = data.total ?? 0;
    counts.active = data.active ?? 0;
    counts.done = data.done ?? 0;
    counts.due = data.due ?? 0;
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

async function submitCreate() {
  if (!form.title.trim() || !form.remind_at || busy.value) return;
  busy.value = true;
  try {
    await createCottageReminder({
      title: form.title.trim(),
      note: form.note.trim() || null,
      remind_at: localDatetimeValueToIso(form.remind_at),
      audience: form.audience,
    });
    form.title = "";
    form.note = "";
    form.remind_at = "";
    form.audience = "both";
    await load();
    showMessage(t('cottageReminders.createdToast'));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function toggleDone(item) {
  try {
    if (item.is_done) {
      await reopenCottageReminder(item.rid);
    } else {
      await markCottageReminderDone(item.rid);
    }
    await load();
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function remove(item) {
  if (!window.confirm(t('cottageReminders.confirmDelete', { title: item.title }))) return;
  try {
    await deleteCottageReminder(item.rid);
    await load();
    showMessage(t('cottageReminders.deletedToast'));
  } catch (error) {
    showMessage(parseError(error));
  }
}

onMounted(load);
</script>

<style scoped>
.cottage-reminders { display: grid; gap: 1rem; }
.reminders-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.reminders-header h2 { margin: 0; font-size: 1.4rem; color: #2f3754; }
.reminders-header p { margin: 0.35rem 0 0; color: var(--text-soft); font-size: 0.9rem; }
.reminders-back {
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
.reminder-form { display: grid; gap: 0.7rem; }
.reminder-form textarea { min-height: 5rem; resize: vertical; }
.btn {
  border: 0;
  border-radius: 12px;
  padding: 0.62rem 0.95rem;
  background: linear-gradient(120deg, #dc4b78, #8f9bff);
  color: #fff;
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
}
.btn:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}
.reminder-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) 160px auto;
  gap: 0.6rem;
}
.reminder-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}
.reminder-counts {
  border-radius: 14px;
  padding: 0.75rem 0.95rem;
  min-width: 140px;
}
.reminder-counts span {
  display: block;
  color: #dc4b78;
  font-size: 1.35rem;
  font-weight: 800;
}
.reminder-counts p { margin: 0.15rem 0 0; color: var(--text-soft); font-size: 0.78rem; }
.include-done {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  color: #475569;
  font-size: 0.84rem;
}
.reminder-list { display: grid; gap: 0.8rem; }
.reminder-card {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem;
  border-radius: 16px;
}
.reminder-card.due {
  border-color: rgba(220, 75, 120, 0.35);
  background: rgba(255, 244, 248, 0.82);
}
.reminder-card.done { opacity: 0.7; }
.reminder-main { min-width: 0; display: grid; gap: 0.45rem; }
.reminder-head {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
}
.reminder-head h3 {
  margin: 0;
  color: #2f3754;
  font-size: 1rem;
  overflow-wrap: anywhere;
}
.audience-pill {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 0.18rem 0.55rem;
  background: rgba(167, 139, 250, 0.14);
  color: #7c3aed;
  font-size: 0.72rem;
}
.reminder-note {
  margin: 0;
  color: var(--text-soft);
  font-size: 0.86rem;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.reminder-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  color: var(--text-soft);
  font-size: 0.78rem;
}
.due-text { color: #dc4b78; font-weight: 700; }
.reminder-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 0.7rem;
}
.btn-small {
  border: 0;
  border-radius: 10px;
  padding: 0.42rem 0.85rem;
  background: #dc4b78;
  color: #fff;
  cursor: pointer;
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
@media (max-width: 768px) {
  .reminders-header,
  .reminder-toolbar,
  .reminder-card,
  .reminder-head {
    flex-direction: column;
  }
  .reminders-back { width: 100%; justify-content: center; }
  .reminder-row { grid-template-columns: 1fr; }
  .reminder-actions { justify-content: flex-start; }
}
</style>
