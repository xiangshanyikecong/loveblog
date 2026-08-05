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
  <div class="editor-page">
    <!-- 顶部工具栏 -->
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <button class="btn-ghost" @click="goBack">
          <span class="icon">←</span> {{ t('articleEditor.back') }}
        </button>
        <div class="editor-title-input">
          <input 
            v-model="article.title" 
            class="title-input" 
            :placeholder="t('articleEditor.titlePlaceholder')"
            @input="markAsModified"
          />
        </div>
      </div>
      
      <div class="toolbar-right">
        <span v-if="hasUnsavedChanges" class="unsaved-indicator">{{ t('articleEditor.unsaved') }}</span>
        <span v-else-if="lastSaved" class="saved-indicator">{{ t('articleEditor.saved') }}</span>
        <span v-if="saveError" class="save-error" role="alert">{{ saveError }}</span>
        
        <button class="btn-secondary" @click="showSettingsModal = true">
          <span class="icon">⚙️</span> {{ t('articleEditor.settings') }}
        </button>
        
        <button 
          v-if="article.status === 'Draft'" 
          class="btn-secondary" 
          :disabled="saving"
          @click="saveDraft"
        >
          <span class="icon">💾</span> {{ saving ? t('articleEditor.saving') : t('articleEditor.saveDraft') }}
        </button>
        
        <button 
          class="btn-primary" 
          :disabled="saving || !article.title"
          @click="publish"
        >
          <span class="icon">🚀</span> {{ article.status === 'Published' ? t('articleEditor.update') : t('articleEditor.publish') }}
        </button>
      </div>
    </div>

    <!-- 编辑器主体 -->
    <div class="editor-container">
      <RichTextEditor
        ref="editorRef"
        v-model="article.content"
        :height="editorHeight"
        :mode="editorMode"
        :upload-url="uploadUrl"
        :placeholder="t('articleEditor.contentPlaceholder')"
        @change="markAsModified"
        @upload="handleUpload"
      />
    </div>

    <!-- 设置模态框 -->
    <div v-if="showSettingsModal" class="modal-overlay" @click.self="showSettingsModal = false">
      <div class="modal-content settings-modal">
        <div class="modal-header">
          <h3>{{ t('articleEditor.settingsTitle') }}</h3>
          <button class="btn-icon" @click="showSettingsModal = false">✕</button>
        </div>
        
        <div class="modal-body">
          <div class="form-group">
            <label>{{ t('articleEditor.excerpt') }}</label>
            <textarea
              v-model="article.excerpt"
              class="input"
              rows="3"
              :placeholder="t('articleEditor.excerptPlaceholder')"
              @input="markAsModified"
            ></textarea>
          </div>

          <div class="form-group">
            <label>{{ t('articleEditor.coverImage') }}</label>
            <div class="cover-upload">
              <div v-if="article.cover_url" class="cover-preview">
                <img :src="resolveAssetUrl(article.cover_url)" :alt="t('articleEditor.coverAlt')" />
                <button class="btn-remove" @click="article.cover_url = null; markAsModified()">
                  {{ t('articleEditor.remove') }}
                </button>
              </div>
              <div v-else class="cover-placeholder">
                <input 
                  ref="coverInput" 
                  type="file"
                  accept="image/*" 
                  style="display: none"
                  @change="handleCoverUpload"
                />
                <button class="btn-secondary" @click="$refs.coverInput.click()">
                  {{ t('articleEditor.uploadCover') }}
                </button>
              </div>
            </div>
          </div>

          <div class="form-group">
            <label>{{ t('articleEditor.tags') }}</label>
            <input
              v-model="article.tagsText"
              class="input"
              :placeholder="t('articleEditor.tagsPlaceholder')"
              @input="markAsModified"
            />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>{{ t('articleEditor.visibility') }}</label>
              <select v-model="article.visibility" class="input" @change="markAsModified">
                <option value="public">{{ t('articleEditor.visibilityPublic') }}</option>
                <option value="guest_viewable">{{ t('articleEditor.visibilityGuest') }}</option>
                <option value="partners_only">{{ t('articleEditor.visibilityPartners') }}</option>
                <option value="private">{{ t('articleEditor.visibilityPrivate') }}</option>
                <option value="password_protected">{{ t('articleEditor.visibilityPassword') }}</option>
              </select>
            </div>

            <div class="form-group">
              <label>{{ t('articleEditor.status') }}</label>
              <select v-model="article.status" class="input" @change="markAsModified">
                <option value="Draft">{{ t('articleEditor.statusDraft') }}</option>
                <option value="Published">{{ t('articleEditor.statusPublished') }}</option>
              </select>
            </div>
          </div>

          <div v-if="article.visibility === 'password_protected'" class="form-group">
            <label>{{ t('articleEditor.accessPassword') }}</label>
            <input 
              v-model="article.password" 
              type="password" 
              class="input" 
              :placeholder="t('articleEditor.passwordPlaceholder')"
              @input="markAsModified"
            />
          </div>

          <div class="form-group">
            <label class="checkbox-label">
              <input
                v-model="article.partner_can_edit"
                type="checkbox"
                @change="markAsModified"
              />
              <span>{{ t('articleEditor.allowPartnerEdit') }}</span>
            </label>
          </div>

          <div class="form-group">
            <label class="checkbox-label">
              <input
                v-model="article.is_co_created"
                type="checkbox"
                :disabled="article.is_co_created"
                @change="markAsModified"
              />
              <span>
                {{ t('articleEditor.markCoCreated') }}
                <small v-if="article.is_co_created" class="muted-hint">
                  {{ t('articleEditor.coCreatedLockedHint') }}
                </small>
                <small v-else class="muted-hint">
                  {{ t('articleEditor.coCreatedEnableHint') }}
                </small>
              </span>
            </label>
          </div>

          <div class="form-group">
            <label>{{ t('articleEditor.editorMode') }}</label>
            <div class="mode-selector">
              <button
                :class="['mode-btn', editorMode === 'wysiwyg' && 'active']"
                @click="editorMode = 'wysiwyg'"
              >
                {{ t('articleEditor.modeWysiwyg') }}
              </button>
              <button
                :class="['mode-btn', editorMode === 'ir' && 'active']"
                @click="editorMode = 'ir'"
              >
                {{ t('articleEditor.modeIR') }}
              </button>
              <button
                :class="['mode-btn', editorMode === 'sv' && 'active']"
                @click="editorMode = 'sv'"
              >
                {{ t('articleEditor.modeSV') }}
              </button>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn-secondary" @click="showSettingsModal = false">
            {{ t('articleEditor.close') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from "vue-i18n";
import RichTextEditor from '../components/RichTextEditor.vue';
import { createArticle, fetchArticle, resolveApiUrl, resolveAssetUrl, updateArticle, uploadFile } from '../lib/api';
import { confirmDialog, alertDialog, choiceDialog } from '../lib/dialog';
import { editorRouteKey, isCurrentEditorSave } from '../utils/editorSave';
import { parseTags } from '../utils/helpers';

const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const editorRef = ref(null);
const coverInput = ref(null);
const showSettingsModal = ref(false);
const saving = ref(false);
const hasUnsavedChanges = ref(false);
const lastSaved = ref(null);
const saveError = ref('');
const editorMode = ref('wysiwyg'); // wysiwyg, ir, sv

// Tracks the article version that the current editor buffer was last known
// to match. Used as the `If-Match` value on save so the server can reject
// concurrent partner edits with a 409 instead of silently overwriting them.
const baseVersion = ref(null);

function emptyArticle() {
  return {
    aid: null,
    title: '',
    content: '',
    excerpt: '',
    cover_url: null,
    tagsText: '',
    status: 'Draft',
    visibility: 'public',
    password: '',
    partner_can_edit: false,
    is_co_created: false
  };
}

const article = ref(emptyArticle());
let editRevision = 0;
let loadGeneration = 0;
let saveGeneration = 0;

const uploadUrl = computed(() => {
  return resolveApiUrl("/v1/uploads/articles");
});

const editorHeight = computed(() => {
  return `${window.innerHeight - 80}px`;
});

// 加载文章
async function loadArticle() {
  const aid = route.params.aid;
  const generation = ++loadGeneration;
  saveGeneration += 1;
  saving.value = false;
  saveError.value = '';
  if (!aid || aid === 'new') {
    article.value = emptyArticle();
    baseVersion.value = null;
    editRevision = 0;
    hasUnsavedChanges.value = false;
    lastSaved.value = null;
    return;
  }

  try {
    const data = await fetchArticle(aid);
    if (generation !== loadGeneration) return;
    article.value = {
      aid: data.aid,
      title: data.title || '',
      content: convertBlocksToMarkdown(data.blocks || []),
      excerpt: data.excerpt || '',
      cover_url: data.cover_url || null,
      tagsText: (data.tags || []).join(', '),
      status: data.status || 'Draft',
      visibility: data.visibility || 'public',
      password: '',
      partner_can_edit: data.partner_can_edit || false,
      is_co_created: Boolean(data.is_co_created)
    };
    // Store the version the buffer was loaded from so subsequent saves can
    // opt into optimistic concurrency via `If-Match`.
    baseVersion.value = data.__etag ?? data.version ?? null;
    editRevision = 0;
    hasUnsavedChanges.value = false;
  } catch (_error) {
    if (generation !== loadGeneration) return;
    await alertDialog(t('articleEditor.loadFailed'));
    goBack();
  }
}

// 将 blocks 转换为 Markdown
function convertBlocksToMarkdown(blocks) {
  if (!blocks || blocks.length === 0) return '';
  
  return blocks.map(block => {
    switch (block.block_type) {
      case 'Heading':
        return `## ${block.content}\n`;
      case 'Quote':
        return `> ${block.content}\n`;
      case 'Image':
        return `![${t('articleEditor.imageAlt')}](${resolveAssetUrl(block.content)})\n`;
      case 'Paragraph':
      default:
        return `${block.content}\n`;
    }
  }).join('\n');
}

// 将 Markdown 转换为 blocks（用于保存）
function convertMarkdownToBlocks(markdown) {
  if (!markdown) return [];
  
  const lines = markdown.split('\n');
  const blocks = [];
  let currentParagraph = [];
  let sortOrder = 0;

  for (const line of lines) {
    const trimmed = line.trim();
    
    // 标题
    if (trimmed.startsWith('## ')) {
      if (currentParagraph.length > 0) {
        blocks.push({
          block_type: 'Paragraph',
          content: currentParagraph.join('\n'),
          sort_order: sortOrder++
        });
        currentParagraph = [];
      }
      blocks.push({
        block_type: 'Heading',
        content: trimmed.substring(3),
        sort_order: sortOrder++
      });
    }
    // 引用
    else if (trimmed.startsWith('> ')) {
      if (currentParagraph.length > 0) {
        blocks.push({
          block_type: 'Paragraph',
          content: currentParagraph.join('\n'),
          sort_order: sortOrder++
        });
        currentParagraph = [];
      }
      blocks.push({
        block_type: 'Quote',
        content: trimmed.substring(2),
        sort_order: sortOrder++
      });
    }
    // 图片
    else if (trimmed.match(/^!\[.*\]\(.*\)$/)) {
      if (currentParagraph.length > 0) {
        blocks.push({
          block_type: 'Paragraph',
          content: currentParagraph.join('\n'),
          sort_order: sortOrder++
        });
        currentParagraph = [];
      }
      const match = trimmed.match(/!\[.*\]\((.*)\)/);
      if (match) {
        blocks.push({
          block_type: 'Image',
          content: match[1],
          sort_order: sortOrder++
        });
      }
    }
    // 空行
    else if (trimmed === '') {
      if (currentParagraph.length > 0) {
        blocks.push({
          block_type: 'Paragraph',
          content: currentParagraph.join('\n'),
          sort_order: sortOrder++
        });
        currentParagraph = [];
      }
    }
    // 普通段落
    else {
      currentParagraph.push(line);
    }
  }

  // 处理最后的段落
  if (currentParagraph.length > 0) {
    blocks.push({
      block_type: 'Paragraph',
      content: currentParagraph.join('\n'),
      sort_order: sortOrder++
    });
  }

  return blocks;
}

// 保存草稿
async function saveDraft() {
  await saveArticle({ status: article.value.status, notify: true });
}

// 发布
async function publish() {
  await saveArticle({ status: 'Published', notify: true });
}

// 保存文章
async function saveArticle({ status = article.value.status, notify = false } = {}) {
  if (saving.value) return false;
  if (!article.value.title.trim()) {
    if (notify) await alertDialog(t('articleEditor.titleRequired'));
    return false;
  }

  saving.value = true;
  saveError.value = '';
  const requestSaveGeneration = ++saveGeneration;
  const requestLoadGeneration = loadGeneration;
  const saveIdentity = {
    saveGeneration: requestSaveGeneration,
    loadGeneration: requestLoadGeneration,
    routeKey: editorRouteKey(route.params.aid)
  };
  const savedRevision = editRevision;
  const statusAtRequest = article.value.status;
  const passwordAtRequest = article.value.password;
  try {
    const content = editorRef.value?.getValue() || article.value.content;
    const blocks = convertMarkdownToBlocks(content);

    const payload = {
      title: article.value.title,
      excerpt: article.value.excerpt || null,
      cover_url: article.value.cover_url || null,
      tags: parseTags(article.value.tagsText),
      status,
      visibility: article.value.visibility,
      // Once a partner has touched the article the server pins
      // `is_co_created` to true; we still echo the latest value back so the
      // user can flip it on themselves for solo drafts.
      is_co_created: Boolean(article.value.is_co_created),
      partner_can_edit: article.value.partner_can_edit,
      blocks: blocks
    };

    // 密码保护
    if (article.value.visibility === 'password_protected' && article.value.password) {
      payload.password = article.value.password;
    }

    let result;
    if (article.value.aid) {
      // 更新现有文章
      result = await updateArticle(article.value.aid, payload, {
        ifMatch: baseVersion.value
      });
    } else {
      // 创建新文章
      result = await createArticle(payload);
      if (!saveStillCurrent(saveIdentity)) return false;
      article.value.aid = result.aid;
      saveIdentity.routeKey = editorRouteKey(result.aid);
      // 更新 URL
      await router.replace({ name: 'article-editor', params: { aid: result.aid } });
    }

    if (!saveStillCurrent(saveIdentity)) return false;

    // Sync the version we now know matches the server so the next save can
    // continue to opt into optimistic concurrency.
    baseVersion.value = result.__etag ?? result.version ?? baseVersion.value;

    // Publishing while the user keeps typing must still advance the local
    // status. Otherwise the next autosave would send the stale Draft value and
    // silently unpublish the article that just succeeded on the server.
    if (article.value.status === statusAtRequest) {
      article.value.status = status;
    }
    if (article.value.password === passwordAtRequest) {
      article.value.password = '';
    }
    if (editRevision === savedRevision) {
      hasUnsavedChanges.value = false;
    }
    lastSaved.value = new Date().toLocaleTimeString();

    if (notify) await alertDialog(status === 'Published' ? t('articleEditor.publishSuccess') : t('articleEditor.saveSuccess'));
    return true;
  } catch (error) {
    if (!saveStillCurrent(saveIdentity)) return false;
    // 409: 另一方刚刚保存过同一篇文章。让用户在「强制覆盖」「放弃并重载」「取消」之间选择
    if (error?.name === 'ArticleVersionConflictError') {
      const choice = await handleVersionConflict(error);
      if (choice === 'overwrite') {
        // 用户选择覆盖：把 baseVersion 设为服务端最新版本号，再次保存（不携带 If-Match，
        // 跳过乐观锁。新的 baseVersion 在成功后会被刷新。）
        if (error.currentVersion) {
          baseVersion.value = error.currentVersion;
        }
        if (saving.value === false) {
          // `finally` 块会在递归调用之前把 saving 还原，所以这里无需重复设置
        }
        return await saveArticle({ status, notify });
      }
      if (choice === 'reload') {
        saveError.value = t('articleEditor.reloadAborted');
        await loadArticle();
        return false;
      }
      // cancel
      saveError.value = error.message || t('articleEditor.conflictCancelled');
      return false;
    }

    saveError.value = t('articleEditor.saveFailed');
    if (notify) {
      await alertDialog(t('articleEditor.saveFailedWithReason', { reason: error.response?.data?.detail || error.message }));
    }
    return false;
  } finally {
    if (requestSaveGeneration === saveGeneration) {
      saving.value = false;
    }
  }
}

// 冲突解决对话框：用户选择覆盖 / 重新载入 / 取消
async function handleVersionConflict(error) {
  const expectedVersion = error.expectedVersion ?? '?';
  const currentVersion = error.currentVersion ?? '?';
  const message = t('articleEditor.conflictMessage', { expected: expectedVersion, current: currentVersion });
  const choice = await choiceDialog(message, [
    { label: t('articleEditor.overwrite'), value: 'overwrite', danger: true },
    { label: t('articleEditor.reload'), value: 'reload' }
  ]);
  return choice; // 'overwrite' | 'reload' | null (cancelled)
}

function saveStillCurrent(saveIdentity) {
  return isCurrentEditorSave(saveIdentity, {
    saveGeneration,
    loadGeneration,
    routeKey: editorRouteKey(route.params.aid)
  });
}

// 上传封面
async function handleCoverUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  try {
    const result = await uploadFile(file, 'articles');
    article.value.cover_url = result.url;
    markAsModified();
    await alertDialog(t('articleEditor.coverUploadSuccess'));
  } catch (_error) {
    await alertDialog(t('articleEditor.uploadFailed'));
  }
}

// 处理编辑器上传
function handleUpload(result) {
  if (!result.success) {
    alertDialog(t('articleEditor.imageUploadFailed'));
  }
}

// 标记为已修改
function markAsModified() {
  editRevision += 1;
  hasUnsavedChanges.value = true;
  saveError.value = '';
}

// 返回
async function goBack() {
  if (hasUnsavedChanges.value) {
    if (!(await confirmDialog(t('articleEditor.leaveWithUnsaved')))) {
      return;
    }
  }
  router.back();
}

// 自动保存（每 30 秒）
let autoSaveTimer = null;
function startAutoSave() {
  autoSaveTimer = setInterval(() => {
    if (!saving.value && hasUnsavedChanges.value && article.value.title) {
      saveArticle({ status: article.value.status, notify: false });
    }
  }, 30000);
}

// 页面离开提示
function handleBeforeUnload(e) {
  if (hasUnsavedChanges.value) {
    e.preventDefault();
    e.returnValue = '';
  }
}

// 快捷键
function handleKeyDown(e) {
  // Ctrl+S / Cmd+S 保存
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault();
    saveArticle({ status: article.value.status, notify: false });
  }
}

