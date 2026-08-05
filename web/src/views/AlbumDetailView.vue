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
      <p>{{ t('albumDetail.loading') }}</p>
    </div>

    <section v-else-if="requiresPassword" class="glass-card access-card">
      <h2>{{ t('albumDetail.requiresPasswordTitle') }}</h2>
      <form class="access-form" @submit.prevent="submitPassword">
        <label for="album-access-password">{{ t('albumDetail.accessPassword') }}</label>
        <input
          id="album-access-password"
          v-model="passwordInput"
          class="input"
          type="password"
          autocomplete="current-password"
          required
        />
        <p v-if="accessError" class="access-error" role="alert">{{ accessError }}</p>
        <button class="btn-primary" :disabled="loading || !passwordInput">
          {{ loading ? t('albumDetail.verifying') : t('albumDetail.openAlbum') }}
        </button>
      </form>
    </section>

    <template v-else-if="album">
      <!-- Back & Actions -->
      <div class="album-toolbar">
        <button class="ghost-btn" @click="$router.back()">{{ t('albumDetail.back') }}</button>
        <div class="toolbar-right">
          <button
            v-if="album.media_items && album.media_items.length"
            class="slideshow-btn"
            @click="startSlideshow"
          >
            {{ t('albumDetail.slideshow') }}
          </button>
          <span v-if="album.is_encrypted" class="pill pill--gold">{{ t('albumDetail.encrypted') }}</span>
          <span v-if="album.visibility === 'public'" class="pill pill--mint">{{ t('albumDetail.visibilityPublic') }}</span>
          <span v-else-if="album.visibility === 'guest_viewable'" class="pill pill--blue">{{ t('albumDetail.visibilityGuest') }}</span>
          <span v-else-if="album.visibility === 'partners_only'" class="pill pill--pink">{{ t('albumDetail.visibilityPartners') }}</span>
          <span v-else-if="album.visibility === 'private'" class="pill pill--gray">{{ t('albumDetail.visibilityPrivate') }}</span>
          <span v-else-if="album.visibility === 'password_protected'" class="pill pill--gold">{{ t('albumDetail.visibilityPassword') }}</span>
          <span v-for="tag in album.tags || []" :key="tag" class="pill pill--tag">#{{ tag }}</span>
        </div>
      </div>

      <!-- Album Header -->
      <article class="glass-card album-viewer">
        <header class="album-header">
          <h1 class="album-title">{{ album.title }}</h1>
          <div class="album-meta">
            <span>{{ album.author_nickname }}</span>
            <span>·</span>
            <span>{{ formatDate(album.created_at) }}</span>
            <span>·</span>
            <span>{{ t('albumDetail.photoCount', { count: album.media_count }) }}</span>
          </div>
          <p v-if="album.description" class="album-description">{{ album.description }}</p>
        </header>

        <div class="album-divider"></div>

        <!-- Media Grid -->
        <div class="album-media-grid">
          <div
            v-for="media in album.media_items"
            :key="media.media_id"
            class="media-item"
            @click="openLightbox(media)"
          >
            <img
              :src="resolveAssetUrl(media.thumbnail_url || media.file_url)"
              :alt="album.title"
              loading="lazy"
              class="media-thumbnail"
            />
          </div>
        </div>

        <div v-if="!album.media_items || !album.media_items.length" class="empty-media">
          <p>{{ t('albumDetail.emptyMedia') }}</p>
        </div>

        <!-- 评论区 -->
        <div class="album-divider"></div>
        <div class="comment-section">
          <h3 class="comment-section-title">{{ t('albumDetail.commentTitle', { count: album.comments?.length || 0 }) }}</h3>
          
          <CommentThread
            v-if="album.comments && album.comments.length"
            :comments="album.comments"
            :can-reply="Boolean(token)"
            :submit-reply="submitComment"
            :submitting="busy"
          />
          
          <div v-if="token" class="comment-input-row">
            <input
              v-model="commentInput"
              class="input-mini"
              :placeholder="t('albumDetail.commentPlaceholder')"
              @keyup.enter="submitComment()"
            />
            <button class="text-btn-mini" :disabled="busy" @click="submitComment()">{{ t('albumDetail.send') }}</button>
          </div>
          
          <div v-else class="comment-login-prompt">
            <p>{{ t('albumDetail.loginToComment') }}</p>
          </div>
        </div>
      </article>
    </template>

    <div v-else class="error-state glass-card">
      <p>{{ loadError || t('albumDetail.notFound') }}</p>
      <button class="ghost-btn" @click="$router.push('/albums')">{{ t('albumDetail.backToList') }}</button>
    </div>

    <!-- Lightbox -->
    <div v-if="lightboxMedia" class="lightbox" @click="closeLightbox">
      <div class="lightbox-content" @click.stop>
        <button class="lightbox-close" @click="closeLightbox">×</button>
        <img :src="resolveAssetUrl(lightboxMedia.file_url)" :alt="album?.title" class="lightbox-image" />
      </div>
    </div>

    <!-- 回忆播放 Slideshow -->
    <div v-if="slideshowActive" class="slideshow-overlay" @click="closeSlideshow">
      <div class="slideshow-stage" @click.stop>
        <div
          v-for="(media, idx) in slideshowImages"
          :key="media.media_id"
          class="slideshow-slide"
          :class="[{ active: idx === slideshowIndex }, idx % 2 === 0 ? 'kb-zoom-in' : 'kb-zoom-out']"
        >
          <img :src="resolveAssetUrl(media.file_url)" :alt="album?.title" class="slideshow-image" />
        </div>

        <div class="slideshow-title-bar">
          <span class="slideshow-title-text">{{ album?.title }}</span>
        </div>

        <button class="slideshow-close-btn" :title="t('albumDetail.closeEsc')" @click="closeSlideshow">×</button>
        <button class="slideshow-nav-btn slideshow-prev-btn" :title="t('albumDetail.prevSlide')" @click="prevSlide">‹</button>
        <button class="slideshow-nav-btn slideshow-next-btn" :title="t('albumDetail.nextSlide')" @click="nextSlide">›</button>

        <div class="slideshow-bottom-bar" @click.stop>
          <div class="slideshow-progress-track">
            <div class="slideshow-progress-fill" :style="{ width: slideProgress + '%' }"></div>
          </div>
          <div class="slideshow-controls-row">
            <span class="slideshow-counter">{{ slideshowIndex + 1 }} / {{ slideshowImages.length }}</span>
            <button class="ss-ctrl-btn" :title="slideshowPlaying ? t('albumDetail.pauseSpace') : t('albumDetail.playSpace')" @click="togglePlay">
              {{ slideshowPlaying ? "⏸" : "▶" }}
            </button>
            <div class="slideshow-music-group">
              <input
                v-model="musicUrl"
                :placeholder="t('albumDetail.musicUrlPlaceholder')"
                class="music-url-input"
                @keyup.enter="toggleMusic"
              />
              <button v-if="musicUrl" class="ss-ctrl-btn" :title="musicPlaying ? t('albumDetail.pauseMusic') : t('albumDetail.playMusic')" @click="toggleMusic">
                {{ musicPlaying ? t('albumDetail.musicPause') : t('albumDetail.musicPlay') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    <audio v-if="musicUrl" ref="musicAudio" :src="resolveAssetUrl(musicUrl)" loop preload="auto"></audio>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject, watch } from "vue";
import { useRoute } from "vue-router";
import { t } from "../locales";
import { fetchAlbum, postAlbumComment, resolveAssetUrl } from "../lib/api";
import { useAuth } from "../stores/auth";
import { parseError } from "../utils/helpers";
import CommentThread from "../components/CommentThread.vue";

const route = useRoute();
const showMessage = inject("showMessage");
const { token } = useAuth();

const album = ref(null);
const loading = ref(true);
const commentInput = ref("");
const busy = ref(false);
const lightboxMedia = ref(null);
const requiresPassword = ref(false);
const passwordInput = ref("");
const accessError = ref("");
const loadError = ref("");
let loadGeneration = 0;

// ── 回忆播放 Slideshow ──────────────────────────────────────────────
const slideshowActive = ref(false);
const slideshowIndex = ref(0);
const slideshowPlaying = ref(true);
const slideProgress = ref(0);
const musicUrl = ref("");
const musicPlaying = ref(false);
const musicAudio = ref(null);
let slideshowTimer = null;
const SLIDE_INTERVAL = 4500;

const slideshowImages = computed(() => {
  if (!album.value || !album.value.media_items) return [];
  const imgs = album.value.media_items.filter((m) => m.media_type === "Image");
  return imgs.length ? imgs : album.value.media_items;
});

function startSlideshow() {
  if (!slideshowImages.value.length) return;
  slideshowIndex.value = 0;
  slideshowActive.value = true;
  slideshowPlaying.value = true;
  slideProgress.value = 0;
  startSlideTimer();
}

function closeSlideshow() {
  slideshowActive.value = false;
  stopSlideTimer();
  if (musicAudio.value) {
    musicAudio.value.pause();
  }
  musicPlaying.value = false;
}

function startSlideTimer() {
  stopSlideTimer();
  if (!slideshowPlaying.value) return;
  let elapsed = 0;
  const tickMs = 60;
  slideshowTimer = setInterval(() => {
    elapsed += tickMs;
    slideProgress.value = Math.min(100, (elapsed / SLIDE_INTERVAL) * 100);
    if (elapsed >= SLIDE_INTERVAL) {
      nextSlide();
      elapsed = 0;
    }
  }, tickMs);
}

function stopSlideTimer() {
  if (slideshowTimer) {
    clearInterval(slideshowTimer);
    slideshowTimer = null;
  }
}

function nextSlide() {
  if (!slideshowImages.value.length) return;
  slideshowIndex.value = (slideshowIndex.value + 1) % slideshowImages.value.length;
  slideProgress.value = 0;
}

function prevSlide() {
  if (!slideshowImages.value.length) return;
  slideshowIndex.value =
    slideshowIndex.value === 0
      ? slideshowImages.value.length - 1
      : slideshowIndex.value - 1;
  slideProgress.value = 0;
}

function togglePlay() {
  slideshowPlaying.value = !slideshowPlaying.value;
  if (slideshowPlaying.value) {
    startSlideTimer();
  } else {
    stopSlideTimer();
  }
}

function toggleMusic() {
  const audio = musicAudio.value;
  if (!audio || !musicUrl.value) return;
  if (musicPlaying.value) {
    audio.pause();
    musicPlaying.value = false;
  } else {
    audio.play()
      .then(() => {
        musicPlaying.value = true;
      })
      .catch(() => {
        showMessage(t("albumDetail.musicFailed"));
      });
  }
}

function handleSlideshowKeydown(e) {
  if (!slideshowActive.value) return;
  switch (e.key) {
    case "Escape":
      e.preventDefault();
      closeSlideshow();
      break;
    case "ArrowRight":
      e.preventDefault();
      nextSlide();
      break;
    case "ArrowLeft":
      e.preventDefault();
      prevSlide();
      break;
    case " ":
      e.preventDefault();
      togglePlay();
      break;
  }
}

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
    const data = await fetchAlbum(route.params.alb_id, { password });
    if (generation !== loadGeneration) return;
    album.value = data;
    requiresPassword.value = false;
    accessError.value = "";
    passwordInput.value = "";
  } catch (error) {
    if (generation !== loadGeneration) return;
    album.value = null;
    if (isPasswordChallenge(error)) {
      requiresPassword.value = true;
      accessError.value = error.response.status === 403 ? t('albumDetail.passwordIncorrect') : "";
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
  album.value = null;
  lightboxMedia.value = null;
  requiresPassword.value = false;
  passwordInput.value = "";
  accessError.value = "";
  loadError.value = "";
  closeSlideshow();
  musicUrl.value = "";
  load();
}

function formatDate(raw) {
  if (!raw) return "";
  return new Date(raw).toLocaleDateString("zh-CN", {
    year: "numeric", month: "long", day: "numeric"
  });
}

function openLightbox(media) {
  lightboxMedia.value = media;
}

function closeLightbox() {
  lightboxMedia.value = null;
}

async function submitComment(payload = null) {
  const content = payload?.content ?? commentInput.value;
  if (!content || !content.trim()) return;

  busy.value = true;
  try {
    await postAlbumComment(route.params.alb_id, {
      content: content.trim(),
      parent_cid: payload?.parentCid || null,
      mention_uids: payload?.mentionUids || []
    });

    if (!payload) {
      commentInput.value = "";
    }

    // 重新加载相册以获取最新评论
    await load();
    showMessage(t('albumDetail.commentSuccess'));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  document.addEventListener("keydown", handleSlideshowKeydown);
  load();
});
watch(() => route.params.alb_id, resetForRoute);

onUnmounted(() => {
  document.removeEventListener("keydown", handleSlideshowKeydown);
  stopSlideTimer();
});
</script>

<style scoped>
.album-toolbar {
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

.album-viewer {
  padding: 2.5rem;
  max-width: 1200px;
  margin: 0 auto;
}

.album-header {
  margin-bottom: 0;
}

.album-title {
  font-size: clamp(1.6rem, 3.5vw, 2.2rem);
  font-weight: 800;
  color: #0f172a;
  line-height: 1.3;
  margin: 0 0 0.75rem;
}

.album-meta {
  display: flex;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: #64748b;
  margin-bottom: 1rem;
}

.album-description {
  font-size: 1.05rem;
  color: #475569;
  line-height: 1.7;
  margin: 1rem 0 0;
}

.album-divider {
  border: none;
  border-top: 1px solid rgba(148, 163, 184, 0.25);
  margin: 2rem 0;
}

.album-media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
  margin: 2rem 0;
}

.media-item {
  position: relative;
  aspect-ratio: 1;
  overflow: hidden;
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.2s;
}

.media-item:hover {
  transform: scale(1.02);
}

.media-thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.empty-media {
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

/* Lightbox */
.lightbox {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 2rem;
}

.lightbox-content {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
}

.lightbox-image {
  max-width: 100%;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 8px;
}

.lightbox-close {
  position: absolute;
  top: -3rem;
  right: 0;
  background: transparent;
  border: none;
  color: white;
  font-size: 3rem;
  cursor: pointer;
  line-height: 1;
  padding: 0;
  width: 3rem;
  height: 3rem;
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

/* ── 回忆播放 Slideshow ─────────────────────────────────────────── */
.slideshow-btn {
  border: 0;
  border-radius: 10px;
  background: linear-gradient(135deg, #818cf8, #c084fc);
  color: #fff;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0.4rem 0.85rem;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  box-shadow: 0 2px 8px rgba(129, 140, 248, 0.35);
}

.slideshow-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(129, 140, 248, 0.45);
}

.slideshow-overlay {
  position: fixed;
  inset: 0;
  background: #000;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.slideshow-stage {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.slideshow-slide {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 1.2s ease-in-out;
  pointer-events: none;
}

.slideshow-slide.active {
  opacity: 1;
  pointer-events: auto;
}

.slideshow-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* Ken Burns effect — alternating zoom direction per slide */
.slideshow-slide.kb-zoom-in .slideshow-image {
  animation: kbZoomIn 6s ease-out forwards;
}

.slideshow-slide.kb-zoom-out .slideshow-image {
  animation: kbZoomOut 6s ease-out forwards;
}

@keyframes kbZoomIn {
  from { transform: scale(1); }
  to { transform: scale(1.12); }
}

@keyframes kbZoomOut {
  from { transform: scale(1.12); }
  to { transform: scale(1); }
}

.slideshow-title-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 1.5rem 2rem;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.55), transparent);
  pointer-events: none;
  z-index: 3;
}

