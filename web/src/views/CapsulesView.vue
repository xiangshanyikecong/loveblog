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
    <ModuleTabs :items="memoryTabs" label="回忆模块导航" />

    <article v-if="canManageContent" class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t('capsules.buryTitle') }}</h2>
      </div>
      <form class="form-stack" @submit.prevent="handleCreate">
        <textarea v-model="form.content" class="input min-h-24" :placeholder="t('capsules.contentPlaceholder')"></textarea>
        <MediaCapture ref="recorderRef" @update="onMediaUpdate" />
        <div class="form-row">
          <label>解锁日期：</label>
          <input v-model="form.date" type="date" class="input" required />
        </div>
        <button class="btn-primary" :disabled="busy">{{ t('capsules.buryButton') }}</button>
      </form>
    </article>

    <div class="capsule-grid">
      <div v-for="item in capsules" :key="item.uuid" class="capsule-card glass-card" :class="{'capsule-locked': !item.is_open}">
        <div class="capsule-icon">
          {{ item.is_open ? '🔓' : '🔒' }}
        </div>
        <div class="capsule-body">
          <p class="capsule-status">{{ item.is_open ? t('capsules.capsuleOpened') : t('capsules.capsuleLocked') }}</p>
          <div v-if="item.is_open" class="capsule-content">
            <p v-if="item.content" class="capsule-text">{{ item.content }}</p>
            <audio
              v-if="item.media_url && item.media_type === 'audio'"
              :src="resolveAssetUrl(item.media_url)"
              controls
              class="capsule-media"
            ></audio>
            <video
              v-else-if="item.media_url && item.media_type === 'video'"
              :src="resolveAssetUrl(item.media_url)"
              controls
              playsinline
              class="capsule-media"
            ></video>
          </div>
          <div v-else class="capsule-mask">
            <span v-if="item.has_media">{{ item.media_type === 'video' ? t('capsules.videoSealed') : t('capsules.audioSealed') }}</span>
            <span v-else>{{ t('capsules.contentSealed') }}</span>
          </div>
          <div class="capsule-footer">
            <span>解锁于：{{ new Date(item.open_at).toLocaleDateString() }}</span>
            <span>来自：{{ item.author_nickname }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, inject } from "vue";
import ModuleTabs from "../components/ModuleTabs.vue";
import MediaCapture from "../components/MediaCapture.vue";
import { fetchCapsules, createCapsule, resolveAssetUrl } from "../lib/api";
import { parseError } from "../utils/helpers";
import { useAuth } from "../stores/auth";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const showMessage = inject("showMessage");
const { canManageContent } = useAuth();
const capsules = ref([]);
const busy = ref(false);
const recorderRef = ref(null);
const memoryTabs = [
  { label: t('capsules.tabMemories'), to: "/events" },
  { label: t('capsules.tabTimeline'), to: "/timeline" },
  { label: t('capsules.tabCapsules'), to: "/capsules" }
];

const form = reactive({
  content: "",
  date: "",
  media: null
});

function onMediaUpdate(media) {
  form.media = media;
}

async function load() {
  try {
    capsules.value = await fetchCapsules();
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function handleCreate() {
  if (!form.content.trim() && !form.media) {
    showMessage(t('capsules.contentRequired'));
    return;
  }
  busy.value = true;
  try {
    const openAt = new Date(form.date);
    openAt.setHours(0, 0, 0, 0);

    await createCapsule({
      content: form.content.trim() || null,
      open_at: openAt.toISOString(),
      media_url: form.media?.media_url || null,
      media_type: form.media?.media_type || null,
      media_duration_sec: form.media?.media_duration_sec ?? null
    });
    showMessage(t('capsules.buriedSuccess'));
    form.content = "";
    form.date = "";
    form.media = null;
    recorderRef.value?.reset();
    await load();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.form-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.capsule-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
  margin-top: 2rem;
}
.capsule-card {
  padding: 1.5rem;
  display: flex;
  gap: 1rem;
  transition: transform 0.2s;
}
.capsule-card:hover {
  transform: translateY(-4px);
}
.capsule-locked {
  opacity: 0.8;
  filter: grayscale(0.5);
}
.capsule-icon {
  font-size: 2rem;
  flex-shrink: 0;
}
.capsule-body {
  flex: 1;
}
.capsule-status {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #64748b;
}
.capsule-content {
  font-size: 1rem;
  line-height: 1.6;
  color: #1e293b;
  margin-bottom: 1rem;
}
.capsule-text {
  white-space: pre-wrap;
  margin: 0 0 0.75rem;
}
.capsule-media {
  width: 100%;
  border-radius: 8px;
}
.capsule-mask {
  height: 60px;
  background: rgba(148, 163, 184, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  border-radius: 8px;
  font-style: italic;
  margin-bottom: 1rem;
}
.capsule-footer {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #94a3b8;
}
</style>