onMounted(() => {
  loadArticle();
  startAutoSave();
  window.addEventListener('beforeunload', handleBeforeUnload);
  window.addEventListener('keydown', handleKeyDown);
});

onBeforeUnmount(() => {
  loadGeneration += 1;
  saveGeneration += 1;
  if (autoSaveTimer) {
    clearInterval(autoSaveTimer);
  }
  window.removeEventListener('beforeunload', handleBeforeUnload);
  window.removeEventListener('keydown', handleKeyDown);
});

// 监听路由变化
watch(() => route.params.aid, () => {
  if (route.name === 'article-editor') {
    if (String(route.params.aid || '') === String(article.value.aid || '')) return;
    loadArticle();
  }
});
</script>

<style scoped>
.editor-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background: white;
  border-bottom: 1px solid #e2e8f0;
  gap: 1rem;
  flex-wrap: wrap;
  position: relative;
  z-index: 10; /* 设置较低的 z-index，让工具提示能显示在上面 */
}

/* 确保工具栏不会阻止工具提示的鼠标事件 */
.editor-toolbar::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: -1;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.editor-title-input {
  flex: 1;
  min-width: 200px;
  max-width: 600px;
}

.title-input {
  width: 100%;
  border: none;
  font-size: 1.25rem;
  font-weight: 600;
  padding: 0.5rem;
  color: #1e293b;
  background: transparent;
  outline: none;
}

