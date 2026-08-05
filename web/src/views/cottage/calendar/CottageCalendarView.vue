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
  <div class="content-section cal-shell">
    <div class="cal-head">
      <router-link to="/cottage" class="cal-back" :aria-label="t('cottageCalendar.back')">‹</router-link>
      <h2>{{ t('cottageCalendar.title') }}</h2>
    </div>

    <section class="glass-card section-block">
      <div class="cal-toolbar">
        <button class="cal-nav" :aria-label="t('cottageCalendar.prevMonth')" @click="shiftMonth(-1)">‹</button>
        <span class="cal-title">{{ t('cottageCalendar.monthTitle', { year: view.year, month: view.month }) }}</span>
        <button class="cal-nav" :disabled="isCurrentMonth" :aria-label="t('cottageCalendar.nextMonth')" @click="shiftMonth(1)">›</button>
      </div>

      <div v-if="loading" class="cal-loading">{{ t('cottageCalendar.loading') }}</div>

      <template v-else>
        <div class="cal-legend">
          <span class="cal-legend-item"><span class="cal-dot cal-dot-mood"></span>{{ t('cottageCalendar.legendMood') }}</span>
          <span class="cal-legend-item"><span class="cal-dot cal-dot-event"></span>{{ t('cottageCalendar.legendEvent') }}</span>
          <span class="cal-legend-item"><span class="cal-dot cal-dot-checkin"></span>{{ t('cottageCalendar.legendCheckin') }}</span>
          <span class="cal-legend-item"><span class="cal-dot cal-dot-plan"></span>{{ t('cottageCalendar.legendPlan') }}</span>
          <span class="cal-legend-item"><span class="cal-dot cal-dot-reminder"></span>{{ t('cottageCalendar.legendReminder') }}</span>
        </div>

        <div class="cal-weekdays">
          <span v-for="w in weekdays" :key="w">{{ w }}</span>
        </div>

        <div class="cal-grid">
          <button
            v-for="(cell, idx) in cells"
            :key="idx"
            type="button"
            class="cal-cell"
            :class="{ blank: !cell, today: cell && cell.dateStr === todayStr, selected: cell && cell.dateStr === selectedDate }"
            :disabled="!cell"
            @click="cell && (selectedDate = cell.dateStr)"
          >
            <template v-if="cell">
              <span class="cal-cell-day">{{ cell.day }}</span>
              <span class="cal-cell-dots">
                <span v-if="cell.items.length" class="cal-cell-badges">
                  <span
                    v-for="(item, i) in cell.items.slice(0, 4)"
                    :key="i"
                    class="cal-cell-badge"
                    :class="`cal-dot-${item.kind}`"
                    :title="item.label"
                  >{{ item.icon }}</span>
                </span>
              </span>
            </template>
          </button>
        </div>
      </template>
    </section>

    <section v-if="selectedItems.length" class="glass-card section-block cal-detail">
      <p class="cal-detail-date">{{ formatLongDate(selectedDate) }}</p>
      <div class="cal-detail-list">
        <div v-for="(item, i) in selectedItems" :key="i" class="cal-detail-item" :class="`cal-detail-${item.kind}`">
          <span class="cal-detail-icon">{{ item.icon }}</span>
          <div class="cal-detail-body">
            <span class="cal-detail-label">{{ item.label }}</span>
            <span v-if="item.sub" class="cal-detail-sub">{{ item.sub }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  fetchCottagePlans,
  fetchCottageReminders,
  fetchEvents,
  fetchCheckins,
  fetchMoodCalendar,
} from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});
const weekdays = computed(() => [
  t('cottageCalendar.weekdaySun'),
  t('cottageCalendar.weekdayMon'),
  t('cottageCalendar.weekdayTue'),
  t('cottageCalendar.weekdayWed'),
  t('cottageCalendar.weekdayThu'),
  t('cottageCalendar.weekdayFri'),
  t('cottageCalendar.weekdaySat'),
]);

const now = new Date();
const todayStr = localDateStr(now);

const view = reactive({ year: now.getFullYear(), month: now.getMonth() + 1 });
const loading = ref(false);
const allItems = ref([]);
const selectedDate = ref(todayStr);

