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
    <ModuleTabs :items="contentTabs" :label="t('articles.tabAriaLabel')" />

    <!-- Tabs -->
    <div class="tabs-row">
      <button :class="['tab-btn', activeTab === 'published' && 'tab-btn--active']" @click="activeTab = 'published'">{{ t('articles.publishedTab') }}</button>
      <button v-if="canManageContent" :class="['tab-btn', activeTab === 'drafts' && 'tab-btn--active']" @click="switchToDrafts">{{ t('articles.draftsTab') }} <span v-if="drafts.length" class="tab-badge">{{ drafts.length }}</span></button>
    </div>

    <!-- New Article Form -->
    <article v-if="canManageContent" class="glass-card section-block">
      <div class="section-header">
        <h2>{{ articleForm.status === 'Draft' ? t('articles.newDraftTitle') : t('articles.newArticleTitle') }}</h2>
        <div style="display:flex;gap:0.5rem;">
          <button class="ghost-btn button-with-icon" type="button" @click="$router.push({ name: 'article-editor', params: { aid: 'new' } })">
            <FilePenLine :size="16" :stroke-width="1.8" aria-hidden="true" />
            {{ t('articles.useRichEditor') }}
          </button>
          <button class="ghost-btn" type="button" @click="articleForm.status = 'Draft'">{{ t('articles.saveAsDraft') }}</button>
          <button class="ghost-btn" type="button" @click="articleForm.status = 'Published'">{{ t('articles.publishDirectly') }}</button>
        </div>
      </div>
      <form class="form-grid" @submit.prevent="createArticleItem">
        <label class="form-field col-2">
          <span>{{ t('articles.articleTitle') }}</span>
          <input v-model="articleForm.title" class="input" :placeholder="t('articles.titlePlaceholder')" required />
        </label>
        <label class="form-field col-2">
          <span>{{ t('articles.excerpt') }}</span>
          <textarea v-model="articleForm.excerpt" class="input min-h-20" :placeholder="t('articles.excerptPlaceholder')" />
        </label>
        <label class="form-field col-2">
          <span>{{ t('articles.tags') }}</span>
          <input v-model="articleForm.tagsText" class="input" :placeholder="t('articles.tagsPlaceholder')" />
        </label>
        <label class="form-field col-2">
          <span>{{ t('articles.body') }}</span>
          <textarea v-model="articleForm.blockContent" class="input min-h-28" :placeholder="t('articles.bodyPlaceholder')" />
        </label>
        <label class="form-field col-2">
          <span>{{ t('articles.visibility') }}</span>
          <select v-model="articleForm.visibility" class="input">
            <option value="public">{{ t('articles.visibilityPublic') }}</option>
            <option value="guest_viewable">{{ t('articles.visibilityGuest') }}</option>
            <option value="partners_only">{{ t('articles.visibilityPartners') }}</option>
            <option value="private">{{ t('articles.visibilityPrivate') }}</option>
            <option value="password_protected">{{ t('articles.visibilityPassword') }}</option>
          </select>
        </label>
        <label v-if="articleForm.visibility === 'password_protected'" class="form-field col-2">
          <span>{{ t('articles.accessPassword') }}</span>
          <input v-model="articleForm.password" type="password" class="input" :placeholder="t('articles.passwordPlaceholder')" />
        </label>
        <label class="check"><input v-model="articleForm.partnerCanEdit" type="checkbox" /> {{ t('articles.allowPartnerEdit') }}</label>
        <button class="btn-primary col-2" :disabled="busy">
          {{ busy ? t('articles.submitting') : (articleForm.status === 'Draft' ? t('articles.saveDraft') : t('articles.publishArticle')) }}
        </button>
      </form>
    </article>

    <!-- Published List -->
    <article v-show="activeTab === 'published'" class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t('articles.articleList') }}</h2>
        <button class="ghost-btn button-with-icon" :disabled="loadingArticles" @click="loadArticles">
          <RefreshCw :class="loadingArticles && 'is-spinning'" :size="16" :stroke-width="1.8" aria-hidden="true" />
          {{ loadingArticles ? t('articles.refreshing') : t('articles.refresh') }}
        </button>
      </div>
      <EmptyState
        v-if="articlesError && !articles.length"
        :icon="CircleAlert"
        tone="error"
        :title="t('articles.loadErrorTitle')"
        :description="articlesError"
        :action-label="t('articles.reload')"
        @action="loadArticles"
      />
      <p v-else-if="articlesError" class="refresh-error" role="alert">
        {{ t('articles.errorStillCached', { error: articlesError }) }}
      </p>
      <ul v-if="articles.length" class="entity-list">
        <li
          v-for="item in articles" :key="item.aid"
          class="entity-item article-card"
          @click="$router.push({ name: 'article-detail', params: { aid: item.aid } })"
        >
          <div class="entity-top">
            <p class="article-title">{{ item.title }}</p>
            <div class="entity-tags">
              <span v-if="item.partner_can_edit" class="pill pill--mint">{{ t('articles.coEditPill') }}</span>
              <span v-if="item.is_co_created" class="pill pill--co-create" :title="t('articles.coCreationTitle')">{{ t('articles.coCreation') }}</span>
              <span v-if="item.is_encrypted" class="pill pill--gold">{{ t('articles.encrypted') }}</span>
              <span v-for="tag in item.tags || []" :key="tag" class="pill pill--tag">#{{ tag }}</span>
            </div>
          </div>
          <p class="entity-desc">{{ item.excerpt || t('articles.clickToRead') }}</p>
          <p class="article-meta">{{ item.author_nickname }} · {{ new Date(item.published_at || item.created_at).toLocaleDateString() }}</p>
        </li>
      </ul>
      <EmptyState
        v-else-if="!articlesError"
        :icon="FileText"
        :title="t('articles.noArticlesTitle')"
        :description="t('articles.noArticlesDesc')"
      />
    </article>

    <!-- Drafts List -->
    <article v-if="canManageContent" v-show="activeTab === 'drafts'" class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t('articles.draftBox') }}</h2>
        <button class="ghost-btn button-with-icon" :disabled="loadingDrafts" @click="loadDraftsList">
          <RefreshCw :class="loadingDrafts && 'is-spinning'" :size="16" :stroke-width="1.8" aria-hidden="true" />
          {{ loadingDrafts ? t('articles.refreshing') : t('articles.refresh') }}
        </button>
      </div>
      <EmptyState
        v-if="draftsError && !drafts.length"
        :icon="CircleAlert"
        tone="error"
        :title="t('articles.draftLoadErrorTitle')"
        :description="draftsError"
        :action-label="t('articles.reload')"
        @action="loadDraftsList"
      />
      <p v-else-if="draftsError" class="refresh-error" role="alert">
        {{ t('articles.errorStillCached', { error: draftsError }) }}
      </p>
      <ul v-if="drafts.length" class="entity-list">
        <li
          v-for="item in drafts" :key="item.aid"
          class="entity-item article-card"
          @click="$router.push({ name: 'article-detail', params: { aid: item.aid } })"
        >
          <div class="entity-top">
            <p class="article-title">{{ item.title }}</p>
            <span class="pill pill--gray">{{ t('articles.draftPill') }}</span>
            <span v-for="tag in item.tags || []" :key="tag" class="pill pill--tag">#{{ tag }}</span>
          </div>
          <p class="entity-desc">{{ item.excerpt || t('articles.clickToEdit') }}</p>
          <p class="article-meta">{{ t('articles.lastModified', { date: new Date(item.created_at).toLocaleDateString() }) }}</p>
        </li>
      </ul>
      <EmptyState
        v-else-if="!draftsError"
        :icon="FileText"
        :title="t('articles.emptyDraftsTitle')"
        :description="t('articles.emptyDraftsDesc')"
      />
    </article>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, inject } from "vue";