.title-input:focus {
  background: #f8fafc;
  border-radius: 6px;
}

.title-input::placeholder {
  color: #94a3b8;
}

.btn-ghost,
.btn-secondary,
.btn-primary {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.btn-ghost {
  background: transparent;
  color: #64748b;
}

.btn-ghost:hover {
  background: #f1f5f9;
}

.btn-secondary {
  background: #f1f5f9;
  color: #475569;
}

.btn-secondary:hover {
  background: #e2e8f0;
}

.btn-primary {
  background: linear-gradient(135deg, #8f9bff, #ff8ab5);
  color: white;
}

.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(143, 155, 255, 0.3);
}

.btn-ghost:disabled,
.btn-secondary:disabled,
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.icon {
  font-size: 1.1em;
}

.unsaved-indicator {
  color: #f59e0b;
  font-size: 0.85rem;
  font-weight: 600;
}

.saved-indicator {
  color: #10b981;
  font-size: 0.85rem;
  font-weight: 600;
}

.save-error {
  color: #b91c1c;
  font-size: 0.82rem;
  font-weight: 600;
}

.editor-container {
  flex: 1;
  overflow: auto; /* 改为 auto，允许滚动但不裁剪定位元素 */
  padding: 1rem;
  position: relative;
  z-index: 100; /* 让编辑器整体高于页面顶部工具栏，向上弹出的 tooltip 才不会被盖住 */
}

/* 确保编辑器内容可以正常滚动 */
.editor-container :deep(.vditor) {
  height: 100%;
  position: relative;
  z-index: 1000; /* 提升 vditor 的层级 */
}

/* 确保 Vditor 工具栏有正确的层级 */
.editor-container :deep(.vditor-toolbar) {
  position: relative;
  z-index: 1001; /* 工具栏在编辑器内容之上 */
}

/* 确保工具栏按钮有正确的定位上下文 */
.editor-container :deep(.vditor-toolbar__item) {
  position: relative;
  z-index: 1002; /* 按钮在工具栏之上 */
}

/* 模态框样式 */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(4px);
  padding: 1rem;
}

