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
  <section class="countdown-card">
    <div class="countdown-head">
      <span class="countdown-icon"><CalendarHeart :size="19" :stroke-width="1.8" aria-hidden="true" /></span>
      <h3>{{ t("countdownCard.title") }}</h3>
    </div>

    <div v-if="loading" class="status-row">{{ t("countdownCard.syncing") }}</div>
    <div v-else-if="!event" class="status-row">{{ t("countdownCard.empty") }}</div>

    <template v-else>
      <p class="event-title">{{ event.title }}</p>
      <div class="timer-row">
        <span class="timer-main">{{ daysLeft }}</span>
        <span class="timer-unit">{{ t("countdownCard.dayUnit") }}</span>
      </div>
      <p class="event-meta">{{ formatDate(event.date) }}，{{ typeText }}</p>
    </template>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { CalendarHeart } from "@lucide/vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps({
  event: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
});

const typeText = computed(() => {
  if (!props.event) {
    return "";
  }
  return props.event.type === "Anniversary" ? t("countdownCard.typeAnniversary") : t("countdownCard.typeCountdown");
});

const daysLeft = computed(() => {
  if (!props.event?.date) {
    return 0;
  }

  const now = new Date();
  now.setHours(0, 0, 0, 0);

  let target = new Date(`${props.event.date}T00:00:00`);

  if (props.event.is_yearly_repeat) {
    target.setFullYear(now.getFullYear());
    if (target.getTime() < now.getTime()) {
      target.setFullYear(now.getFullYear() + 1);
    }
  }

  const ms = target.getTime() - now.getTime();
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
});

function formatDate(raw) {
  if (!raw) {
    return "";
  }
  const date = new Date(`${raw}T00:00:00`);
  return Number.isNaN(date.getTime()) ? raw : date.toLocaleDateString();
}
</script>

<style scoped>
.countdown-card {
  background: var(--surface-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  padding: 1.2rem 1.15rem;
  box-shadow: var(--shadow-soft);
}

.countdown-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.countdown-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  color: var(--brand-strong);
  border-radius: 10px;
  background: var(--brand-soft);
}

h3 {
  margin: 0;
  font-size: 0.98rem;
  color: var(--text-main);
}

.status-row {
  margin-top: 0.8rem;
  border-radius: var(--radius-control);
  border: 1px dashed var(--border-strong);
  background: var(--surface-subtle);
  padding: 0.7rem 0.75rem;
  font-size: 0.8rem;
  color: var(--text-soft);
}

.event-title {
  margin: 0.8rem 0 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-main);
}

.timer-row {
  margin-top: 0.7rem;
  display: flex;
  align-items: flex-end;
  gap: 0.3rem;
}

.timer-main {
  font-size: 2rem;
  line-height: 1;
  font-weight: 700;
  color: var(--brand-strong);
}

.timer-unit {
  font-size: 0.9rem;
  color: var(--text-soft);
  padding-bottom: 0.15rem;
}

.event-meta {
  margin: 0.45rem 0 0;
  font-size: 0.78rem;
  color: var(--text-soft);
}
</style>