import { useI18n } from "vue-i18n";
import { CircleAlert, FilePenLine, FileText, RefreshCw } from "@lucide/vue";
import EmptyState from "../components/EmptyState.vue";
import ModuleTabs from "../components/ModuleTabs.vue";
import { fetchArticles, fetchDrafts, createArticle } from "../lib/api";
import { parseError, parseTags } from "../utils/helpers";
import { useAuth } from "../stores/auth";

const showMessage = inject("showMessage");
const { token, canManageContent } = useAuth();
const { t } = useI18n();
const articles = ref([]);
const drafts = ref([]);
const busy = ref(false);
const loadingArticles = ref(false);
const loadingDrafts = ref(false);
const articlesError = ref("");
const draftsError = ref("");
const activeTab = ref("published");
const contentTabs = [
  { label: t("articles.tabArticles"), to: "/articles" },
  { label: t("articles.tabAlbums"), to: "/albums" },
  { label: t("articles.tabSearch"), to: "/search" }
];

const articleForm = reactive({
  title: "",
  excerpt: "",
  blockContent: "",
  tagsText: "",
  status: "Published",
  visibility: "public",
  password: "",
  partnerCanEdit: false
});

async function loadArticles() {
  loadingArticles.value = true;
  articlesError.value = "";
  try {
    const data = await fetchArticles({ only_published: !token.value });
    articles.value = data.items || [];
  } catch (error) {
    articlesError.value = parseError(error);
  } finally {
    loadingArticles.value = false;
  }
}