const isCurrentMonth = computed(
  () => view.year === now.getFullYear() && view.month === now.getMonth() + 1,
);

function localDateStr(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function isoToLocalDateStr(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return localDateStr(d);
}

function monthPrefix(year, month) {
  return `${year}-${String(month).padStart(2, "0")}`;
}

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.slice(0, len) + "…" : str;
}

// ── Data loading ──────────────────────────────────────────────────
async function loadData() {
  loading.value = true;
  const prefix = monthPrefix(view.year, view.month);
  const items = [];

  try {
    const [moodRes, eventsRes, checkinRes, planRes, reminderRes] = await Promise.allSettled([
      fetchMoodCalendar(view.year, view.month),
      fetchEvents(),
      fetchCheckins({ page: 1, page_size: 100 }),
      fetchCottagePlans(),
      fetchCottageReminders(),
    ]);

    // Mood
    if (moodRes.status === "fulfilled") {
      for (const m of moodRes.value.items || []) {
        if (!m.mood_date) continue;
        items.push({
          dateStr: m.mood_date,
          kind: "mood",
          icon: m.emoji || "😊",
          label: t('cottageCalendar.moodLabel', { name: m.is_self ? t('cottageCalendar.moodLabelSelf') : (m.author_nickname || t('cottageCalendar.moodLabelPartner')), mood: m.mood || t('cottageCalendar.moodDefault') }),
          sub: m.note || null,
        });
      }
    }

    // Events
    if (eventsRes.status === "fulfilled") {
      for (const e of eventsRes.value.items || []) {
        const ds = e.date ? String(e.date).slice(0, 10) : null;
        if (!ds || !ds.startsWith(prefix)) continue;
        const isAnniversary = e.type === "Anniversary";
        items.push({
          dateStr: ds,
          kind: "event",
          icon: isAnniversary ? "🎂" : "⏰",
          label: e.title || "纪念日",
          sub: [e.is_important ? "重要" : null, e.is_yearly_repeat ? "每年" : null, e.type].filter(Boolean).join(" · ") || null,
        });
      }
    }

    // Checkins
    if (checkinRes.status === "fulfilled") {
      for (const c of checkinRes.value.items || []) {
        const ds = isoToLocalDateStr(c.created_at);
        if (!ds || !ds.startsWith(prefix)) continue;
        items.push({
          dateStr: ds,
          kind: "checkin",
          icon: "📍",
          label: t('cottageCalendar.checkinLabel', { name: c.author_nickname || t('cottageCalendar.moodLabelPartner') }),
          sub: truncate(c.location_text || c.content, 40) || null,
        });
      }
    }

    // Plans
    if (planRes.status === "fulfilled") {
      for (const p of planRes.value.items || []) {
        const ds = p.plan_date ? String(p.plan_date).slice(0, 10) : null;
        if (!ds || !ds.startsWith(prefix)) continue;
        items.push({
          dateStr: ds,
          kind: "plan",
          icon: "📝",
          label: p.title || t('cottageCalendar.defaultPlanLabel'),
          sub: [p.status === "done" ? t('cottageCalendar.planStatusDone') : p.status === "in_progress" ? t('cottageCalendar.planStatusInProgress') : null, p.author_nickname].filter(Boolean).join(" · ") || null,
        });
      }
    }

    // Reminders
    if (reminderRes.status === "fulfilled") {
      for (const r of reminderRes.value.items || []) {
        const ds = isoToLocalDateStr(r.remind_at);
        if (!ds || !ds.startsWith(prefix)) continue;
        items.push({
          dateStr: ds,
          kind: "reminder",
          icon: "🔔",
          label: r.title || t('cottageCalendar.defaultReminderLabel'),
          sub: [r.is_done ? t('cottageCalendar.reminderDone') : r.is_due ? t('cottageCalendar.reminderDue') : null, r.audience === "me" ? t('cottageCalendar.reminderAudienceMe') : r.audience === "partner" ? t('cottageCalendar.reminderAudiencePartner') : null].filter(Boolean).join(" · ") || null,
        });
      }
    }
  } catch (error) {
    showMessage(parseError(error));
  }

  allItems.value = items;
  loading.value = false;
}

