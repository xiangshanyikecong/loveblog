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
  <div class="content-section">
    <ModuleTabs :items="memoryTabs" :label="t('events.tabAriaLabel')" />

    <article class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t('events.timelineTitle') }}</h2>
        <button class="ghost-btn" @click="loadEvents">{{ t('events.refresh') }}</button>
      </div>

      <form v-if="canManageContent" class="form-grid" @submit.prevent="createEventItem">
        <input v-model="eventForm.title" class="input" :placeholder="t('events.titlePlaceholder')" />
        <input v-model="eventForm.date" class="input" type="date" />
        <select v-model="eventForm.type" class="input">
          <option value="Countdown">Countdown</option>
          <option value="Anniversary">Anniversary</option>
        </select>
        <input v-model="eventForm.tagsText" class="input" :placeholder="t('events.tagsPlaceholder')" />
        <div class="check-group">
          <label class="check"><input v-model="eventForm.isImportant" type="checkbox" /> {{ t('events.importantEvent') }}</label>
          <label class="check"><input v-model="eventForm.isYearlyRepeat" type="checkbox" /> {{ t('events.yearlyRepeat') }}</label>
        </div>
        <button class="btn-primary col-2" :disabled="busy">
          {{ busy ? t('events.saving') : t('events.addEvent') }}
        </button>
      </form>
    </article>

    <article class="glass-card section-block">
      <div v-if="events.length" class="events-list">
        <div
          v-for="(item, index) in events"
          :key="item.eid"
          class="event-pill"
          :style="eventGradient(index)"
        >
          <div class="event-pill-main">
            <p class="event-pill-title">{{ item.title }}</p>
            <p class="event-pill-desc">
              {{ item.type }}
              <span v-if="item.is_important"> · {{ t('events.important') }}</span>
              <span v-if="item.is_yearly_repeat"> · {{ t('events.yearlyRepeatDays', { n: item.next_occurrence_days }) }}</span>
              <span v-for="tag in item.tags || []" :key="tag"> · #{{ tag }}</span>
            </p>
          </div>
          <div class="event-pill-meta">
            <p class="event-pill-date">{{ item.date }}</p>
            <p class="event-pill-days">{{ eventStatusText(item) }}</p>
          </div>
        </div>
      </div>
      <p v-else class="muted">{{ t('events.noEvents') }}</p>
    </article>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, inject } from "vue";
import { useI18n } from "vue-i18n";
import ModuleTabs from "../components/ModuleTabs.vue";
import { fetchEvents, createEvent } from "../lib/api";
import { parseError, eventGradient, eventStatusText, parseTags } from "../utils/helpers";
import { useAuth } from "../stores/auth";

const showMessage = inject("showMessage");
const { canManageContent } = useAuth();
const { t } = useI18n();
const events = ref([]);
const busy = ref(false);
const memoryTabs = [
  { label: t("events.tabMemories"), to: "/events" },
  { label: t("events.tabTimeline"), to: "/timeline" },
  { label: t("events.tabCapsules"), to: "/capsules" }
];

const eventForm = reactive({
  title: "",
  date: "",
  type: "Countdown",
  tagsText: "",
  isImportant: false,
  isYearlyRepeat: false
});

async function loadEvents() {
  try {
    const data = await fetchEvents();
    events.value = data.items || [];
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function createEventItem() {
  busy.value = true;
  try {
    await createEvent({
      title: eventForm.title,
      date: eventForm.date,
      type: eventForm.type,
      tags: parseTags(eventForm.tagsText),
      is_important: eventForm.isImportant,
      is_yearly_repeat: eventForm.isYearlyRepeat
    });
    showMessage(t("events.createSuccess"));
    eventForm.title = "";
    eventForm.tagsText = "";
    await loadEvents();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  loadEvents();
});
</script>
