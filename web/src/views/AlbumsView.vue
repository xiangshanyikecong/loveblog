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
    <ModuleTabs :items="contentTabs" :label="t('albums.tabAriaLabel')" />

    <article class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t('albums.title') }}</h2>
        <button class="ghost-btn" @click="loadAlbums">{{ t('albums.refresh') }}</button>
      </div>

      <form v-if="canManageContent" class="form-grid" @submit.prevent="createAlbumItem">
        <input v-model="albumForm.title" class="input" :placeholder="t('albums.titlePlaceholder')" />
        <input v-model="albumForm.coverUrl" class="input" :placeholder="t('albums.coverUrlPlaceholder')" />
        <textarea v-model="albumForm.description" class="input col-2 min-h-20" :placeholder="t('albums.descriptionPlaceholder')" />
        <input v-model="albumForm.tagsText" class="input col-2" :placeholder="t('albums.tagsPlaceholder')" />
        <input v-model="albumForm.mediaUrl" class="input col-2" :placeholder="t('albums.uploadedUrlPlaceholder')" readonly />
        <div
          class="upload-dropzone col-2"
          :class="{
            'upload-dropzone--active': albumDropActive,
            'upload-dropzone--busy': busy.upload
          }"
          @click="triggerAlbumFilePicker"
          @dragenter.prevent="albumDropActive = true"
          @dragover.prevent="albumDropActive = true"
          @dragleave.prevent="albumDropActive = false"
          @drop.prevent="handleAlbumDrop"
        >
          <input
            ref="albumFileInput"
            class="upload-dropzone-input"
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            @change="handleAlbumFileChange"
          />
          <div class="upload-dropzone-body">
            <p class="upload-dropzone-title">
              {{ busy.upload ? t('albums.uploading') : t('albums.dropzoneHint') }}
            </p>
            <p class="upload-dropzone-meta">{{ t('albums.dropzoneMeta') }}</p>
          </div>
        </div>
        <div v-if="albumUploadPreview.url" class="upload-preview col-2">
          <img :src="resolveAssetUrl(albumUploadPreview.url)" :alt="albumUploadPreview.fileName || t('albums.uploadPreview')" class="upload-preview-image" />
          <div class="upload-preview-meta">
            <p>{{ albumUploadPreview.fileName || t('albums.uploadedImage') }}</p>
            <p>{{ formatFileSize(albumUploadPreview.size) }}</p>
          </div>
          <button type="button" class="text-btn upload-preview-remove" @click="clearAlbumUpload">{{ t('albums.removeImage') }}</button>
        </div>
        <label class="col-2">
          {{ t('albums.visibilityLevel') }}
          <select v-model="albumForm.visibility" class="input">
            <option value="public">{{ t('albums.visibilityPublic') }}</option>
            <option value="guest_viewable">{{ t('albums.visibilityGuest') }}</option>
            <option value="partners_only">{{ t('albums.visibilityPartners') }}</option>
            <option value="private">{{ t('albums.visibilityPrivate') }}</option>
            <option value="password_protected">{{ t('albums.visibilityPassword') }}</option>
          </select>
        </label>
        <input 
          v-if="albumForm.visibility === 'password_protected'"
          v-model="albumForm.password" 
          type="password" 
          class="input col-2" 
          :placeholder="t('albums.passwordPlaceholder')" 
        />
        <button class="btn-primary col-2" :disabled="busy.create || busy.upload">
          {{ busy.upload ? t('albums.uploading') : busy.create ? t('albums.creating') : t('albums.createAlbum') }}
        </button>
      </form>
    </article>

    <article class="album-grid">
      <div 
        v-for="item in albums" 
        :key="item.alb_id" 
        class="glass-card section-block album-card"
        @click="goToAlbum(item.alb_id)"
      >
        <img v-if="item.cover_url" :src="resolveAssetUrl(item.cover_url)" :alt="item.title" class="album-cover" />
        <p class="entity-title">{{ item.title }}</p>
        <p class="entity-desc">{{ t('albums.mediaCount', { n: item.media_count }) }}</p>
        <p class="entity-desc">{{ item.description || t('albums.noDescription') }}</p>
        <p class="entity-desc">
          <span v-if="item.visibility === 'public'" class="pill pill--mint">{{ t('albums.visibilityPublicShort') }}</span>
          <span v-else-if="item.visibility === 'guest_viewable'" class="pill pill--blue">{{ t('albums.visibilityGuestShort') }}</span>
          <span v-else-if="item.visibility === 'partners_only'" class="pill pill--pink">{{ t('albums.visibilityPartnersShort') }}</span>
          <span v-else-if="item.visibility === 'private'" class="pill pill--gray">{{ t('albums.visibilityPrivateShort') }}</span>
          <span v-else-if="item.visibility === 'password_protected'" class="pill pill--gold">{{ t('albums.visibilityPasswordShort') }}</span>
          <span v-for="tag in item.tags || []" :key="tag" class="pill pill--tag">#{{ tag }}</span>
        </p>
      </div>
      <p v-if="!albums.length" class="muted">{{ t('albums.noAlbums') }}</p>
    </article>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, inject } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import ModuleTabs from "../components/ModuleTabs.vue";
