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
  <div class="content-section search-page">
    <ModuleTabs :items="contentTabs" :label="t('search.tabAriaLabel')" />

    <article class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t('search.title') }}</h2>
        <button class="ghost-btn" :disabled="loading" @click="runSearch">
          {{ loading ? t('search.searching') : t('search.refresh') }}
        </button>
      </div>

      <form class="search-form" @submit.prevent="runSearch">
        <label class="search-field search-field--wide">
          {{ t('search.keywordLabel') }}
          <input v-model.trim="filters.q" class="input" maxlength="120" :placeholder="t('search.keywordPlaceholder')" />
        </label>

        <label class="search-field">
          {{ t('search.tagsLabel') }}
          <input v-model.trim="filters.tags" class="input" maxlength="240" :placeholder="t('search.tagsPlaceholder')" />
        </label>

        <label class="search-field">
          {{ t('search.tagMatchLabel') }}
          <select v-model="filters.tagMode" class="input">
            <option value="any">{{ t('search.tagMatchAny') }}</option>
            <option value="all">{{ t('search.tagMatchAll') }}</option>
          </select>
        </label>

        <label class="search-field">
          {{ t('search.dateFromLabel') }}
          <input v-model="filters.dateFrom" class="input" type="date" />
        </label>

        <label class="search-field">
          {{ t('search.dateToLabel') }}
          <input v-model="filters.dateTo" class="input" type="date" />
        </label>

        <div class="type-filter search-field--wide">
          <span class="type-filter-label">{{ t('search.contentTypeLabel') }}</span>
          <label v-for="item in contentTypes" :key="item.value" class="type-chip">
            <input v-model="selectedTypes" type="checkbox" :value="item.value" />
            <span>{{ item.label }}</span>
          </label>
        </div>

        <div class="search-actions search-field--wide">
          <button class="btn-primary" :disabled="loading">
            {{ loading ? t('search.searching') : t('search.search') }}
          </button>
          <button type="button" class="ghost-btn" @click="resetFilters">{{ t('search.clear') }}</button>
        </div>
      </form>
    </article>

    <!-- AI 语义搜索：仅在 /ai/status 启用且支持 semantic_search 时显示 -->
    <article v-if="aiSearchEnabled" class="glass-card section-block ai-search-card">
      <div class="section-header">
        <h2>{{ t('search.aiTitle') }} <span class="ai-search-badge" aria-hidden="true">AI</span></h2>
      </div>
      <p class="ai-search-desc">{{ t('search.aiDesc') }}</p>

      <form class="ai-search-form" @submit.prevent="runAiSearch">
        <input v-model.trim="aiQuery" class="input" maxlength="120" :placeholder="t('search.aiPlaceholder')" />
        <button class="btn-primary" type="submit" :disabled="aiLoading || !aiQuery">
          {{ aiLoading ? t('search.aiSearching') : t('search.aiSearch') }}
        </button>
      </form>

      <div v-if="aiError" class="ai-search-error" role="alert">{{ aiError }}</div>

      <template v-else-if="aiResults.length">
        <p class="ai-search-meta">{{ t('search.aiIndexed', { count: aiIndexedCount }) }}</p>
        <ul class="entity-list search-results">
          <li v-for="item in aiResults" :key="item.aid" class="entity-item search-result">
            <div class="result-main">
              <div class="entity-top">
                <p class="entity-title">{{ item.title || t('search.typeArticle') }}</p>
                <div class="entity-tags">
                  <span class="pill pill--type">{{ t('search.typeArticle') }}</span>
                  <span class="pill ai-score-pill">{{ t('search.aiScore', { score: scorePercent(item.score) }) }}</span>
                </div>
              </div>
              <p class="entity-desc result-snippet">{{ item.snippet || t('search.noSnippet') }}</p>
              <p class="result-meta">{{ formatDate(item.updated_at) }}</p>
            </div>
            <router-link class="text-btn result-link" :to="`/articles/${item.aid}`">{{ t('search.view') }}</router-link>
          </li>
        </ul>
      </template>
      <p v-else-if="aiSearched && !aiLoading" class="muted">{{ t('search.aiNoResults') }}</p>
    </article>

    <article class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t('search.resultsTitle') }}</h2>
        <p class="result-count">{{ loading ? t('search.querying') : t('search.resultCount', { count: total }) }}</p>
      </div>

      <ul class="entity-list search-results">
        <li v-for="item in results" :key="`${item.type}-${item.id}`" class="entity-item search-result">
          <div class="result-main">
            <div class="entity-top">
              <p class="entity-title">{{ item.title || typeLabel(item.type) }}</p>
              <div class="entity-tags">
                <span class="pill pill--type">{{ typeLabel(item.type) }}</span>
                <span v-if="item.is_encrypted" class="pill pill--gold">{{ t('search.encrypted') }}</span>
                <span v-if="item.visibility === 'Private'" class="pill pill--gray">{{ t('search.private') }}</span>
                <span v-if="item.visibility === 'PartnersOnly'" class="pill pill--mint">{{ t('search.partnersVisible') }}</span>
              </div>
            </div>
            <p class="entity-desc result-snippet">{{ item.snippet || t('search.noSnippet') }}</p>
            <div v-if="item.tags && item.tags.length" class="result-tags">
              <span v-for="tag in item.tags" :key="tag" class="tag-pill">#{{ tag }}</span>
            </div>
            <p class="result-meta">
              {{ item.author_nickname || t('search.system') }} · {{ formatDate(item.date) }}
            </p>
          </div>
          <router-link class="text-btn result-link" :to="item.url">{{ t('search.view') }}</router-link>
        </li>
        <li v-if="!results.length && !loading" class="muted">{{ t('search.noResults') }}</li>
      </ul>

      <div v-if="hasMore" class="load-more">
        <button class="text-btn" :disabled="loading" @click="loadMore">{{ t('search.loadMore') }}</button>
      </div>
    </article>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue";
