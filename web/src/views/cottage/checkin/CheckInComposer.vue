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
  <article class="glass-card section-block composer">
    <h3 class="composer-heading">{{ t('checkInComposer.newCheckin') }}</h3>

    <textarea
      v-model="content"
      class="composer-input"
      :placeholder="t('checkInComposer.notePlaceholder')"
      rows="3"
      maxlength="1000"
    />

    <div class="composer-media">
      <div
        v-for="(url, idx) in mediaUrls"
        :key="url"
        class="composer-thumb"
      >
        <img :src="resolveAssetUrl(url)" alt="" />
        <button
          type="button"
          class="composer-thumb-remove"
          :aria-label="t('checkInComposer.removePhoto')"
          @click="removeMedia(idx)"
        >×</button>
      </div>
      <label v-if="mediaUrls.length < 9" class="composer-add">
        <input
          ref="fileInput"
          type="file"
          accept="image/*"
          hidden
          @change="onFileSelected"
        />
        <span v-if="!uploading">{{ t('checkInComposer.addPhoto') }}</span>
        <span v-else>{{ t('checkInComposer.uploading') }}</span>
      </label>
    </div>

    <div class="composer-location">
      <span class="composer-location-label">{{ t('checkInComposer.locationLabel') }}</span>
      <span class="composer-location-state">{{ locationStateLabel }}</span>
      <button
        v-if="locationState !== 'granted'"
        type="button"
        class="composer-loc-btn composer-loc-btn--primary"
        :disabled="locationState === 'requesting'"
        @click="requestLocation"
      >
        {{ locationState === 'requesting' ? t('checkInComposer.getRequesting') : t('checkInComposer.getLocation') }}
      </button>
      <button
        v-if="locationState !== 'idle' && locationState !== 'skipped'"
        type="button"
        class="composer-loc-btn"
        @click="skipLocation"
      >
        {{ t('checkInComposer.skipLocation') }}
      </button>
    </div>

    <p v-if="locationHint" class="composer-location-hint">{{ locationHint }}</p>

    <p v-if="errorMsg" class="composer-error">{{ errorMsg }}</p>
    <p v-if="successMsg" class="composer-success">{{ successMsg }}</p>

    <div class="composer-actions">
      <button
        type="button"
        class="composer-submit"
        :disabled="busy"
        @click="submit"
      >
        {{ busy ? t('checkInComposer.sending') : t('checkInComposer.submit') }}
      </button>
    </div>
  </article>
</template>

<script setup>
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  createCheckin,
  resolveAssetUrl,
  uploadCheckinImage
} from "../../../lib/api";

const { t } = useI18n();

const emit = defineEmits(["submitted"]);

const content = ref("");
const mediaUrls = ref([]);
const fileInput = ref(null);
const uploading = ref(false);
const busy = ref(false);
const errorMsg = ref("");
const successMsg = ref("");

// State machine: idle -> requesting -> granted | denied | failed | skipped
// granted holds latitude/longitude in `coords` (NOT persisted anywhere).
const locationState = ref("idle");
const coords = ref(null); // { latitude, longitude } when granted, else null
const locationHint = ref("");
let locationRequestId = 0;

const locationStateLabel = computed(() => {
  switch (locationState.value) {
    case "idle":
      return t('checkInComposer.locStateIdle');
    case "requesting":
      return t('checkInComposer.locStateRequesting');
    case "granted":
      return t('checkInComposer.locStateGranted');
    case "denied":
      return t('checkInComposer.locStateDenied');
    case "failed":
      return t('checkInComposer.locStateFailed');
    case "skipped":
      return t('checkInComposer.locStateSkipped');
    default:
      return "";
  }
});

function resetForm() {
  locationRequestId += 1;
  content.value = "";
  mediaUrls.value = [];
  coords.value = null;
  locationState.value = "idle";
  locationHint.value = "";
  errorMsg.value = "";
}

async function onFileSelected(evt) {
  const file = evt.target.files && evt.target.files[0];
  evt.target.value = ""; // allow selecting the same file again later
  if (!file) return;
  if (mediaUrls.value.length >= 9) {
    errorMsg.value = t('checkInComposer.maxPhotos');
    return;
  }
  uploading.value = true;
  errorMsg.value = "";
  try {
    const data = await uploadCheckinImage(file);
    if (data && data.url) {
      mediaUrls.value.push(data.url);
    }
  } catch (e) {
    errorMsg.value = e?.response?.data?.detail || t('checkInComposer.uploadFailed');
  } finally {
    uploading.value = false;
  }
}

function removeMedia(idx) {
  mediaUrls.value.splice(idx, 1);
}