import { fetchAlbums, createAlbum, resolveAssetUrl, uploadAlbumImage } from "../lib/api";
import { parseError, formatFileSize, parseTags } from "../utils/helpers";
import { useAuth } from "../stores/auth";

const router = useRouter();
const showMessage = inject("showMessage");
const { canManageContent } = useAuth();
const { t } = useI18n();
const albums = ref([]);
const contentTabs = [
  { label: t("albums.tabArticles"), to: "/articles" },
  { label: t("albums.tabAlbums"), to: "/albums" },
  { label: t("albums.tabSearch"), to: "/search" }
];

const busy = reactive({
  create: false,
  upload: false
});

const albumForm = reactive({
  title: "",
  description: "",
  tagsText: "",
  coverUrl: "",
  mediaUrl: "",
  visibility: "public",
  password: ""
});

const albumFileInput = ref(null);
const albumDropActive = ref(false);
const albumUploadPreview = reactive({
  url: "",
  fileName: "",
  size: 0
});

async function loadAlbums() {
  try {
    const data = await fetchAlbums();
    albums.value = data.items || [];
  } catch (error) {
    showMessage(parseError(error));
  }
}

function triggerAlbumFilePicker() {
  albumFileInput.value?.click();
}

async function handleAlbumFileChange(event) {
  const [file] = Array.from(event.target.files || []);
  await uploadSelectedAlbumFile(file);
  event.target.value = "";
}

async function handleAlbumDrop(event) {
  albumDropActive.value = false;
  const [file] = Array.from(event.dataTransfer?.files || []);
  await uploadSelectedAlbumFile(file);
}

async function uploadSelectedAlbumFile(file) {
  if (!file) {
    return;
  }

  const allowedTypes = ["image/jpeg", "image/png", "image/webp", "image/gif"];
  if (!allowedTypes.includes(file.type)) {
    showMessage(t("albums.unsupportedImageType"));
    return;
  }

  busy.upload = true;

  try {
    const previousMediaUrl = albumForm.mediaUrl;
    const shouldSyncCover = !albumForm.coverUrl || albumForm.coverUrl === previousMediaUrl;
    const data = await uploadAlbumImage(file);

    albumForm.mediaUrl = data.url;
    if (shouldSyncCover) {
      albumForm.coverUrl = data.url;
    }

    albumUploadPreview.url = data.url;
    albumUploadPreview.fileName = data.file_name || file.name;
    albumUploadPreview.size = data.size || file.size || 0;
    showMessage(t("albums.uploadSuccess"));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.upload = false;
  }
}

function clearAlbumUpload() {
  if (albumForm.coverUrl === albumForm.mediaUrl) {
    albumForm.coverUrl = "";
  }
  albumForm.mediaUrl = "";
  albumUploadPreview.url = "";
  albumUploadPreview.fileName = "";
  albumUploadPreview.size = 0;
  albumDropActive.value = false;

  if (albumFileInput.value) {
    albumFileInput.value.value = "";
  }
}

async function createAlbumItem() {
  busy.create = true;
  try {
    const payload = {
      title: albumForm.title,
      description: albumForm.description || null,
      cover_url: albumForm.coverUrl || albumForm.mediaUrl || null,
      visibility: albumForm.visibility,
      tags: parseTags(albumForm.tagsText),
      media_items: albumForm.mediaUrl
        ? [
            {
              media_type: "Image",
              file_url: albumForm.mediaUrl,
              thumbnail_url: albumForm.coverUrl || albumForm.mediaUrl || null
            }
          ]
        : []
    };
    
    // 只有在密码保护模式下才发送密码
    if (albumForm.visibility === 'password_protected' && albumForm.password) {
      payload.password = albumForm.password;
    }
    
    await createAlbum(payload);
    showMessage(t("albums.createSuccess"));
    albumForm.title = "";
    albumForm.description = "";
    albumForm.tagsText = "";
    albumForm.coverUrl = "";
    albumForm.password = "";
    clearAlbumUpload();
    await loadAlbums();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.create = false;
  }
}

function goToAlbum(albId) {
  router.push({ name: "album-detail", params: { alb_id: albId } });
}

onMounted(() => {
  loadAlbums();
});
</script>


<style scoped>
.album-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.album-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}
</style>