import ModuleTabs from "../components/ModuleTabs.vue";
import { aiSearchArticles, fetchAiStatus, fetchSearch } from "../lib/api";
import { parseError } from "../utils/helpers";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const showMessage = inject("showMessage");
const contentTabs = [
  { label: t('search.tabArticles'), to: "/articles" },
  { label: t('search.tabAlbums'), to: "/albums" },
  { label: t('search.tabSearch'), to: "/search" }
];

const contentTypes = [
  { value: "article", label: t('search.typeArticle') },
  { value: "moment", label: t('search.typeMoment') },
  { value: "album", label: t('search.typeAlbum') },
  { value: "event", label: t('search.typeEvent') },
  { value: "message", label: t('search.typeMessage') }
];

const labels = {
  article: t('search.typeArticle'),
  moment: t('search.typeMoment'),
  album: t('search.typeAlbum'),
  event: t('search.typeEvent'),
  message: t('search.typeMessage')
};

const filters = reactive({
  q: "",
  tags: "",
  tagMode: "any",
  dateFrom: "",
  dateTo: ""
});

const selectedTypes = ref(contentTypes.map((item) => item.value));
const results = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);

// AI 语义搜索（按 /ai/status 显隐）
const aiSearchEnabled = ref(false);
const aiQuery = ref("");
const aiLoading = ref(false);
const aiSearched = ref(false);
const aiResults = ref([]);
const aiIndexedCount = ref(0);
const aiError = ref("");

const hasMore = computed(() => results.value.length < total.value);

function typeLabel(type) {
  return labels[type] || type;
}

function buildParams(targetPage) {
  return {
    q: filters.q || undefined,
    tags: filters.tags || undefined,
    tag_mode: filters.tagMode,
    types: selectedTypes.value.join(","),
    date_from: filters.dateFrom || undefined,
    date_to: filters.dateTo || undefined,
    page: targetPage,
    page_size: pageSize
  };
}

function formatDate(raw) {
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? raw : date.toLocaleString();
}

