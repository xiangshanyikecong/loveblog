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
  <div class="media-capture">
    <div v-if="!recordedUrl && !uploadedMedia" class="mc-modes">
      <button
        v-if="allowAudio"
        type="button"
        class="mc-mode-btn"
        :class="{ active: mode === 'audio' }"
        @click="setMode('audio')"
      >🎙️ {{ t("mediaCapture.audioMode") }}</button>
      <button
        v-if="allowVideo"
        type="button"
        class="mc-mode-btn"
        :class="{ active: mode === 'video' }"
        @click="setMode('video')"
      >🎬 {{ t("mediaCapture.videoMode") }}</button>
    </div>

    <!-- Live preview while recording video -->
    <video
      v-show="mode === 'video' && (recording || stream) && !recordedUrl"
      ref="previewEl"
      class="mc-preview"
      muted
      playsinline
    ></video>

    <div v-if="!recordedUrl && !uploadedMedia" class="mc-controls">
      <button
        v-if="!recording"
        type="button"
        class="mc-rec-btn"
        :disabled="busy"
        @click="startRecording"
      >
        <span class="mc-dot"></span>
        {{ mode === 'video' ? t("mediaCapture.startVideo") : t("mediaCapture.startAudio") }}
      </button>
      <button
        v-else
        type="button"
        class="mc-stop-btn"
        @click="stopRecording"
      >■ {{ t("mediaCapture.stop") }} · {{ formatTime(elapsed) }}</button>

      <label class="mc-file-btn">
        {{ t("mediaCapture.selectFile") }}
        <input
          type="file"
          :accept="fileAccept"
          class="hidden-input"
          @change="onFilePick"
        />
      </label>
    </div>

    <!-- Local preview before confirming upload -->
    <div v-if="recordedUrl && !uploadedMedia" class="mc-review">
      <audio v-if="mode === 'audio'" :src="recordedUrl" controls class="mc-player"></audio>
      <video v-else :src="recordedUrl" controls playsinline class="mc-player"></video>
      <div class="mc-review-actions">
        <button type="button" class="mc-confirm" :disabled="busy" @click="confirmUpload">
          {{ busy ? t("mediaCapture.uploading", { progress }) : t("mediaCapture.useRecording") }}
        </button>
        <button type="button" class="mc-discard" :disabled="busy" @click="discard">{{ t("mediaCapture.redo") }}</button>
      </div>
    </div>

    <!-- Uploaded result -->
    <div v-if="uploadedMedia" class="mc-done">
      <span class="mc-done-label">
        {{ uploadedMedia.media_type === 'video' ? t("mediaCapture.videoLabel") : t("mediaCapture.audioLabel") }}
        {{ t("mediaCapture.ready") }} · {{ formatTime(uploadedMedia.media_duration_sec) }}
      </span>
      <button type="button" class="mc-discard" @click="reset">{{ t("mediaCapture.remove") }}</button>
    </div>

    <p v-if="error" class="mc-error">{{ error }}</p>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, computed } from "vue";
import { uploadCapsuleMedia } from "../lib/api";
import { t } from "../locales";

const props = defineProps({
  allowAudio: { type: Boolean, default: true },
  allowVideo: { type: Boolean, default: true }
});
const emit = defineEmits(["update"]);

const mode = ref(props.allowAudio ? "audio" : "video");
const recording = ref(false);
const busy = ref(false);
const progress = ref(0);
const elapsed = ref(0);
const error = ref("");
const recordedUrl = ref("");
const uploadedMedia = ref(null);

const previewEl = ref(null);
let mediaRecorder = null;
let chunks = [];
let stream = null;
let recordedBlob = null;
let recordedMime = "";
let timer = null;
let startedAt = 0;
let disposed = false;
let captureRequestId = 0;

const fileAccept = computed(() => (mode.value === "video" ? "video/*" : "audio/*"));

function setMode(next) {
  if (recording.value) return;
  mode.value = next;
}

function formatTime(totalSec) {
  const s = Math.max(0, Math.round(totalSec || 0));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

function pickMime(kind) {
  const candidates =
    kind === "video"
      ? ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm", "video/mp4"]
      : ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) {
    return "";
  }
  return candidates.find((c) => MediaRecorder.isTypeSupported(c)) || "";
}