// ── Computed ──────────────────────────────────────────────────────
const byDate = computed(() => {
  const map = {};
  for (const item of allItems.value) {
    if (!map[item.dateStr]) map[item.dateStr] = [];
    map[item.dateStr].push(item);
  }
  return map;
});

const cells = computed(() => {
  const first = new Date(view.year, view.month - 1, 1);
  const startWeekday = first.getDay();
  const daysInMonth = new Date(view.year, view.month, 0).getDate();
  const out = [];
  for (let i = 0; i < startWeekday; i += 1) out.push(null);
  for (let day = 1; day <= daysInMonth; day += 1) {
    const dateStr = `${view.year}-${String(view.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    out.push({ day, dateStr, items: byDate.value[dateStr] || [] });
  }
  return out;
});

const selectedItems = computed(() => byDate.value[selectedDate.value] || []);

// ── Actions ───────────────────────────────────────────────────────
function shiftMonth(delta) {
  let y = view.year;
  let m = view.month + delta;
  if (m < 1) { m = 12; y -= 1; }
  else if (m > 12) { m = 1; y += 1; }
  if (y > now.getFullYear() || (y === now.getFullYear() && m > now.getMonth() + 1)) return;
  view.year = y;
  view.month = m;
  loadData();
}

function formatLongDate(raw) {
  const d = new Date(`${raw}T00:00:00`);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric", weekday: "long" });
}

onMounted(() => {
  loadData();
});
</script>

<style scoped>
.cal-shell {
  display: grid;
  gap: 1rem;
}
.cal-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.2rem 0.2rem 0;
}
.cal-back {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 1.4rem;
  line-height: 1;
  color: #6d77a8;
  text-decoration: none;
  background: rgba(148, 163, 184, 0.14);
}
.cal-head h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #2f3754;
}

.cal-toolbar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-bottom: 0.6rem;
}
.cal-title {
  font-size: 1rem;
  font-weight: 700;
  color: #2f3754;
}
.cal-nav {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1px solid rgba(148, 163, 184, 0.36);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  font-size: 1.1rem;
  cursor: pointer;
}
.cal-nav:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.cal-loading {
  text-align: center;
  padding: 2rem;
  color: var(--text-soft);
  font-size: 0.85rem;
}

.cal-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  justify-content: center;
  margin-bottom: 0.7rem;
}
.cal-legend-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.72rem;
  color: var(--text-soft);
}
.cal-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.cal-dot-mood { background: #fb7185; }
.cal-dot-event { background: #fcd34d; }
.cal-dot-checkin { background: #60a5fa; }
.cal-dot-plan { background: #a78bfa; }
.cal-dot-reminder { background: #34d399; }

.cal-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  font-size: 0.72rem;
  color: var(--text-soft);
  margin-bottom: 0.3rem;
}
.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.3rem;
}
.cal-cell {
  aspect-ratio: 1 / 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 0.1rem;
  padding: 0.2rem 0;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.55);
  cursor: pointer;
  overflow: hidden;
}
.cal-cell.blank {
  border: none;
  background: transparent;
  cursor: default;
}
.cal-cell.today {
  border-color: rgba(143, 155, 255, 0.75);
  box-shadow: inset 0 0 0 1px rgba(143, 155, 255, 0.5);
}
.cal-cell.selected {
  background: rgba(167, 139, 250, 0.16);
  border-color: rgba(143, 155, 255, 0.7);
}
.cal-cell-day {
  font-size: 0.7rem;
  color: var(--text-soft);
}
.cal-cell-dots {
  min-height: 1rem;
}
.cal-cell-badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.05rem;
  font-size: 0.7rem;
  line-height: 1;
}
.cal-cell-badge {
  display: inline-block;
}

/* Detail */
.cal-detail {
  display: grid;
  gap: 0.5rem;
}
.cal-detail-date {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: #2f3754;
}
.cal-detail-list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}
.cal-detail-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.5rem 0.6rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.5);
}
.cal-detail-icon {
  font-size: 1.1rem;
  flex: 0 0 auto;
}
.cal-detail-body {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}
.cal-detail-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: #2f3754;
  word-break: break-word;
}
.cal-detail-sub {
  font-size: 0.74rem;
  color: var(--text-soft);
  word-break: break-word;
}
</style>
