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
  <div ref="root" class="lang-switcher">
    <button
      type="button"
      class="lang-switcher-btn"
      :aria-expanded="open"
      :title="t('languageSwitcher.title')"
      @click="open = !open"
    >
      <Globe :size="17" :stroke-width="2" aria-hidden="true" />
      <span class="lang-switcher-label">{{ currentLabel }}</span>
    </button>
    <ul v-if="open" class="lang-switcher-menu" role="listbox">
      <li
        v-for="loc in supportedLocales"
        :key="loc.code"
        role="option"
        :aria-selected="loc.code === current"
        :class="['lang-switcher-item', loc.code === current && 'lang-switcher-item--active']"
        @click="choose(loc.code)"
      >
        <span class="lang-switcher-flag">{{ loc.flag }}</span>
        <span>{{ loc.label }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Globe } from "@lucide/vue";
import { useI18n } from "vue-i18n";
import { supportedLocales, setLocale, getLocale } from "../locales";

const { t } = useI18n();
const root = ref(null);
const open = ref(false);
const current = ref(getLocale());

const currentLabel = computed(() => {
  const loc = supportedLocales.find((l) => l.code === current.value);
  return loc ? loc.label : "";
});

function choose(code) {
  setLocale(code);
  current.value = code;
  open.value = false;
}

function handleClickOutside(e) {
  if (root.value && !root.value.contains(e.target)) {
    open.value = false;
  }
}

onMounted(() => document.addEventListener("click", handleClickOutside));
onBeforeUnmount(() => document.removeEventListener("click", handleClickOutside));
</script>

<style scoped>
.lang-switcher {
  position: relative;
  display: inline-flex;
}

.lang-switcher-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border: 1px solid var(--border-strong);
  background: var(--surface-raised);
  border-radius: 999px;
  padding: 0.35rem 0.7rem;
  font-size: 0.74rem;
  color: var(--text-main);
  cursor: pointer;
  white-space: nowrap;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.lang-switcher-btn:hover {
  border-color: #efc3d1;
  background: var(--brand-soft);
}

.lang-switcher-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin: 0.3rem 0 0;
  padding: 0.3rem;
  list-style: none;
  background: var(--surface-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  box-shadow: 0 12px 24px rgb(39 57 50 / 0.12);
  z-index: 50;
  min-width: 130px;
}

.lang-switcher-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.6rem;
  border-radius: calc(var(--radius-control) - 2px);
  font-size: 0.8rem;
  color: var(--text-main);
  cursor: pointer;
  transition: background 0.12s ease;
}

.lang-switcher-item:hover {
  background: var(--surface-subtle);
}

.lang-switcher-item--active {
  color: var(--brand-strong);
  font-weight: 600;
}

.lang-switcher-flag {
  font-size: 1rem;
  line-height: 1;
}
</style>