async function runSearch(targetPage = 1) {
  loading.value = true;
  try {
    const data = await fetchSearch(buildParams(targetPage));
    page.value = data.page || targetPage;
    total.value = data.total || 0;
    if (targetPage === 1) {
      results.value = data.items || [];
    } else {
      results.value = [...results.value, ...(data.items || [])];
    }
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  filters.q = "";
  filters.tags = "";
  filters.tagMode = "any";
  filters.dateFrom = "";
  filters.dateTo = "";
  selectedTypes.value = contentTypes.map((item) => item.value);
  runSearch();
}

function loadMore() {
  if (loading.value || !hasMore.value) return;
  runSearch(page.value + 1);
}

// ── AI 语义搜索 ───────────────────────────────────────────────────────────
async function loadAiStatus() {
  try {
    const status = await fetchAiStatus();
    aiSearchEnabled.value = Boolean(
      status?.enabled && (status?.features || []).includes("semantic_search")
    );
  } catch (_) {
    // AI 未配置或网络失败 → 隐藏入口
    aiSearchEnabled.value = false;
  }
}

function scorePercent(score) {
  const value = Math.round((Number(score) || 0) * 100);
  return Math.min(100, Math.max(0, value));
}

async function runAiSearch() {
  if (aiLoading.value || !aiQuery.value) return;
  aiLoading.value = true;
  aiSearched.value = true;
  aiError.value = "";
  try {
    const data = await aiSearchArticles(aiQuery.value, 5);
    aiResults.value = data.results || [];
    aiIndexedCount.value = data.indexed_count || 0;
  } catch (error) {
    aiResults.value = [];
    aiIndexedCount.value = 0;
    const status = error?.response?.status;
    aiError.value = !status || status === 503 ? t("aiFeature.unavailable") : parseError(error);
  } finally {
    aiLoading.value = false;
  }
}

onMounted(() => {
  runSearch();
  loadAiStatus();
});
</script>

<style scoped>
.search-page {
  gap: 1rem;
}

.search-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.search-field {
  display: grid;
  gap: 0.35rem;
  color: #475569;
  font-size: 0.82rem;
  font-weight: 600;
}

.search-field--wide {
  grid-column: span 2;
}

.type-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  align-items: center;
}

.type-filter-label {
  flex-basis: 100%;
  color: #475569;
  font-size: 0.82rem;
  font-weight: 600;
}

.type-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: 1px solid rgb(148 163 184 / 0.4);
  border-radius: 999px;
  padding: 0.4rem 0.7rem;
  background: rgb(255 255 255 / 0.72);
  color: #334155;
  font-size: 0.8rem;
  cursor: pointer;
}

.search-actions {
  display: flex;
  gap: 0.65rem;
  align-items: center;
}

.result-count {
  margin: 0;
  color: #64748b;
  font-size: 0.82rem;
}

/* AI 语义搜索 */
.ai-search-card {
  display: grid;
  gap: 0.7rem;
}

.ai-search-badge {
  display: inline-flex;
  align-items: center;
  margin-left: 0.4rem;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
  font-size: 0.66rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  vertical-align: middle;
}

.ai-search-desc {
  margin: 0;
  color: #64748b;
  font-size: 0.82rem;
}

.ai-search-form {
  display: flex;
  gap: 0.65rem;
}

.ai-search-form .input {
  flex: 1;
  min-width: 0;
}

.ai-search-error {
  color: #b91c1c;
  font-size: 0.85rem;
  font-weight: 600;
}

.ai-search-meta {
  margin: 0;
  color: #94a3b8;
  font-size: 0.77rem;
}

.ai-score-pill {
  background: #fdf2f8;
  color: #be185d;
}

.search-result {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}

.result-main {
  flex: 1;
  min-width: 0;
}

.result-snippet {
  white-space: pre-wrap;
}

.result-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.55rem;
}

.tag-pill {
  border-radius: 999px;
  padding: 0.14rem 0.5rem;
  color: #31566a;
  background: #e0f2fe;
  font-size: 0.72rem;
  font-weight: 600;
}

.result-meta {
  margin: 0.55rem 0 0;
  color: #94a3b8;
  font-size: 0.77rem;
}

.result-link {
  flex-shrink: 0;
}

.pill--type {
  background: #e0e7ff;
  color: #3730a3;
}

.pill--gray {
  background: #f1f5f9;
  color: #64748b;
}

.load-more {
  text-align: center;
  margin-top: 1rem;
}

@media (max-width: 768px) {
  .search-form {
    grid-template-columns: 1fr;
  }

  .search-field--wide {
    grid-column: span 1;
  }

  .ai-search-form {
    flex-direction: column;
  }

  .search-result {
    display: grid;
  }
}
</style>
