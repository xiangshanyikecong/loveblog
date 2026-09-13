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
  <section class="relationship-summary glass-card">
    <div class="relationship-summary-head">
      <div>
        <p class="relationship-summary-label">{{ t('dashboard.togetherLabel') }}</p>
        <h2>{{ t('dashboard.dayN', { n: days }) }}</h2>
      </div>
      <Heart class="relationship-summary-icon" :size="28" :stroke-width="1.8" fill="currentColor" aria-hidden="true" />
    </div>
    <div class="relationship-summary-body">
      <div class="love-timer">
        <span class="love-timer-number">{{ pad2(hours) }}</span>
        <span class="love-timer-label">{{ t('dashboard.hours') }}</span>
        <span class="love-timer-number">{{ pad2(minutes) }}</span>
        <span class="love-timer-label">{{ t('dashboard.minutes') }}</span>
        <span class="love-timer-number">{{ pad2(seconds) }}</span>
        <span class="love-timer-label">{{ t('dashboard.seconds') }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { Heart } from "@lucide/vue";
import { pad2 } from "../utils/helpers";

// The per-second tick lives entirely inside this component so the parent
// dashboard view is not re-rendered every second. The parent only receives a
// rare "day-advance" event (once per 24h) to keep the hero days counter in sync.
const props = defineProps({
  initialClock: {
    type: Object,
    default: () => ({ days: 0, hours: 0, minutes: 0, seconds: 0 })
  }
});

const emit = defineEmits(["day-advance"]);

const { t } = useI18n();
const days = ref(props.initialClock.days ?? 0);
const hours = ref(props.initialClock.hours ?? 0);
const minutes = ref(props.initialClock.minutes ?? 0);
const seconds = ref(props.initialClock.seconds ?? 0);

let interval = null;

function applyClock(clock) {
  if (!clock) return;
  days.value = clock.days ?? 0;
  hours.value = clock.hours ?? 0;
  minutes.value = clock.minutes ?? 0;
  seconds.value = clock.seconds ?? 0;
}

watch(() => props.initialClock, applyClock);

function tick() {
  seconds.value += 1;
  if (seconds.value >= 60) {
    seconds.value = 0;
    minutes.value += 1;
    if (minutes.value >= 60) {
      minutes.value = 0;
      hours.value += 1;
      if (hours.value >= 24) {
        hours.value = 0;
        days.value += 1;
        emit("day-advance");
      }
    }
  }
}

onMounted(() => {
  interval = setInterval(tick, 1000);
});

onUnmounted(() => {
  if (interval) {
    clearInterval(interval);
    interval = null;
  }
});
</script>

<style scoped>
.relationship-summary {
  display: grid;
  gap: 1.15rem;
  padding: 1.2rem 1.35rem;
}

.relationship-summary-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.relationship-summary-label {
  margin: 0;
  color: var(--text-soft);
  font-size: 0.78rem;
  font-weight: 700;
}

.relationship-summary h2 {
  margin: 0.28rem 0 0;
  color: var(--text-main);
  font-size: 1.45rem;
}

.relationship-summary-icon {
  color: var(--brand);
}

.relationship-summary-body {
  display: flex;
  align-items: baseline;
}

.relationship-summary .love-timer {
  margin-top: 0;
}
</style>
