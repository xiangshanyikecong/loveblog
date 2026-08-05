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
    <ModuleTabs :items="memoryTabs" :label="t('timelineView.tabAriaLabel')" />

    <article v-if="token" class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t('timelineView.postTitle') }}</h2>
        <button class="ghost-btn" @click="loadTimeline">{{ t('timelineView.refresh') }}</button>
      </div>

      <form class="form-stack" @submit.prevent="createMomentItem">
        <textarea v-model="momentForm.content" class="input min-h-24" :placeholder="t('timelineView.contentPlaceholder')"></textarea>
        <div class="form-row">
          <input v-model="momentForm.location" class="input" :placeholder="t('timelineView.locationPlaceholder')" />
          <input v-model="momentForm.tagsText" class="input" :placeholder="t('timelineView.tagsPlaceholder')" />
          <div class="image-upload-trigger">
            <button type="button" class="ghost-btn" @click="$refs.fileInput.click()">📷 添加图片</button>
            <input ref="fileInput" type="file" hidden multiple accept="image/*" @change="onFilesSelected" />
          </div>
        </div>
        
        <div v-if="selectedFiles.length" class="upload-previews">
          <div v-for="(file, idx) in selectedFiles" :key="idx" class="preview-item">
            <img :src="file.preview" />
            <button type="button" class="remove-preview" @click="removeSelected(idx)">×</button>
          </div>
        </div>

        <details class="voice-diary">
          <summary>🎙️ 录一段语音日记</summary>
          <MediaCapture ref="recorderRef" :allow-video="false" @update="onAudioUpdate" />
        </details>

        <button class="btn-primary" :disabled="busy">
          {{ busy ? t('timelineView.publishing') : t('timelineView.publish') }}
        </button>
      </form>
    </article>

    <article class="glass-card section-block">
      <div v-if="!token" class="section-header">
        <h2>恋爱时间轴</h2>
        <button class="ghost-btn" @click="loadTimeline">刷新</button>
      </div>
      <ul class="entity-list">
        <li v-for="item in moments" :key="item.mid" class="entity-item timeline-item">
          <div class="timeline-avatar">
            {{ item.author_nickname.charAt(0).toUpperCase() }}
          </div>
          <div class="timeline-content">
            <p class="timeline-meta">
              <span class="timeline-author">{{ item.author_nickname }}</span>
              <span class="timeline-time">{{ new Date(item.timestamp).toLocaleString() }}</span>
              <span v-if="item.location" class="timeline-location">📍 {{ item.location }}</span>
            </p>
            <p class="timeline-text">{{ item.content }}</p>
            <div v-if="item.tags && item.tags.length" class="timeline-tags">
              <span v-for="tag in item.tags" :key="tag" class="pill pill--tag">#{{ tag }}</span>
            </div>
            <div v-if="item.media_urls && item.media_urls.length" class="timeline-media">
              <img v-for="(url, idx) in item.media_urls" :key="idx" :src="resolveAssetUrl(url)" class="timeline-image" loading="lazy" />
            </div>
            <audio
              v-if="item.audio_url"
              :src="resolveAssetUrl(item.audio_url)"
              controls
              class="timeline-audio"
            ></audio>

            <div class="comment-section">
              <CommentThread
                v-if="item.comments && item.comments.length"
                :comments="item.comments"
                :can-reply="Boolean(token)"
                :submit-reply="(payload) => submitComment(item.mid, payload)"
                :submitting="busy"
              />
              <div v-if="token" class="comment-input-row">
                <input
                  v-model="commentInputs[item.mid]"
                  class="input-mini"
                  :placeholder="t('timelineView.commentPlaceholder')"
                  @keyup.enter="submitComment(item.mid)"
                />
                <button class="text-btn-mini" @click="submitComment(item.mid)">{{ t('timelineView.send') }}</button>
              </div>
            </div>
          </div>
        </li>
        <li v-if="!moments.length" class="muted">{{ t('timelineView.empty') }}</li>
      </ul>
      <div v-if="hasNext" class="load-more">
        <button class="text-btn" :disabled="busy" @click="loadMore">加载更多</button>
      </div>
    </article>
  </div>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from "vue";
import ModuleTabs from "../components/ModuleTabs.vue";
import CommentThread from "../components/CommentThread.vue";
import MediaCapture from "../components/MediaCapture.vue";
import { createMoment, fetchTimeline, postComment, resolveAssetUrl, uploadTimelineImage } from "../lib/api";
import { useAuth } from "../stores/auth";
import { parseError, parseTags } from "../utils/helpers";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const showMessage = inject("showMessage");
const { token } = useAuth();
const moments = ref([]);
const busy = ref(false);
const currentPage = ref(1);
const hasNext = ref(false);
const commentInputs = reactive({});
const selectedFiles = ref([]);
const fileInput = ref(null);
const recorderRef = ref(null);
const memoryTabs = [
  { label: t('timelineView.tabMemories'), to: "/events" },
  { label: t('timelineView.tabTimeline'), to: "/timeline" },
  { label: t('timelineView.tabCapsules'), to: "/capsules" }
];

