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
  <div :class="['app-state', `app-state--${tone}`]">
    <component :is="icon" class="app-state-icon" :size="24" :stroke-width="1.8" aria-hidden="true" />
    <div class="app-state-copy">
      <p class="app-state-title">{{ title }}</p>
      <p v-if="description" class="app-state-description">{{ description }}</p>
    </div>
    <router-link v-if="actionTo && actionLabel" :to="actionTo" class="app-state-action">
      {{ actionLabel }}
      <ArrowRight :size="16" :stroke-width="2" aria-hidden="true" />
    </router-link>
    <button v-else-if="actionLabel" type="button" class="app-state-action" @click="$emit('action')">
      {{ actionLabel }}
      <ArrowRight :size="16" :stroke-width="2" aria-hidden="true" />
    </button>
  </div>
</template>

<script setup>
import { ArrowRight, Inbox } from "@lucide/vue";

defineProps({
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ""
  },
  icon: {
    type: [Object, Function],
    default: Inbox
  },
  tone: {
    type: String,
    default: "neutral"
  },
  actionLabel: {
    type: String,
    default: ""
  },
  actionTo: {
    type: String,
    default: ""
  }
});

defineEmits(["action"]);
</script>

<style scoped>
.app-state {
  min-height: 108px;
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 0.45rem;
  padding: 1.1rem;
  text-align: center;
  color: var(--text-soft);
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--surface-subtle);
}

.app-state-icon {
  color: var(--brand);
}

.app-state-copy {
  display: grid;
  gap: 0.2rem;
}

.app-state-title,
.app-state-description {
  margin: 0;
}

.app-state-title {
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 700;
}

.app-state-description {
  max-width: 34rem;
  font-size: 0.8rem;
  line-height: 1.55;
}

.app-state-action {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.35rem 0.65rem;
  color: var(--brand-strong);
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}

.app-state--error {
  color: #9f3f55;
  border-color: #efb9c8;
  background: #fff5f7;
}

.app-state--error .app-state-icon,
.app-state--error .app-state-action {
  color: #b34864;
}
</style>
