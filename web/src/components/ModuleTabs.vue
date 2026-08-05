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
  <nav class="module-tabs" :aria-label="label || t('moduleTabs.navLabel')">
    <router-link
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      class="module-tab"
      exact-active-class="module-tab--active"
    >
      {{ item.label }}
    </router-link>
  </nav>
</template>

<script setup>
import { useI18n } from "vue-i18n";

const { t } = useI18n();

defineProps({
  items: {
    type: Array,
    required: true
  },
  label: {
    type: String,
    default: ""
  }
});
</script>

<style scoped>
.module-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.module-tab {
  padding: 0.45rem 0.9rem;
  border-radius: var(--radius-control);
  text-decoration: none;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-soft);
  background: var(--surface-raised);
  border: 1px solid var(--border-subtle);
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.module-tab--active {
  color: var(--brand-strong);
  border-color: #efc3d1;
  background: var(--brand-soft);
}
</style>