const momentForm = reactive({
  content: "",
  location: "",
  tagsText: "",
  mediaUrls: [],
  audio: null
});

function onAudioUpdate(media) {
  momentForm.audio = media;
}

async function loadTimeline(page = 1) {
  try {
    const data = await fetchTimeline({ page, page_size: 20, sort: "desc" });
    if (page === 1) {
      moments.value = data.items || [];
    } else {
      moments.value = [...moments.value, ...(data.items || [])];
    }
    currentPage.value = data.page;
    hasNext.value = data.has_next;
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function loadMore() {
  if (busy.value || !hasNext.value) return;
  busy.value = true;
  await loadTimeline(currentPage.value + 1);
  busy.value = false;
}

function onFilesSelected(e) {
  const files = Array.from(e.target.files);
  files.forEach(file => {
    selectedFiles.value.push({
      file,
      preview: URL.createObjectURL(file)
    });
  });
}

function removeSelected(idx) {
  const item = selectedFiles.value.splice(idx, 1)[0];
  if (item.preview) URL.revokeObjectURL(item.preview);
}

async function createMomentItem() {
  if (!momentForm.content.trim() && !momentForm.audio) {
    showMessage(t('timelineView.contentRequired'));
    return;
  }
  busy.value = true;
  try {
    const mediaUrls = [];
    for (const item of selectedFiles.value) {
      const res = await uploadTimelineImage(item.file);
      mediaUrls.push(res.url);
    }

    await createMoment({
      content: momentForm.content,
      location: momentForm.location || null,
      tags: parseTags(momentForm.tagsText),
      media_urls: mediaUrls,
      audio_url: momentForm.audio?.media_url || null,
      audio_duration_sec: momentForm.audio?.media_duration_sec ?? null
    });
    showMessage(t('timelineView.publishSuccess'));
    momentForm.content = "";
    momentForm.location = "";
    momentForm.tagsText = "";
    momentForm.audio = null;
    recorderRef.value?.reset();
    selectedFiles.value.forEach(f => URL.revokeObjectURL(f.preview));
    selectedFiles.value = [];
    await loadTimeline(1);
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function submitComment(mid, payload = null) {
  const content = payload?.content ?? commentInputs[mid];
  if (!content || !content.trim()) return;

  try {
    await postComment(mid, {
      content: content.trim(),
      parent_cid: payload?.parentCid || null,
      mention_uids: payload?.mentionUids || []
    });

    if (!payload) {
      commentInputs[mid] = "";
    }

    await loadTimeline(1);
  } catch (error) {
    showMessage(parseError(error));
  }
}

onMounted(() => {
  loadTimeline();
});
</script>

<style scoped>
.timeline-item {
  display: flex;
  gap: 1rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 0.7rem;
  align-items: center;
}
.timeline-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.timeline-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #a855f7, #ec4899);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  flex-shrink: 0;
}
.timeline-content {
  flex: 1;
}
.timeline-meta {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  color: #64748b;
  display: flex;
  gap: 0.75rem;
  align-items: center;
}
.timeline-author {
  font-weight: 600;
  color: #334155;
  font-size: 0.95rem;
}
.timeline-text {
  margin: 0;
  line-height: 1.6;
  color: #1e293b;
  white-space: pre-wrap;
}
.timeline-media {
  margin-top: 0.75rem;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.timeline-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.55rem;
}
.timeline-image {
  max-width: 200px;
  max-height: 200px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid #e2e8f0;
}
.timeline-audio {
  margin-top: 0.75rem;
  width: 100%;
  max-width: 320px;
}
.voice-diary summary {
  cursor: pointer;
  font-size: 0.9rem;
  color: #64748b;
  margin-bottom: 0.5rem;
}
.image-upload-trigger {
  flex-shrink: 0;
}
.upload-previews {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}
.preview-item {
  position: relative;
  width: 80px;
  height: 80px;
}
.preview-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 8px;
}
.remove-preview {
  position: absolute;
  top: -5px;
  right: -5px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #ef4444;
  color: white;
  border: none;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.comment-section {
  margin-top: 1rem;
  background: rgba(248, 250, 252, 0.5);
  padding: 0.75rem;
  border-radius: 8px;
}
.comment-input-row {
  display: flex;
  gap: 0.5rem;
}
.input-mini {
  flex: 1;
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  outline: none;
}
.input-mini:focus {
  border-color: #94a3b8;
}
.text-btn-mini {
  background: none;
  border: none;
  color: #3b82f6;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}
.load-more {
  margin-top: 1rem;
  text-align: center;
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