function requestLocation() {
  const requestId = ++locationRequestId;
  errorMsg.value = "";
  locationHint.value = "";

  // Browsers refuse geolocation in non-secure contexts (anything other than
  // HTTPS, localhost, 127.0.0.1, or file://). They typically don't even
  // show a permission prompt — they just deny silently. Detect this
  // proactively so the user knows what to do instead of staring at a
  // mysterious "已拒绝".
  if (typeof window !== "undefined" && window.isSecureContext === false) {
    locationState.value = "denied";
    locationHint.value = t('checkInComposer.locHintInsecure');
    return;
  }

  if (!navigator.geolocation) {
    locationState.value = "failed";
    locationHint.value = t('checkInComposer.locHintUnsupported');
    return;
  }

  locationState.value = "requesting";

  // If the Permissions API is available, do a non-prompting check first.
  // When state is 'denied' before we even call getCurrentPosition, it means
  // the user (or browser policy) blocked us previously — no prompt would
  // appear if we called anyway.
  const proceed = () => {
    if (requestId !== locationRequestId || locationState.value === "skipped") return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (requestId !== locationRequestId || locationState.value === "skipped") return;
        coords.value = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude
        };
        locationState.value = "granted";
        locationHint.value = "";
      },
      (err) => {
        if (requestId !== locationRequestId || locationState.value === "skipped") return;
        coords.value = null;
        if (err && err.code === err.PERMISSION_DENIED) {
          locationState.value = "denied";
          locationHint.value =
            t('checkInComposer.locHintDenied');
        } else if (err && err.code === err.POSITION_UNAVAILABLE) {
          locationState.value = "failed";
          locationHint.value = t('checkInComposer.locHintUnavailable');
        } else if (err && err.code === err.TIMEOUT) {
          locationState.value = "failed";
          locationHint.value = t('checkInComposer.locHintTimeout');
        } else {
          locationState.value = "failed";
          locationHint.value = err?.message || t('checkInComposer.locHintFailed');
        }
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 }
    );
  };

  if (
    typeof navigator !== "undefined" &&
    navigator.permissions &&
    typeof navigator.permissions.query === "function"
  ) {
    navigator.permissions
      .query({ name: "geolocation" })
      .then((status) => {
        if (requestId !== locationRequestId || locationState.value === "skipped") return;
        if (status.state === "denied") {
          locationState.value = "denied";
          locationHint.value =
            t('checkInComposer.locHintDeniedRemembered');
          return;
        }
        proceed();
      })
      .catch(() => {
        if (requestId === locationRequestId) proceed();
      });
  } else {
    proceed();
  }
}

function skipLocation() {
  locationRequestId += 1;
  locationState.value = "skipped";
  coords.value = null;
  locationHint.value = "";
}

function buildPayload() {
  const payload = {};
  const trimmed = content.value.trim();
  if (trimmed) payload.content = trimmed;
  if (mediaUrls.value.length) payload.media_urls = [...mediaUrls.value];

  if (locationState.value === "granted" && coords.value) {
    payload.latitude = coords.value.latitude;
    payload.longitude = coords.value.longitude;
  } else if (
    locationState.value === "denied" ||
    locationState.value === "failed"
  ) {
    payload.location_permission_denied = true;
  }
  // idle / skipped: send neither lat/lng nor location_permission_denied
  // → server stores location_status=omitted.
  return payload;
}

async function submit() {
  errorMsg.value = "";
  successMsg.value = "";

  const trimmed = content.value.trim();
  const hasContent = trimmed.length > 0;
  const hasMedia = mediaUrls.value.length > 0;
  const hasLocationIntent =
    locationState.value === "granted" ||
    locationState.value === "denied" ||
    locationState.value === "failed";
  if (!hasContent && !hasMedia && !hasLocationIntent) {
    errorMsg.value = t('checkInComposer.requireOne');
    return;
  }

  busy.value = true;
  try {
    await createCheckin(buildPayload());
    successMsg.value = t('checkInComposer.sent');
    resetForm();
    emit("submitted");
    setTimeout(() => {
      successMsg.value = "";
    }, 3000);
  } catch (e) {
    errorMsg.value = e?.response?.data?.detail || t('checkInComposer.submitFailed');
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.composer {
  padding: 1.2rem 1.4rem;
  display: grid;
  gap: 0.85rem;
}

.composer-heading {
  margin: 0;
  font-size: 1rem;
  color: #2f3754;
}

.composer-input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 12px;
  padding: 0.7rem 0.85rem;
  font-size: 0.9rem;
  resize: vertical;
  background: rgba(255, 255, 255, 0.85);
  font-family: inherit;
}

.composer-media {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.composer-thumb {
  position: relative;
  width: 84px;
  height: 84px;
  border-radius: 10px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.16);
}

.composer-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.composer-thumb-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: none;
  background: rgba(15, 23, 42, 0.55);
  color: #fff;
  font-size: 0.95rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.composer-add {
  width: 84px;
  height: 84px;
  border-radius: 10px;
  border: 1.5px dashed rgba(148, 163, 184, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.78rem;
  color: #475569;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.55);
}

.composer-add:hover {
  border-color: rgba(143, 155, 255, 0.7);
  color: #2f3754;
}

.composer-location {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.55rem;
  font-size: 0.85rem;
  color: #475569;
}

.composer-location-label {
  font-weight: 600;
  color: #2f3754;
}

.composer-location-state {
  color: #64748b;
  margin-right: 0.3rem;
}

.composer-loc-btn {
  min-height: 44px;
  padding: 0.4rem 0.95rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  font-size: 0.82rem;
  cursor: pointer;
}

.composer-loc-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.composer-loc-btn--primary {
  border-color: transparent;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
}

.composer-error {
  margin: 0;
  font-size: 0.84rem;
  color: #dc2626;
}

.composer-location-hint {
  margin: 0;
  padding: 0.55rem 0.75rem;
  border-radius: 10px;
  background: rgba(252, 211, 77, 0.18);
  color: #92400e;
  font-size: 0.8rem;
  line-height: 1.55;
}

.composer-success {
  margin: 0;
  font-size: 0.84rem;
  color: #047857;
}

.composer-actions {
  display: flex;
  justify-content: flex-end;
}

.composer-submit {
  min-height: 44px;
  padding: 0.55rem 1.4rem;
  border-radius: 999px;
  border: none;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(143, 155, 255, 0.32);
}

.composer-submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}
</style>