.modal-content {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
  color: #1e293b;
}

.btn-icon {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #94a3b8;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: #f1f5f9;
  color: #475569;
}

.modal-body {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  font-size: 0.9rem;
  font-weight: 600;
  color: #475569;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.input {
  padding: 0.75rem;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 0.95rem;
  color: #1e293b;
  transition: all 0.2s;
}

.input:focus {
  outline: none;
  border-color: #8f9bff;
  box-shadow: 0 0 0 3px rgba(143, 155, 255, 0.1);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-weight: normal;
}

.checkbox-label input[type="checkbox"] {
  cursor: pointer;
  width: 18px;
  height: 18px;
}

.checkbox-label input[type="checkbox"]:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.muted-hint {
  display: block;
  margin-top: 0.2rem;
  margin-left: 1.7rem;
  font-size: 0.78rem;
  color: #94a3b8;
  font-weight: normal;
}

.cover-upload {
  border: 2px dashed #cbd5e1;
  border-radius: 8px;
  overflow: hidden;
}

.cover-preview {
  position: relative;
}

.cover-preview img {
  width: 100%;
  height: 200px;
  object-fit: cover;
  display: block;
}

.btn-remove {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  border: none;
  padding: 0.4rem 0.8rem;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-remove:hover {
  background: rgba(0, 0, 0, 0.9);
}

.cover-placeholder {
  padding: 2rem;
  display: flex;
  justify-content: center;
  align-items: center;
}

.mode-selector {
  display: flex;
  gap: 0.5rem;
  background: #f1f5f9;
  padding: 0.25rem;
  border-radius: 8px;
}

.mode-btn {
  flex: 1;
  padding: 0.5rem 1rem;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 0.85rem;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn.active {
  background: white;
  color: #1e293b;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.mode-btn:hover:not(.active) {
  color: #475569;
}

@media (max-width: 768px) {
  .editor-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-left,
  .toolbar-right {
    width: 100%;
    justify-content: space-between;
  }

  .editor-title-input {
    max-width: none;
  }

  .form-row {
    grid-template-columns: 1fr;
  }

  /* Reclaim horizontal room on phones and let the third-party Vditor toolbar
     wrap so every tool stays reachable instead of being clipped off-screen. */
  .editor-container {
    padding: 0.6rem;
  }

  .editor-container :deep(.vditor-toolbar) {
    flex-wrap: wrap;
  }
}
</style>