async function loadDraftsList() {
  loadingDrafts.value = true;
  draftsError.value = "";
  try {
    const data = await fetchDrafts();
    drafts.value = data.items || [];
  } catch (error) {
    draftsError.value = parseError(error);
  } finally {
    loadingDrafts.value = false;
  }
}

async function switchToDrafts() {
  activeTab.value = 'drafts';
  if (!drafts.value.length) await loadDraftsList();
}

async function createArticleItem() {
  busy.value = true;
  try {
    const payload = {
      title: articleForm.title,
      excerpt: articleForm.excerpt || null,
      status: articleForm.status,
      visibility: articleForm.visibility,
      partner_can_edit: articleForm.partnerCanEdit,
      tags: parseTags(articleForm.tagsText),
      blocks: articleForm.blockContent
        ? [{ block_type: "Paragraph", content: articleForm.blockContent, sort_order: 0 }]
        : []
    };
    
    // 只有在密码保护模式下才发送密码
    if (articleForm.visibility === 'password_protected' && articleForm.password) {
      payload.password = articleForm.password;
    }
    
    await createArticle(payload);
    showMessage(articleForm.status === 'Draft' ? t('articles.draftSaved') : t('articles.articlePublished'));
    articleForm.title = "";
    articleForm.excerpt = "";
    articleForm.blockContent = "";
    articleForm.tagsText = "";
    articleForm.password = "";
    if (articleForm.status === 'Draft') {
      await loadDraftsList();
      activeTab.value = 'drafts';
    } else {
      await loadArticles();
    }
  } catch (error) {
    showMessage(parseError(error), "error");
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  loadArticles();
});
</script>

<style scoped>
.tabs-row {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.refresh-error {
  margin: 0 0 0.75rem;
  border: 1px solid #efb9c8;
  border-radius: var(--radius-control);
  background: #fff2f5;
  color: #9f3f55;
  padding: 0.65rem 0.75rem;
  font-size: 0.82rem;
}
.tab-btn {
  padding: 0.45rem 1.2rem;
  border-radius: var(--radius-control);
  border: 1px solid var(--border-subtle);
  background: var(--surface-raised);
  color: var(--text-soft);
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.tab-btn--active {
  background: var(--brand-soft);
  color: var(--brand-strong);
  border-color: #efc3d1;
}
.tab-badge {
  background: rgb(255 255 255 / 0.7);
  border-radius: 999px;
  padding: 0 0.4rem;
  font-size: 0.75rem;
}
.article-card {
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.article-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-soft);
}
.article-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-main);
  margin: 0;
}
.article-meta {
  font-size: 0.78rem;
  color: var(--text-soft);
  margin: 0.35rem 0 0;
}
.pill--gray {
  background: #f1f5f9;
  color: #64748b;
}
.pill--tag {
  background: #e0f2fe;
  color: #075985;
}
.form-field {
  margin: 0;
}
select.input {
  cursor: pointer;
}
</style>
