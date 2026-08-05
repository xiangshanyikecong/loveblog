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
    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>{{ t('articleDetail.loading') }}</p>
    </div>

    <section v-else-if="requiresPassword" class="glass-card access-card">
      <h2>{{ t('articleDetail.requiresPasswordTitle') }}</h2>
      <form class="access-form" @submit.prevent="submitPassword">
        <label for="article-access-password">{{ t('articleDetail.accessPassword') }}</label>
        <input
          id="article-access-password"
          v-model="passwordInput"
          class="input"
          type="password"
          autocomplete="current-password"
          required
        />
        <p v-if="accessError" class="access-error" role="alert">{{ accessError }}</p>
        <button class="btn-primary" :disabled="loading || !passwordInput">
          {{ loading ? t('articleDetail.verifying') : t('articleDetail.openArticle') }}
        </button>
      </form>
    </section>

    <template v-else-if="article">
      <!-- Back & Actions -->
      <div class="article-toolbar">
        <button class="ghost-btn" @click="$router.back()">{{ t('articleDetail.back') }}</button>
        <div class="toolbar-right">
          <span v-if="article.status !== 'Published'" class="status-badge status-badge--draft">{{ t('articleDetail.draftBadge') }}</span>
          <span v-if="article.is_encrypted" class="pill pill--gold">{{ t('articleDetail.encrypted') }}</span>
          <span v-if="article.partner_can_edit" class="pill pill--mint">{{ t('articleDetail.coEdit') }}</span>
          <span v-if="article.is_co_created" class="pill pill--co-create" :title="t('articleDetail.coCreationTitle')">{{ t('articleDetail.coCreation') }}</span>
          <span v-for="tag in article.tags || []" :key="tag" class="pill pill--tag">#{{ tag }}</span>
          <button v-if="canManageContent" class="ghost-btn" @click="goToEdit">{{ t('articleDetail.editInAdmin') }}</button>
        </div>
      </div>

      <!-- Article Header -->
      <article class="glass-card article-reader">
        <header class="article-header">
          <h1 class="article-title">{{ article.title }}</h1>
          <div class="article-meta">
            <span>{{ article.author_nickname }}</span>
            <span>·</span>
            <span>{{ formatDate(article.published_at || article.created_at) }}</span>
          </div>
          <p v-if="article.excerpt" class="article-excerpt">{{ article.excerpt }}</p>

          <!-- 共同创作者头像行：当有不止一个作者时显示，强调「这是两个人的故事」 -->
          <div
            v-if="article.is_co_created && coCreatorList.length > 1"
            class="co-creators"
            :aria-label="t('articleDetail.coCreatorsAria')"
          >
            <span class="co-creators-label">{{ t('articleDetail.coCreatorsLabel') }}</span>
            <ul class="co-creator-avatars">
              <li
                v-for="creator in coCreatorList"
                :key="creator.uid"
                class="co-creator-avatar"
                :title="creator.nickname + (creator.uid === article.author_uid ? t('articleDetail.originalAuthor') : '')"
              >
                <span
                  class="co-creator-initial"
                  :style="{ background: avatarColor(creator.uid) }"
                >{{ avatarInitial(creator.nickname) }}</span>
                <span class="co-creator-name">{{ creator.nickname }}</span>
              </li>
            </ul>
          </div>
        </header>

        <div class="article-divider"></div>

        <!-- Blocks -->
        <div class="article-body">
          <!-- 如果有 Markdown 内容，使用 Markdown 渲染 -->
          <!-- eslint-disable-next-line vue/no-v-html -- renderedMarkdown is DOMPurify-sanitized. -->
          <div v-if="hasMarkdownContent" class="markdown-content" v-html="renderedMarkdown"></div>
          
          <!-- 否则使用传统的 blocks 渲染 -->
          <div v-else>
            <div
              v-for="block in article.blocks"
              :key="block.bid"
              class="article-block"
              :class="`block-${block.block_type.toLowerCase()}`"
            >
              <!-- Paragraph -->
              <p v-if="block.block_type === 'Paragraph'" class="block-paragraph">{{ block.content }}</p>
              <!-- Heading -->
              <h2 v-else-if="block.block_type === 'Heading'" class="block-heading">{{ block.content }}</h2>
              <!-- Quote -->
              <blockquote v-else-if="block.block_type === 'Quote'" class="block-quote">{{ block.content }}</blockquote>
              <!-- Image -->
              <figure v-else-if="block.block_type === 'Image'" class="block-image">
                <img :src="resolveAssetUrl(block.content)" :alt="t('articleDetail.imageAlt')" loading="lazy" />
              </figure>
              <!-- Co-author badge -->
              <p v-if="block.author_nickname !== article.author_nickname" class="block-coauthor">
                - {{ block.author_nickname }} {{ t('articleDetail.coAuthorSuffix') }}
              </p>
            </div>
          </div>

          <div v-if="!article.blocks || !article.blocks.length" class="empty-body">
            <p>{{ t('articleDetail.emptyBody') }}</p>
          </div>
        </div>

        <!-- 评论区 -->
        <div class="article-divider"></div>
        <div class="comment-section">
          <h3 class="comment-section-title">{{ t('articleDetail.commentTitle', { count: article.comments?.length || 0 }) }}</h3>
          
          <CommentThread
            v-if="article.comments && article.comments.length"
            :comments="article.comments"
            :can-reply="Boolean(token)"
            :submit-reply="submitComment"
            :submitting="busy"
          />
          
          <div v-if="token" class="comment-input-row">
            <input
              v-model="commentInput"
              class="input-mini"
              :placeholder="t('articleDetail.commentPlaceholder')"
              @keyup.enter="submitComment()"
            />
            <button class="text-btn-mini" :disabled="busy" @click="submitComment()">{{ t('articleDetail.send') }}</button>
          </div>
          
          <div v-else class="comment-login-prompt">
            <p>{{ t('articleDetail.loginToComment') }}</p>
          </div>
        </div>
      </article>
    </template>

    <div v-else class="error-state glass-card">
      <p>{{ loadError || t('articleDetail.notFound') }}</p>
      <button class="ghost-btn" @click="$router.push('/articles')">{{ t('articleDetail.backToList') }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, inject, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { t } from "../locales";
import { fetchArticle, postArticleComment, resolveAssetUrl, rewriteAssetUrlsInHtml } from "../lib/api";
import { useAuth } from "../stores/auth";
import { parseError } from "../utils/helpers";
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import CommentThread from "../components/CommentThread.vue";

const route = useRoute();
const router = useRouter();
const showMessage = inject("showMessage");
const { canManageContent, token } = useAuth();

const article = ref(null);
const loading = ref(true);
const commentInput = ref("");
const busy = ref(false);
const requiresPassword = ref(false);
const passwordInput = ref("");
const accessError = ref("");
const loadError = ref("");
let loadGeneration = 0;

// 检测是否有 Markdown 内容
const hasMarkdownContent = computed(() => {
  if (!article.value || !article.value.blocks || article.value.blocks.length === 0) {
    return false;
  }

  // 如果第一个 block 包含 Markdown 语法，认为是 Markdown 内容
  const firstBlock = article.value.blocks[0];
  if (!firstBlock || !firstBlock.content) return false;

  const content = firstBlock.content;
  // 检测常见的 Markdown 语法
  return content.includes('##') ||
         content.includes('**') ||
         content.includes('```') ||
         content.includes('[') && content.includes('](') ||
         content.includes('- ') ||
         content.includes('> ');
});

// 共同创作者列表：去重合并「文章作者」与「所有 block 的 author_uid」，
// 保留 server 端 collaborator_uids 的去重权威性，并用 blocks 中的昵称补充显示名。
const coCreatorList = computed(() => {
  if (!article.value) return [];
  const a = article.value;
  const nameByUid = new Map();
  // 先用 article.author 的昵称作基底
  if (a.author_uid) {
    nameByUid.set(a.author_uid, a.author_nickname || a.author_uid);
  }
  // 再用每个 block 的 author 覆盖/补充
  (a.blocks || []).forEach((b) => {
    if (b.author_uid && !nameByUid.has(b.author_uid)) {
      nameByUid.set(b.author_uid, b.author_nickname || b.author_uid);
    }
  });
  // 关键：用 server 返回的 collaborator_uids（权威去重）作为最终顺序
  const orderedUids = (a.collaborator_uids && a.collaborator_uids.length)
    ? a.collaborator_uids
    : Array.from(nameByUid.keys());
  return orderedUids
    .map((uid) => ({ uid, nickname: nameByUid.get(uid) || uid }))
    .filter((c) => nameByUid.has(c.uid));
});

function avatarInitial(nickname) {
  if (!nickname) return "?";
  // 中文取首字，英文取首字母并大写
  const first = String(nickname).trim().charAt(0);
  return first ? first.toUpperCase() : "?";
}

function avatarColor(seed) {
  // 把 uid 哈希成稳定的暖色系色相，避免每次重渲都换色
  let h = 0;
  for (let i = 0; i < (seed || "").length; i++) {
    h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  }
  const hue = h % 360;
  return `linear-gradient(135deg, hsl(${hue}, 70%, 70%), hsl(${(hue + 40) % 360}, 70%, 60%))`;
}

// 渲染 Markdown
const renderedMarkdown = computed(() => {
  if (!hasMarkdownContent.value || !article.value) return '';

  // 合并所有 blocks 的内容
  const markdown = article.value.blocks
    .map(block => block.content)
    .join('\n\n');

  try {
    // 先用 marked 渲染 Markdown
    const rawHtml = marked(markdown, {
      breaks: true,
      gfm: true
    });

    // 使用 DOMPurify 清理 HTML，防止 XSS 攻击
    const sanitizedHtml = DOMPurify.sanitize(rawHtml, {
      ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 's', 'a', 'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'div', 'span'],
      ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'id', 'target', 'rel'],
      ALLOW_DATA_ATTR: false
    });

    // 重写资源 URL
    return rewriteAssetUrlsInHtml(sanitizedHtml);
  } catch (_error) {
    return DOMPurify.sanitize(markdown, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
  }
});

function isPasswordChallenge(error) {
  const detail = error?.response?.data?.detail;
  return (
    error?.response?.status === 401 && detail === "Password required for this content"
  ) || (
    error?.response?.status === 403 && detail === "Incorrect password"
  );
}

async function load({ password = "" } = {}) {
  const generation = ++loadGeneration;
  loading.value = true;
  loadError.value = "";
  try {
    const data = await fetchArticle(route.params.aid, { password });
    if (generation !== loadGeneration) return;
    article.value = data;
    requiresPassword.value = false;
    accessError.value = "";
    passwordInput.value = "";
  } catch (error) {
    if (generation !== loadGeneration) return;
    article.value = null;
    if (isPasswordChallenge(error)) {
      requiresPassword.value = true;
      accessError.value = error.response.status === 403 ? t("articleDetail.passwordIncorrect") : "";
    } else {
      requiresPassword.value = false;
      loadError.value = parseError(error);
    }
  } finally {
    if (generation === loadGeneration) loading.value = false;
  }
}

function submitPassword() {
  if (!passwordInput.value || loading.value) return;
  load({ password: passwordInput.value });
}

function resetForRoute() {
  loadGeneration += 1;
  article.value = null;
  requiresPassword.value = false;
  passwordInput.value = "";
  accessError.value = "";
  loadError.value = "";
  load();
}

function formatDate(raw) {
  if (!raw) return "";
  return new Date(raw).toLocaleDateString("zh-CN", {
    year: "numeric", month: "long", day: "numeric"
  });
}

function goToEdit() {
  router.push({ name: "admin-articles" });
}

async function submitComment(payload = null) {
  const content = payload?.content ?? commentInput.value;
  if (!content || !content.trim()) return;

  busy.value = true;
  try {
    await postArticleComment(route.params.aid, {
      content: content.trim(),
      parent_cid: payload?.parentCid || null,
      mention_uids: payload?.mentionUids || []
    });

    if (!payload) {
      commentInput.value = "";
    }

    // 重新加载文章以获取最新评论
    await load();
    showMessage(t('articleDetail.commentSuccess'));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

onMounted(load);
watch(() => route.params.aid, resetForRoute);
</script>

<style scoped>
.article-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.status-badge {
  display: inline-block;
  padding: 0.2rem 0.7rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
}
.status-badge--draft {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fcd34d;
}

.article-reader {
  padding: 2.5rem;
  max-width: 800px;
  margin: 0 auto;
}

.article-header {
  margin-bottom: 0;
}

.article-title {
  font-size: clamp(1.6rem, 3.5vw, 2.2rem);
  font-weight: 800;
  color: #0f172a;
  line-height: 1.3;
  margin: 0 0 0.75rem;
}

.article-meta {
  display: flex;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: #64748b;
  margin-bottom: 1rem;
}

.article-excerpt {
  font-size: 1.05rem;
  color: #475569;
  font-style: italic;
  line-height: 1.7;
  border-left: 3px solid rgba(143,155,255,0.5);
  padding-left: 1rem;
  margin: 0.6rem 0 0;
}

.co-creators {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.85rem;
  padding: 0.5rem 0.7rem;
  background: linear-gradient(135deg, rgba(252, 231, 243, 0.55), rgba(219, 234, 254, 0.55));
  border-radius: 12px;
  border: 1px dashed rgba(244, 114, 182, 0.35);
}

.co-creators-label {
  font-size: 0.85rem;
  color: #9d174d;
  font-weight: 600;
  flex-shrink: 0;
}

.co-creator-avatars {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.co-creator-avatar {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.15rem 0.5rem 0.15rem 0.15rem;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 999px;
  border: 1px solid rgba(244, 114, 182, 0.25);
}

.co-creator-initial {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.6rem;
  height: 1.6rem;
  border-radius: 999px;
  color: #fff;
  font-weight: 600;
  font-size: 0.85rem;
  flex-shrink: 0;
}

.co-creator-name {
  font-size: 0.85rem;
  color: #475569;
  font-weight: 500;
}

.article-divider {
  border: none;
  border-top: 1px solid rgba(148, 163, 184, 0.25);
  margin: 2rem 0;
}

.article-body {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}

.block-paragraph {
  font-size: 1.05rem;
  line-height: 1.9;
  color: #1e293b;
  white-space: pre-wrap;
  margin: 0;
}

.block-heading {
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
  margin: 1rem 0 0;
}

.block-quote {
  border-left: 4px solid #8f9bff;
  background: rgba(143, 155, 255, 0.08);
  padding: 0.8rem 1.2rem;
  border-radius: 0 8px 8px 0;
  color: #3730a3;
  font-style: italic;
  margin: 0;
  font-size: 1rem;
  line-height: 1.7;
}

.block-image img {
  max-width: 100%;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}
.block-image {
  margin: 0;
}

.block-coauthor {
  font-size: 0.8rem;
  color: #94a3b8;
  text-align: right;
  margin: 0;
  font-style: italic;
}

.empty-body {
  text-align: center;
  padding: 2rem;
  color: #94a3b8;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 4rem 0;
  color: #64748b;
}

.loading-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid rgba(143,155,255,0.2);
  border-top-color: #8f9bff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state {
  text-align: center;
  padding: 3rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  color: #64748b;
}

.access-card {
  max-width: 440px;
  margin: 2rem auto;
  padding: 1.5rem;
}
.access-card h2 {
  margin: 0 0 1rem;
  font-size: 1.1rem;
  color: #0f172a;
}
.access-form {
  display: grid;
  gap: 0.75rem;
}
.access-form label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #475569;
}
.access-error {
  margin: 0;
  color: #b91c1c;
  font-size: 0.84rem;
}

/* Markdown 内容样式 */
.markdown-content {
  font-size: 1.05rem;
  line-height: 1.9;
  color: #1e293b;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  font-weight: 700;
  color: #0f172a;
  margin-top: 2em;
  margin-bottom: 0.75em;
  line-height: 1.3;
}

.markdown-content :deep(h1) {
  font-size: 2em;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 0.3em;
}

.markdown-content :deep(h2) {
  font-size: 1.5em;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 0.3em;
}

.markdown-content :deep(h3) {
  font-size: 1.25em;
}

.markdown-content :deep(p) {
  margin: 1em 0;
}

.markdown-content :deep(a) {
  color: #8f9bff;
  text-decoration: none;
  border-bottom: 1px solid rgba(143, 155, 255, 0.3);
  transition: all 0.2s;
}

.markdown-content :deep(a:hover) {
  color: #6366f1;
  border-bottom-color: #6366f1;
}

.markdown-content :deep(strong) {
  font-weight: 700;
  color: #0f172a;
}

.markdown-content :deep(em) {
  font-style: italic;
}

.markdown-content :deep(code) {
  background: rgba(143, 155, 255, 0.1);
  color: #6366f1;
  padding: 0.2em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}

.markdown-content :deep(pre) {
  background: #1e293b;
  border-radius: 8px;
  padding: 1.25rem;
  overflow-x: auto;
  margin: 1.5em 0;
}

.markdown-content :deep(pre code) {
  background: transparent;
  color: #e2e8f0;
  padding: 0;
  font-size: 0.9em;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid #8f9bff;
  background: rgba(143, 155, 255, 0.08);
  padding: 0.8rem 1.2rem;
  border-radius: 0 8px 8px 0;
  color: #3730a3;
  font-style: italic;
  margin: 1.5em 0;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 1em 0;
  padding-left: 2em;
}

.markdown-content :deep(li) {
  margin: 0.5em 0;
}

.markdown-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  margin: 1.5em 0;
}

.markdown-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 1.5em 0;
  font-size: 0.95em;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 0.75em 1em;
  text-align: left;
}

.markdown-content :deep(th) {
  background: rgba(143, 155, 255, 0.1);
  font-weight: 600;
  color: #0f172a;
}

.markdown-content :deep(tr:hover) {
  background: #f8fafc;
}

.markdown-content :deep(hr) {
  border: none;
  border-top: 2px solid #e2e8f0;
  margin: 2em 0;
}

/* 评论区样式 */
.comment-section {
  margin-top: 2rem;
}

.comment-section-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 1.5rem;
}

.comment-input-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-top: 1rem;
}

.input-mini {
  flex: 1;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.92);
  padding: 0.55rem 0.7rem;
  font-size: 0.84rem;
  outline: none;
}

.input-mini:focus {
  border-color: rgba(99, 102, 241, 0.55);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.12);
}

.text-btn-mini {
  border: 0;
  background: transparent;
  color: #6366f1;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  padding: 0.5rem 1rem;
}

.text-btn-mini:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.comment-login-prompt {
  text-align: center;
  padding: 2rem;
  color: #94a3b8;
  font-size: 0.9rem;
}
</style>