.slideshow-title-text {
  color: #fff;
  font-size: 1.3rem;
  font-weight: 700;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
}

.slideshow-close-btn {
  position: absolute;
  top: 1rem;
  right: 1.5rem;
  z-index: 5;
  background: rgba(0, 0, 0, 0.4);
  border: none;
  color: #fff;
  font-size: 2rem;
  cursor: pointer;
  width: 2.8rem;
  height: 2.8rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: background 0.2s;
}

.slideshow-close-btn:hover {
  background: rgba(0, 0, 0, 0.7);
}

.slideshow-nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 5;
  background: rgba(0, 0, 0, 0.35);
  border: none;
  color: #fff;
  font-size: 2.5rem;
  cursor: pointer;
  width: 3rem;
  height: 4rem;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: background 0.2s;
}

.slideshow-nav-btn:hover {
  background: rgba(0, 0, 0, 0.65);
}

.slideshow-prev-btn {
  left: 1rem;
}

.slideshow-next-btn {
  right: 1rem;
}

.slideshow-bottom-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 1rem 2rem 1.5rem;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.7), transparent);
  z-index: 4;
}

.slideshow-progress-track {
  width: 100%;
  height: 3px;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 0.75rem;
}

.slideshow-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #818cf8, #c084fc);
  border-radius: 2px;
  transition: width 0.06s linear;
}

.slideshow-controls-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.slideshow-counter {
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.85rem;
  font-weight: 600;
  min-width: 3.5rem;
}

.ss-ctrl-btn {
  border: 0;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0.4rem 0.8rem;
  cursor: pointer;
  transition: background 0.2s;
}

.ss-ctrl-btn:hover {
  background: rgba(255, 255, 255, 0.28);
}

.slideshow-music-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
}

.music-url-input {
  width: 220px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  padding: 0.4rem 0.7rem;
  font-size: 0.8rem;
  outline: none;
}

.music-url-input::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.music-url-input:focus {
  border-color: rgba(167, 139, 250, 0.7);
  box-shadow: 0 0 0 2px rgba(167, 139, 250, 0.2);
}

@media (max-width: 640px) {
  .slideshow-nav-btn {
    width: 2.4rem;
    height: 3.2rem;
    font-size: 2rem;
  }

  .slideshow-title-text {
    font-size: 1.05rem;
  }

  .music-url-input {
    width: 140px;
  }

  .slideshow-bottom-bar {
    padding: 0.75rem 1rem 1rem;
  }
}
</style>
