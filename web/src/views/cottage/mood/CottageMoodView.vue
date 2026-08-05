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
  <div class="content-section mood-shell">
    <div class="mood-head">
      <router-link to="/cottage" class="mood-back" :aria-label="t('cottageMood.back')">‹</router-link>
      <h2>{{ t('cottageMood.title') }}</h2>
    </div>

    <!-- 今日双人心情 -->
    <section class="glass-card section-block mood-today">
      <div class="mood-today-row">
        <div class="mood-today-card">
          <span class="mood-today-who">{{ t('cottageMood.meToday', { label: todayLabel }) }}</span>
          <div class="mood-today-face" :style="mineFaceStyle">
            {{ mine ? mine.emoji : "＋" }}
          </div>
          <span class="mood-today-name">{{ mine ? moodLabel(mine.mood) : t('cottageMood.notCheckedIn') }}</span>
          <p v-if="mine && mine.note" class="mood-today-note">{{ mine.note }}</p>
        </div>
        <div class="mood-today-heart">💞</div>
        <div class="mood-today-card">
          <span class="mood-today-who">{{ partnerName }}</span>
          <div class="mood-today-face" :style="partnerFaceStyle">
            {{ partner ? partner.emoji : "…" }}
          </div>
          <span class="mood-today-name">{{ partner ? moodLabel(partner.mood) : t('cottageMood.notCheckedIn') }}</span>
          <p v-if="partner && partner.note" class="mood-today-note">{{ partner.note }}</p>
        </div>
      </div>
    </section>

    <!-- 打卡 -->
    <section class="glass-card section-block">
      <h3 class="mood-form-title">{{ mine ? t('cottageMood.updateTitle') : t('cottageMood.newTitle') }}</h3>
      <div class="mood-palette">
        <button
          v-for="m in palette"
          :key="m.key"
          type="button"
          class="mood-chip"
          :class="{ active: form.mood === m.key }"
          :style="form.mood === m.key ? { background: m.color, borderColor: m.color } : {}"
          @click="form.mood = m.key"
        >
          <span class="mood-chip-emoji">{{ m.emoji }}</span>
          <span class="mood-chip-label">{{ m.label }}</span>
        </button>
      </div>
      <textarea
        v-model="form.note"
        class="input mood-note"
        maxlength="500"
        :placeholder="t('cottageMood.notePlaceholder')"
      ></textarea>
      <div class="mood-form-actions">
        <button class="btn mood-save" :disabled="!form.mood || saving" @click="save">
          {{ saving ? t('cottageMood.saving') : mine ? t('cottageMood.update') : t('cottageMood.checkIn') }}
        </button>
      </div>
    </section>

    <!-- 情绪日历 -->
    <section class="glass-card section-block mood-cal">
      <div class="mood-cal-head">
        <button class="mood-cal-nav" :aria-label="t('cottageMood.prevMonth')" @click="shiftMonth(-1)">‹</button>
        <span class="mood-cal-title">{{ t('cottageMood.monthTitle', { year: view.year, month: view.month }) }}</span>
        <button class="mood-cal-nav" :disabled="isCurrentMonth" :aria-label="t('cottageMood.nextMonth')" @click="shiftMonth(1)">›</button>
      </div>

      <div class="mood-cal-weekdays">
        <span v-for="w in weekdays" :key="w">{{ w }}</span>
      </div>

      <div class="mood-cal-grid">
        <button
          v-for="(cell, idx) in cells"
          :key="idx"
          type="button"
          class="mood-cell"
          :class="{ blank: !cell, today: cell && cell.dateStr === todayStr, selected: cell && cell.dateStr === selectedDate }"
          :disabled="!cell"
          @click="cell && (selectedDate = cell.dateStr)"
        >
          <template v-if="cell">
            <span class="mood-cell-day">{{ cell.day }}</span>
            <span class="mood-cell-faces">
              <span v-if="cell.mine" class="mood-cell-face" :title="t('cottageMood.meLabel')">{{ cell.mine.emoji }}</span>
              <span v-if="cell.partner" class="mood-cell-face" :title="t('cottageMood.partnerLabel')">{{ cell.partner.emoji }}</span>
            </span>
          </template>
        </button>
      </div>

      <!-- 选中日详情 -->
      <div v-if="selectedDetail" class="mood-detail">
        <p class="mood-detail-date">{{ formatLongDate(selectedDate) }}</p>
        <div class="mood-detail-row">
          <span class="mood-detail-who">{{ t('cottageMood.meLabel') }}</span>
          <template v-if="selectedDetail.mine">
            <span class="mood-detail-emoji">{{ selectedDetail.mine.emoji }}</span>
            <span class="mood-detail-name">{{ moodLabel(selectedDetail.mine.mood) }}</span>
            <span v-if="selectedDetail.mine.note" class="mood-detail-note">「{{ selectedDetail.mine.note }}」</span>
          </template>
          <span v-else class="mood-detail-empty">{{ t('cottageMood.noRecord') }}</span>
        </div>
        <div class="mood-detail-row">
          <span class="mood-detail-who">{{ partnerName }}</span>
          <template v-if="selectedDetail.partner">
            <span class="mood-detail-emoji">{{ selectedDetail.partner.emoji }}</span>
            <span class="mood-detail-name">{{ moodLabel(selectedDetail.partner.mood) }}</span>
            <span v-if="selectedDetail.partner.note" class="mood-detail-note">「{{ selectedDetail.partner.note }}」</span>
          </template>
          <span v-else class="mood-detail-empty">{{ t('cottageMood.noRecord') }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { fetchMoodCalendar, fetchMoodToday, upsertMood } from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

const palette = computed(() => [
  { key: "happy", emoji: "😄", label: t("cottageMood.moodHappy"), color: "#fcd34d" },
  { key: "loved", emoji: "🥰", label: t("cottageMood.moodLoved"), color: "#fb7185" },
  { key: "calm", emoji: "😌", label: t("cottageMood.moodCalm"), color: "#93c5fd" },
  { key: "excited", emoji: "🤩", label: t("cottageMood.moodExcited"), color: "#f9a8d4" },
  { key: "tired", emoji: "😪", label: t("cottageMood.moodTired"), color: "#c4b5fd" },
  { key: "sad", emoji: "😢", label: t("cottageMood.moodSad"), color: "#a5b4cf" },
  { key: "angry", emoji: "😡", label: t("cottageMood.moodAngry"), color: "#fca5a5" },
  { key: "sick", emoji: "🤒", label: t("cottageMood.moodSick"), color: "#6ee7b7" },
]);
const paletteByKey = computed(() => Object.fromEntries(palette.value.map((p) => [p.key, p])));
const weekdays = computed(() => [
  t("cottageMood.weekdaySun"), t("cottageMood.weekdayMon"), t("cottageMood.weekdayTue"),
  t("cottageMood.weekdayWed"), t("cottageMood.weekdayThu"), t("cottageMood.weekdayFri"),
  t("cottageMood.weekdaySat"),
]);

function localDateStr(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const now = new Date();
const todayStr = localDateStr(now);

const mine = ref(null);
const partner = ref(null);
const partnerNameRef = ref("");
const saving = ref(false);

const form = reactive({ mood: "", note: "" });

const view = reactive({ year: now.getFullYear(), month: now.getMonth() + 1 });
const calItems = ref([]);
const selectedDate = ref(todayStr);

const partnerName = computed(() => partnerNameRef.value || t("cottageMood.defaultPartner"));
const todayLabel = computed(() => t("cottageMood.today"));
const isCurrentMonth = computed(
  () => view.year === now.getFullYear() && view.month === now.getMonth() + 1
);

function moodLabel(key) {
  return paletteByKey.value[key] ? paletteByKey.value[key].label : key;
}

const mineFaceStyle = computed(() =>
  mine.value && paletteByKey.value[mine.value.mood]
    ? { background: paletteByKey.value[mine.value.mood].color }
    : {}
);
const partnerFaceStyle = computed(() =>
  partner.value && paletteByKey.value[partner.value.mood]
    ? { background: paletteByKey.value[partner.value.mood].color }
    : {}
);

// Map: dateStr -> { mine, partner }
const byDate = computed(() => {
  const map = {};
  for (const item of calItems.value) {
    const key = item.mood_date;
    if (!map[key]) map[key] = { mine: null, partner: null };
    if (item.is_self) map[key].mine = item;
    else map[key].partner = item;
  }
  return map;
});

const cells = computed(() => {
  const first = new Date(view.year, view.month - 1, 1);
  const startWeekday = first.getDay(); // 0 = Sunday
  const daysInMonth = new Date(view.year, view.month, 0).getDate();
  const out = [];
  for (let i = 0; i < startWeekday; i += 1) out.push(null);
  for (let day = 1; day <= daysInMonth; day += 1) {
    const dateStr = `${view.year}-${String(view.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const moods = byDate.value[dateStr] || { mine: null, partner: null };
    out.push({ day, dateStr, mine: moods.mine, partner: moods.partner });
  }
  return out;
});

const selectedDetail = computed(() => byDate.value[selectedDate.value] || { mine: null, partner: null });

function formatLongDate(raw) {
  const d = new Date(`${raw}T00:00:00`);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric", weekday: "long" });
}

async function loadToday() {
  try {
    const data = await fetchMoodToday(todayStr);
    mine.value = data.mine;
    partner.value = data.partner;
    if (data.partner && data.partner.author_nickname) {
      partnerNameRef.value = data.partner.author_nickname;
    }
    if (data.mine) {
      form.mood = data.mine.mood;
      form.note = data.mine.note || "";
    }
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function loadCalendar() {
  try {
    const data = await fetchMoodCalendar(view.year, view.month);
    calItems.value = data.items || [];
    // Pick up partner nickname from calendar too (covers months with history).
    if (!partnerNameRef.value) {
      const other = calItems.value.find((i) => !i.is_self);
      if (other && other.author_nickname) partnerNameRef.value = other.author_nickname;
    }
  } catch (error) {
    showMessage(parseError(error));
  }
}

function shiftMonth(delta) {
  let y = view.year;
  let m = view.month + delta;
  if (m < 1) {
    m = 12;
    y -= 1;
  } else if (m > 12) {
    m = 1;
    y += 1;
  }
  if (y > now.getFullYear() || (y === now.getFullYear() && m > now.getMonth() + 1)) {
    return; // don't navigate into the future
  }
  view.year = y;
  view.month = m;
  loadCalendar();
}

async function save() {
  if (!form.mood || saving.value) return;
  saving.value = true;
  try {
    const chip = paletteByKey.value[form.mood];
    await upsertMood({
      mood: form.mood,
      emoji: chip ? chip.emoji : null,
      note: form.note.trim() || null,
      mood_date: todayStr,
    });
    showMessage(t("cottageMood.savedToast"));
    await Promise.all([loadToday(), loadCalendar()]);
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await Promise.all([loadToday(), loadCalendar()]);
});
</script>

<style scoped>
.mood-shell {
  display: grid;
  gap: 1rem;
}
.mood-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.2rem 0.2rem 0;
}
.mood-back {
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
.mood-head h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #2f3754;
}

/* Today */
.mood-today-row {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}
.mood-today-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  text-align: center;
  min-width: 0;
}
.mood-today-who {
  font-size: 0.78rem;
  color: var(--text-soft);
}
.mood-today-face {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2rem;
  background: rgba(148, 163, 184, 0.16);
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.6);
}
.mood-today-name {
  font-size: 0.88rem;
  font-weight: 600;
  color: #2f3754;
}
.mood-today-note {
  margin: 0;
  font-size: 0.76rem;
  color: var(--text-soft);
  word-break: break-word;
}
.mood-today-heart {
  font-size: 1.5rem;
  flex: 0 0 auto;
}

/* Palette */
.mood-form-title {
  margin: 0 0 0.7rem;
  font-size: 1rem;
  color: #2f3754;
}
.mood-palette {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
}
.mood-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  padding: 0.55rem 0.3rem;
  border-radius: 14px;
  border: 1.5px solid rgba(148, 163, 184, 0.3);
  background: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: transform 0.12s ease;
}
.mood-chip:hover {
  transform: translateY(-2px);
}
.mood-chip.active {
  color: #4a2740;
  font-weight: 700;
  box-shadow: 0 8px 16px rgba(143, 155, 255, 0.22);
}
.mood-chip-emoji {
  font-size: 1.4rem;
  line-height: 1;
}
.mood-chip-label {
  font-size: 0.74rem;
  color: inherit;
}
.mood-note {
  margin-top: 0.7rem;
  min-height: 3.5rem;
  resize: vertical;
}
.mood-form-actions {
  margin-top: 0.7rem;
  display: flex;
  justify-content: flex-end;
}
.mood-save {
  min-width: 120px;
}

/* Calendar */
.mood-cal-head {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-bottom: 0.6rem;
}
.mood-cal-title {
  font-size: 1rem;
  font-weight: 700;
  color: #2f3754;
}
.mood-cal-nav {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1px solid rgba(148, 163, 184, 0.36);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  font-size: 1.1rem;
  cursor: pointer;
}
.mood-cal-nav:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.mood-cal-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  font-size: 0.72rem;
  color: var(--text-soft);
  margin-bottom: 0.3rem;
}
.mood-cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.3rem;
}
.mood-cell {
  aspect-ratio: 1 / 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 0.1rem;
  padding: 0.25rem 0;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.55);
  cursor: pointer;
  overflow: hidden;
}
.mood-cell.blank {
  border: none;
  background: transparent;
  cursor: default;
}
.mood-cell.today {
  border-color: rgba(143, 155, 255, 0.75);
  box-shadow: inset 0 0 0 1px rgba(143, 155, 255, 0.5);
}
.mood-cell.selected {
  background: rgba(167, 139, 250, 0.16);
  border-color: rgba(143, 155, 255, 0.7);
}
.mood-cell-day {
  font-size: 0.7rem;
  color: var(--text-soft);
}
.mood-cell-faces {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.05rem;
  font-size: 0.95rem;
  line-height: 1;
}

/* Detail */
.mood-detail {
  margin-top: 0.9rem;
  padding-top: 0.8rem;
  border-top: 1px dashed rgba(148, 163, 184, 0.3);
  display: grid;
  gap: 0.45rem;
}
.mood-detail-date {
  margin: 0;
  font-size: 0.82rem;
  font-weight: 600;
  color: #2f3754;
}
.mood-detail-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.84rem;
  flex-wrap: wrap;
}
.mood-detail-who {
  flex: 0 0 auto;
  min-width: 2.4rem;
  color: var(--text-soft);
}
.mood-detail-emoji {
  font-size: 1.1rem;
}
.mood-detail-name {
  font-weight: 600;
  color: #2f3754;
}
.mood-detail-note {
  color: var(--text-soft);
  word-break: break-word;
}
.mood-detail-empty {
  color: #b6bccd;
}

@media (max-width: 480px) {
  .mood-palette { grid-template-columns: repeat(4, 1fr); }
  .mood-chip-label { font-size: 0.68rem; }
}
</style>
