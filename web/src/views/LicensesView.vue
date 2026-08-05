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
  <div class="licenses-page">
    <header class="licenses-header">
      <div>
        <p class="licenses-eyebrow">LEGAL</p>
        <h1>{{ t('licenses.title') }}</h1>
        <p>{{ t('licenses.description') }}</p>
      </div>
      <a class="source-link" href="/THIRD_PARTY_LICENSES.md" target="_blank" rel="noopener">
        {{ t('licenses.openOriginal') }}
      </a>
    </header>

    <div class="license-tabs" role="tablist" :aria-label="t('licenses.tabsAriaLabel')">
      <button
        v-for="item in documents"
        :key="item.key"
        type="button"
        :class="['license-tab', activeDocument === item.key && 'license-tab--active']"
        role="tab"
        :aria-selected="activeDocument === item.key"
        @click="activeDocument = item.key"
      >
        {{ item.label }}
      </button>
    </div>

    <section class="license-document" aria-live="polite">
      <p v-if="loading" class="document-state">{{ t('licenses.loading') }}</p>
      <p v-else-if="error" class="document-state document-state--error">{{ error }}</p>
      <pre v-else>{{ content }}</pre>
    </section>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const documents = [
  { key: "notice", label: t('licenses.noticeLabel'), path: "/NOTICE" },
  { key: "licenses", label: t('licenses.fullLicensesLabel'), path: "/THIRD_PARTY_LICENSES.md" }
];

const activeDocument = ref("notice");
const content = ref("");
const loading = ref(false);
const error = ref("");

watch(
  activeDocument,
  async (key) => {
    const document = documents.find((item) => item.key === key);
    loading.value = true;
    error.value = "";
    try {
      const response = await fetch(document.path);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      content.value = await response.text();
    } catch {
      content.value = "";
      error.value = t('licenses.loadError');
    } finally {
      loading.value = false;
    }
  },
  { immediate: true }
);
</script>

<style scoped>
.licenses-page {
  margin-top: 1.2rem;
}

.licenses-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.2rem;
  padding: 1.4rem 0 1rem;
  border-bottom: 1px solid rgb(148 163 184 / 0.28);
}

.licenses-eyebrow {
  margin: 0 0 0.4rem;
  color: #667085;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0;
}

.licenses-header h1 {
  margin: 0;
  color: #2f3754;
  font-size: 1.55rem;
}

.licenses-header p:not(.licenses-eyebrow) {
  margin: 0.55rem 0 0;
  color: #64748b;
  font-size: 0.88rem;
}

.source-link {
  flex-shrink: 0;
  border: 1px solid rgb(148 163 184 / 0.5);
  border-radius: 8px;
  padding: 0.55rem 0.8rem;
  color: #445070;
  background: rgb(255 255 255 / 0.72);
  text-decoration: none;
  font-size: 0.8rem;
}

.license-tabs {
  display: inline-grid;
  grid-template-columns: repeat(2, minmax(7.5rem, 1fr));
  margin-top: 1rem;
  padding: 3px;
  border: 1px solid rgb(148 163 184 / 0.35);
  border-radius: 8px;
  background: rgb(255 255 255 / 0.56);
}

.license-tab {
  min-height: 38px;
  border: 0;
  border-radius: 6px;
  padding: 0.45rem 0.8rem;
  color: #5c6785;
  background: transparent;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 600;
}

.license-tab--active {
  color: #2f3754;
  background: #fff;
  box-shadow: 0 2px 8px rgb(15 23 42 / 0.08);
}

.license-document {
  margin-top: 0.8rem;
  min-height: 22rem;
  max-height: 70vh;
  overflow: auto;
  border: 1px solid rgb(148 163 184 / 0.32);
  border-radius: 8px;
  background: rgb(255 255 255 / 0.82);
}

.license-document pre {
  margin: 0;
  padding: 1rem;
  color: #334155;
  font-family: Consolas, "SFMono-Regular", monospace;
  font-size: 0.75rem;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.document-state {
  margin: 0;
  padding: 1rem;
  color: #64748b;
  font-size: 0.84rem;
}

.document-state--error {
  color: #b42318;
}

@media (max-width: 640px) {
  .licenses-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .license-tabs {
    width: 100%;
  }

  .license-document {
    max-height: 68vh;
  }
}
</style>