async function startRecording() {
  error.value = "";
  if (typeof MediaRecorder === "undefined") {
    error.value = t("mediaCapture.unsupportedRecorder");
    return;
  }
  const requestId = ++captureRequestId;
  busy.value = true;
  let acquiredStream;
  try {
    const constraints = mode.value === "video" ? { audio: true, video: true } : { audio: true };
    acquiredStream = await navigator.mediaDevices.getUserMedia(constraints);
  } catch (_error) {
    if (!disposed && requestId === captureRequestId) {
      error.value = t("mediaCapture.permissionError");
    }
    return;
  } finally {
    if (!disposed && requestId === captureRequestId) busy.value = false;
  }

  if (disposed || requestId !== captureRequestId) {
    acquiredStream.getTracks().forEach((track) => track.stop());
    return;
  }
  stream = acquiredStream;

  if (mode.value === "video" && previewEl.value) {
    previewEl.value.srcObject = stream;
    previewEl.value.play().catch(() => {});
  }

  recordedMime = pickMime(mode.value);
  try {
    mediaRecorder = recordedMime
      ? new MediaRecorder(stream, { mimeType: recordedMime })
      : new MediaRecorder(stream);
  } catch (_error) {
    error.value = t("mediaCapture.recorderInitFailed");
    stopStream();
    return;
  }

  chunks = [];
  mediaRecorder.ondataavailable = (ev) => {
    if (ev.data && ev.data.size > 0) chunks.push(ev.data);
  };
  mediaRecorder.onstop = () => {
    if (disposed || requestId !== captureRequestId) {
      chunks = [];
      stopStream();
      return;
    }
    const type = recordedMime || (mode.value === "video" ? "video/webm" : "audio/webm");
    recordedBlob = new Blob(chunks, { type });
    recordedUrl.value = URL.createObjectURL(recordedBlob);
    stopStream();
  };

  mediaRecorder.start();
  recording.value = true;
  startedAt = Date.now();
  elapsed.value = 0;
  timer = setInterval(() => {
    elapsed.value = (Date.now() - startedAt) / 1000;
  }, 200);
}

function stopRecording() {
  if (mediaRecorder && recording.value) {
    elapsed.value = (Date.now() - startedAt) / 1000;
    try {
      mediaRecorder.stop();
    } catch (_error) {
      /* ignore */
    }
  }
  recording.value = false;
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

function stopStream() {
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  if (previewEl.value) previewEl.value.srcObject = null;
}

function onFilePick(ev) {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  error.value = "";
  recordedBlob = file;
  recordedMime = file.type;
  mode.value = file.type.startsWith("video") ? "video" : "audio";
  recordedUrl.value = URL.createObjectURL(file);
  elapsed.value = 0;
  // Try to read duration from the decoded media metadata.
  const probe = document.createElement(mode.value === "video" ? "video" : "audio");
  probe.preload = "metadata";
  probe.onloadedmetadata = () => {
    if (isFinite(probe.duration)) elapsed.value = probe.duration;
  };
  probe.src = recordedUrl.value;
}

async function confirmUpload() {
  if (!recordedBlob) return;
  busy.value = true;
  progress.value = 0;
  error.value = "";
  try {
    const ext = (recordedMime.split("/")[1] || "webm").split(";")[0];
    const filename = `${mode.value}-${Date.now()}.${ext}`;
    const file =
      recordedBlob instanceof File
        ? recordedBlob
        : new File([recordedBlob], filename, { type: recordedMime });
    const res = await uploadCapsuleMedia(file, (p) => (progress.value = p));
    uploadedMedia.value = {
      media_url: res.url,
      media_type: mode.value,
      media_duration_sec: Math.round(elapsed.value)
    };
    emit("update", uploadedMedia.value);
    if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value);
    recordedUrl.value = "";
  } catch (e) {
    error.value = e?.response?.data?.detail || t("mediaCapture.uploadFailed");
  } finally {
    busy.value = false;
  }
}

function discard() {
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value);
  recordedUrl.value = "";
  recordedBlob = null;
  chunks = [];
  elapsed.value = 0;
}

function reset() {
  discard();
  uploadedMedia.value = null;
  emit("update", null);
}

defineExpose({ reset });

onBeforeUnmount(() => {
  disposed = true;
  captureRequestId += 1;
  if (mediaRecorder && recording.value) {
    mediaRecorder.ondataavailable = null;
    mediaRecorder.onstop = null;
    try {
      mediaRecorder.stop();
    } catch (_) { /* ignore */ }
  }
  recording.value = false;
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
  stopStream();
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value);
});
</script>

<style scoped>
.media-capture {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px dashed rgba(148, 163, 184, 0.5);
  border-radius: 12px;
  background: rgba(148, 163, 184, 0.06);
}
.mc-modes {
  display: flex;
  gap: 0.5rem;
}
.mc-mode-btn {
  flex: 1;
  padding: 0.4rem 0.75rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: transparent;
  cursor: pointer;
  font-size: 0.85rem;
}
.mc-mode-btn.active {
  background: var(--accent, #f472b6);
  color: #fff;
  border-color: transparent;
}
.mc-preview {
  width: 100%;
  max-height: 220px;
  border-radius: 10px;
  background: #000;
}
.mc-controls {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}
.mc-rec-btn,
.mc-stop-btn,
.mc-confirm,
.mc-discard {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
}
.mc-rec-btn {
  background: #ef4444;
  color: #fff;
}
.mc-stop-btn {
  background: #1e293b;
  color: #fff;
}
.mc-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #fff;
}
.mc-file-btn {
  font-size: 0.8rem;
  color: #64748b;
  cursor: pointer;
  text-decoration: underline;
}
.hidden-input {
  display: none;
}
.mc-player {
  width: 100%;
}
.mc-review-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.5rem;
}
.mc-confirm {
  background: #10b981;
  color: #fff;
}
.mc-discard {
  background: rgba(148, 163, 184, 0.25);
  color: #475569;
}
.mc-done {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.mc-done-label {
  font-size: 0.85rem;
  color: #0f766e;
  font-weight: 600;
}
.mc-error {
  margin: 0;
  font-size: 0.8rem;
  color: #ef4444;
}
</style>
