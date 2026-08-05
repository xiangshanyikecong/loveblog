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
  <div class="content-section admin-root">

    <!-- ── System Health ── -->
    <article class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t("admin.healthCheck") }}</h2>
        <div class="health-actions">
          <button
            class="ghost-btn"
            :disabled="remediateLoading"
            :title="t('admin.remediateTitle')"
            @click="onRemediateNow"
          >
            {{ remediateLoading ? t("admin.cleaning") : t("admin.cleanNow") }}
          </button>
          <button class="ghost-btn" :disabled="healthLoading" @click="loadSystemHealth">
            {{ healthLoading ? t("admin.checking") : t("admin.refresh") }}
          </button>
        </div>
      </div>

      <div v-if="systemHealth" class="health-layout">
        <!-- Health Score -->
        <div class="health-score-card">
          <div class="score-circle" :class="getScoreClass(systemHealth.health_score)">
            <div class="score-value">{{ systemHealth.health_score }}</div>
            <div class="score-label">{{ t("admin.healthScore") }}</div>
          </div>
          <div class="score-info">
            <div class="status-badge" :class="'status-' + systemHealth.overall_status">
              {{ getStatusText(systemHealth.overall_status) }}
            </div>
            <div class="uptime-text">
              {{ t("admin.uptime", { time: formatUptime(systemHealth.uptime_seconds) }) }}
            </div>
          </div>
        </div>

        <!-- Component Checks -->
        <div class="checks-grid">
          <div
            v-for="check in systemHealth.checks"
            :key="check.component"
            class="check-card"
            :class="'check-' + check.status"
          >
            <div class="check-header">
              <span class="check-icon">{{ getComponentIcon(check.component) }}</span>
              <span class="check-name">{{ getComponentName(check.component) }}</span>
              <span class="check-status-badge" :class="'badge-' + check.status">
                {{ getCheckStatusText(check.status) }}
              </span>
            </div>
            <div class="check-message">{{ check.message }}</div>
            <div v-if="check.response_time_ms" class="check-response-time">
              {{ t("admin.responseTime", { ms: check.response_time_ms.toFixed(0) }) }}
            </div>
          </div>
        </div>

        <!-- Recommendations -->
        <div v-if="systemHealth.recommendations && systemHealth.recommendations.length" class="recommendations-section">
          <h3 class="recommendations-title">{{ t("admin.recommendations") }}</h3>
          <ul class="recommendations-list">
            <li v-for="(rec, idx) in systemHealth.recommendations" :key="idx" class="recommendation-item">
              {{ rec }}
            </li>
          </ul>
        </div>

        <!-- History Trend (last 24h) -->
        <div v-if="healthHistory.length" class="health-trend">
          <div class="health-trend-head">
            <h3 class="recommendations-title">{{ t("admin.trend24h") }}</h3>
            <span class="health-trend-meta">{{ t("admin.samplePoints", { n: healthHistory.length }) }}</span>
          </div>
          <svg
            class="health-trend-chart"
            :viewBox="`0 0 ${trendPoints.width} ${trendPoints.height}`"
            preserveAspectRatio="none"
            role="img"
            :aria-label="t('admin.trendAriaLabel')"
          >
            <path :d="trendPoints.path" class="trend-line" />
            <circle
              v-for="(p, i) in trendPoints.points"
              :key="i"
              :cx="p.x"
              :cy="p.y"
              r="1.2"
              :class="'trend-dot status-' + p.status"
            />
          </svg>
          <div class="health-trend-legend">
            <span class="legend-item"><span class="legend-dot status-healthy"></span>{{ t("admin.statusHealthy") }}</span>
            <span class="legend-item"><span class="legend-dot status-degraded"></span>{{ t("admin.statusDegraded") }}</span>
            <span class="legend-item"><span class="legend-dot status-unhealthy"></span>{{ t("admin.statusUnhealthy") }}</span>
            <span v-if="healthHistory.some(h => h.remediated)" class="legend-item">
              <span class="legend-dot remediated"></span>{{ t("admin.autoCleaned") }}
            </span>
          </div>
        </div>

        <div v-if="remediateNote" class="remediation-note">{{ remediateNote }}</div>

        <div class="health-timestamp">
          {{ t("admin.lastCheck", { time: formatTimestamp(systemHealth.timestamp) }) }}
        </div>
      </div>
      <p v-else-if="!healthLoading" class="muted-tip">{{ t("admin.healthTip") }}</p>
    </article>

    <!-- ── Site Settings ── -->
    <article class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t("admin.siteSettings") }}</h2>
        <button class="ghost-btn" @click="loadSettings">{{ t("admin.refresh") }}</button>
      </div>

      <form class="form-grid" @submit.prevent="saveSettings">
        <label class="field-label col-1">
          {{ t("admin.siteName") }}
          <input v-model="settingsForm.site_name" class="input" :placeholder="t('admin.siteNamePlaceholder')" />
        </label>
        <label class="field-label col-1">
          {{ t("admin.loveStartDate") }}
          <input v-model="settingsForm.love_start_date" class="input" type="datetime-local" />
        </label>

        <!-- Couple Avatars Section -->
        <div class="col-2 couple-avatars-admin">
          <h3 class="subsection-title">{{ t("admin.coupleAvatarSettings") }}</h3>
          <div class="avatars-upload-grid">
            <div class="avatar-upload-card">
              <label class="avatar-upload-label">{{ t("admin.partnerAAvatar") }}</label>
              <div class="avatar-preview-wrapper">
                <img 
                  v-if="settingsForm.partner_a_avatar" 
                  :src="getAvatarUrl(settingsForm.partner_a_avatar)" 
                  alt="Partner A" 
                  class="avatar-preview"
                />
                <div v-else class="avatar-preview-placeholder">A</div>
              </div>
              <div class="avatar-upload-controls">
                <input 
                  ref="partnerAInput"
                  type="file"
                  accept="image/*" 
                  style="display: none"
                  @change="handleAvatarUpload($event, 'partner_a')"
                />
                <button 
                  type="button" 
                  class="btn-upload" 
                  :disabled="uploading"
                  @click="$refs.partnerAInput.click()"
                >
                  {{ uploading ? t("admin.uploading") : t("admin.selectImage") }}
                </button>
                <button 
                  v-if="settingsForm.partner_a_avatar"
                  type="button" 
                  class="btn-clear" 
                  :disabled="uploading"
                  @click="clearAvatar('partner_a')"
                >
                  {{ t("admin.clear") }}
                </button>
              </div>
              <div class="avatar-qq-row">
                <input
                  v-model="qqInputs.partner_a"
                  class="qq-input"
                  inputmode="numeric"
                  :placeholder="t('admin.qqPlaceholder')"
                  @keyup.enter="fetchQQAvatar('partner_a')"
                />
                <button
                  type="button"
                  class="btn-qq"
                  :disabled="qqLoading.partner_a"
                  @click="fetchQQAvatar('partner_a')"
                >
                  {{ qqLoading.partner_a ? t("admin.fetching") : t("admin.useQqAvatar") }}
                </button>
              </div>
            </div>

            <div class="avatar-upload-card">
              <label class="avatar-upload-label">{{ t("admin.partnerBAvatar") }}</label>
              <div class="avatar-preview-wrapper">
                <img 
                  v-if="settingsForm.partner_b_avatar" 
                  :src="getAvatarUrl(settingsForm.partner_b_avatar)" 
                  alt="Partner B" 
                  class="avatar-preview"
                />
                <div v-else class="avatar-preview-placeholder">B</div>
              </div>
              <div class="avatar-upload-controls">
                <input 
                  ref="partnerBInput"
                  type="file"
                  accept="image/*" 
                  style="display: none"
                  @change="handleAvatarUpload($event, 'partner_b')"
                />
                <button 
                  type="button" 
                  class="btn-upload" 
                  :disabled="uploading"
                  @click="$refs.partnerBInput.click()"
                >
                  {{ uploading ? t("admin.uploading") : t("admin.selectImage") }}
                </button>
                <button 
                  v-if="settingsForm.partner_b_avatar"
                  type="button" 
                  class="btn-clear" 
                  :disabled="uploading"
                  @click="clearAvatar('partner_b')"
                >
                  {{ t("admin.clear") }}
                </button>
              </div>
              <div class="avatar-qq-row">
                <input
                  v-model="qqInputs.partner_b"
                  class="qq-input"
                  inputmode="numeric"
                  :placeholder="t('admin.qqPlaceholder')"
                  @keyup.enter="fetchQQAvatar('partner_b')"
                />
                <button
                  type="button"
                  class="btn-qq"
                  :disabled="qqLoading.partner_b"
                  @click="fetchQQAvatar('partner_b')"
                >
                  {{ qqLoading.partner_b ? t("admin.fetching") : t("admin.useQqAvatar") }}
                </button>
              </div>
            </div>
          </div>
          <p class="avatar-hint">{{ t("admin.avatarHint") }}</p>
        </div>

        <label class="field-label col-2">
          {{ t("admin.uploadsRoot") }}
          <input v-model="settingsForm.uploads_root" class="input" :placeholder="t('admin.uploadsRootPlaceholder')" />
        </label>
        <label class="field-label col-1">
          {{ t("admin.articlesPath") }}
          <input v-model="settingsForm.articles_path" class="input" />
        </label>
        <label class="field-label col-1">
          {{ t("admin.albumsPath") }}
          <input v-model="settingsForm.albums_path" class="input" />
        </label>
        <label class="field-label col-1">
          {{ t("admin.avatarPath") }}
          <input v-model="settingsForm.avatar_path" class="input" />
        </label>
        <label class="field-label col-1">
          {{ t("admin.timelinePath") }}
          <input v-model="settingsForm.timeline_path" class="input" />
        </label>
        <label class="field-label col-2">
          {{ t("admin.videosPath") }}
          <input v-model="settingsForm.videos_path" class="input" />
        </label>
        <button class="btn-secondary col-2" :disabled="busy">
          {{ busy ? t("admin.saving") : t("admin.saveSiteSettings") }}
        </button>
      </form>
    </article>

    <!-- ── Media Policy ── -->
    <article class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t("admin.mediaPolicy") }}</h2>
        <span class="section-hint">{{ t("admin.mediaPolicyHint") }}</span>
      </div>

      <div class="policy-grid">
        <!-- Max image size -->
        <div class="policy-card">
          <div class="policy-icon">📏</div>
          <div class="policy-body">
            <p class="policy-title">{{ t("admin.maxImageSize") }}</p>
            <p class="policy-desc">{{ t("admin.maxImageSizeDesc") }}</p>
            <div class="policy-control">
              <input
                v-model.number="settingsForm.max_image_kb"
                class="input input-sm"
                type="number"
                min="0" max="102400"
                placeholder="1024"
              />
              <span class="unit">KB</span>
            </div>
          </div>
        </div>

        <!-- Compress quality -->
        <div class="policy-card">
          <div class="policy-icon">🗜</div>
          <div class="policy-body">
            <p class="policy-title">{{ t("admin.compressQuality") }}</p>
            <p class="policy-desc">{{ t("admin.compressQualityDesc") }}</p>
            <div class="policy-control">
              <input
                v-model.number="settingsForm.compress_quality"
                class="input input-sm"
                type="number"
                min="1" max="95"
              />
              <span class="unit">/ 95</span>
              <div class="quality-bar">
                <div class="quality-fill" :style="{ width: (settingsForm.compress_quality / 95 * 100) + '%' }" />
              </div>
            </div>
          </div>
        </div>

        <!-- Thumbnail width -->
        <div class="policy-card">
          <div class="policy-icon">🖼</div>
          <div class="policy-body">
            <p class="policy-title">{{ t("admin.thumbWidth") }}</p>
            <p class="policy-desc">{{ t("admin.thumbWidthDesc") }}</p>
            <div class="policy-control">
              <input
                v-model.number="settingsForm.thumb_width"
                class="input input-sm"
                type="number"
                min="0" max="4096"
                placeholder="400"
              />
              <span class="unit">px</span>
            </div>
          </div>
        </div>

        <!-- Strip EXIF -->
        <div class="policy-card">
          <div class="policy-icon">🔒</div>
          <div class="policy-body">
            <p class="policy-title">{{ t("admin.stripExif") }}</p>
            <p class="policy-desc">{{ t("admin.stripExifDesc") }}</p>
            <label class="toggle">
              <input v-model="settingsForm.strip_exif" type="checkbox" />
              <span class="toggle-track">
                <span class="toggle-thumb" />
              </span>
              <span class="toggle-label">{{ settingsForm.strip_exif ? t("admin.enabled") : t("admin.disabled") }}</span>
            </label>
          </div>
        </div>

        <!-- Allowed types -->
        <div class="policy-card policy-card--wide">
          <div class="policy-icon">✅</div>
          <div class="policy-body">
            <p class="policy-title">{{ t("admin.imageTypeWhitelist") }}</p>
            <p class="policy-desc">{{ t("admin.imageTypeWhitelistDesc") }}</p>
            <div class="type-toggles">
              <label
                v-for="mime in allMimeTypes"
                :key="mime"
                class="type-chip"
                :class="{ 'type-chip--on': allowedSet.has(mime) }"
              >
                <input
                  type="checkbox"
                  style="display:none"
                  :checked="allowedSet.has(mime)"
                  @change="toggleMime(mime)"
                />
                {{ mimeLabel[mime] || mime }}
              </label>
            </div>
          </div>
        </div>
      </div>

      <button class="btn-secondary mt-1" :disabled="busy" @click="saveMediaPolicy">
        {{ busy ? t("admin.saving") : t("admin.saveMediaPolicy") }}
      </button>
    </article>

    <!-- ── Storage Stats ── -->
    <article class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t("admin.storage") }}</h2>
        <button class="ghost-btn" :disabled="statsLoading" @click="loadStats">
          {{ statsLoading ? t("admin.counting") : t("admin.refreshStats") }}
        </button>
      </div>

      <div v-if="stats" class="stats-layout">
        <div class="stats-total">
          <span class="stats-total-val">{{ fmtBytes(stats.total_bytes) }}</span>
          <span class="stats-total-label">{{ t("admin.totalFiles", { n: stats.total_files }) }}</span>
        </div>
        <div class="dir-bars">
          <div
            v-for="(info, name) in stats.directories"
            :key="name"
            class="dir-row"
          >
            <span class="dir-name">{{ dirLabel[name] || name }}</span>
            <div class="bar-wrap">
              <div
                class="bar-fill"
                :style="{ width: barPct(info.bytes) + '%', background: dirColor(name) }"
              />
            </div>
            <span class="dir-size">{{ fmtBytes(info.bytes) }}</span>
            <span class="dir-count">{{ t("admin.fileCount", { n: info.files }) }}</span>
          </div>
        </div>
      </div>
      <p v-else-if="!statsLoading" class="muted-tip">{{ t("admin.statsTip") }}</p>
    </article>

  </div>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue";
import { fetchAvatarFromQQ, fetchHealthHistory, fetchSettings, fetchStorageStats, fetchSystemHealth, remediateHealthNow, resolveAssetUrl, updateSettings, uploadFile } from "../lib/api";
import { confirmDialog } from "../lib/dialog";
import { t } from "../locales";
import { parseError } from "../utils/helpers";

const showMessage = inject("showMessage");
const busy = ref(false);
const statsLoading = ref(false);
const stats = ref(null);
const uploading = ref(false);
const healthLoading = ref(false);
const systemHealth = ref(null);
const healthHistory = ref([]);
const remediateLoading = ref(false);
const remediateNote = ref("");

// Refs for file inputs
const partnerAInput = ref(null);
const partnerBInput = ref(null);

// QQ-avatar fetch state (per partner)
const qqInputs = reactive({ partner_a: "", partner_b: "" });
const qqLoading = reactive({ partner_a: false, partner_b: false });

// ── All known MIME types ──────────────────────────────────────────────────
const allMimeTypes = ["image/jpeg", "image/png", "image/webp", "image/gif"];
const mimeLabel = {
  "image/jpeg": "JPEG",
  "image/png":  "PNG",
  "image/webp": "WebP",
  "image/gif":  "GIF",
};

// ── Settings form ─────────────────────────────────────────────────────────
const DEFAULT_SETTINGS = {
  site_name: "恋爱记",
  love_start_date: "",
  uploads_root: "uploads",
  articles_path: "uploads/articles",
  albums_path: "uploads/albums",
  avatar_path: "uploads/avatars",
  timeline_path: "uploads/timeline",
  videos_path: "uploads/videos",
  allow_registration: false,
  partner_a_avatar: null,
  partner_b_avatar: null,
  max_image_kb: 1024,
  thumb_width: 400,
  compress_quality: 82,
  strip_exif: true,
  allowed_image_types: "image/jpeg,image/png,image/webp,image/gif",
};

const settingsForm = reactive({ ...DEFAULT_SETTINGS });

// Derived set from comma-string for checkboxes
const allowedSet = computed(() => {
  const types = (settingsForm.allowed_image_types || "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  return new Set(types);
});

function toggleMime(mime) {
  const current = new Set(allowedSet.value);
  if (current.has(mime)) {
    if (current.size <= 1) {
      showMessage?.(t("admin.errKeepOneType"));
      return;
    }
    current.delete(mime);
  } else {
    current.add(mime);
  }
  settingsForm.allowed_image_types = [...current].join(",");
}

// ── Date helpers ─────────────────────────────────────────────────────────
function toDatetimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function toBackendIso(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error(t("admin.errLoveDateFormat"));
  return date.toISOString();
}

// ── Load / Save ──────────────────────────────────────────────────────────
function getAvatarUrl(path) {
  return resolveAssetUrl(path);
}

async function handleAvatarUpload(event, partner) {
  const file = event.target.files?.[0];
  if (!file) return;

  // Validate file type
  if (!file.type.startsWith("image/")) {
    showMessage?.(t("admin.errSelectImage"));
    return;
  }

  // Validate file size (max 5MB)
  if (file.size > 5 * 1024 * 1024) {
    showMessage?.(t("admin.errImageTooLarge"));
    return;
  }

  uploading.value = true;
  try {
    const result = await uploadFile(file, "avatars");
    const avatarPath = result.url; // Backend returns 'url' field
    
    if (partner === "partner_a") {
      settingsForm.partner_a_avatar = avatarPath;
    } else {
      settingsForm.partner_b_avatar = avatarPath;
    }
    
    // Auto-save after upload
    await updateSettings({
      partner_a_avatar: settingsForm.partner_a_avatar,
      partner_b_avatar: settingsForm.partner_b_avatar,
    });
    
    showMessage?.(t("admin.avatarUpdated", { name: partner === "partner_a" ? t("adminAccounts.partnerA") : t("adminAccounts.partnerB") }));
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    uploading.value = false;
    // Clear file input
    if (event.target) {
      event.target.value = "";
    }
  }
}

async function fetchQQAvatar(partner) {
  const qq = String(qqInputs[partner] ?? "").trim();
  if (!/^\d{5,12}$/.test(qq)) {
    showMessage?.(t("admin.errQqInvalid"));
    return;
  }

  qqLoading[partner] = true;
  try {
    const result = await fetchAvatarFromQQ(qq);
    const avatarPath = result.url;

    if (partner === "partner_a") {
      settingsForm.partner_a_avatar = avatarPath;
    } else {
      settingsForm.partner_b_avatar = avatarPath;
    }

    await updateSettings({
      partner_a_avatar: settingsForm.partner_a_avatar,
      partner_b_avatar: settingsForm.partner_b_avatar,
    });

    qqInputs[partner] = "";
    showMessage?.(t("admin.qqAvatarApplied", { name: partner === "partner_a" ? t("adminAccounts.partnerA") : t("adminAccounts.partnerB") }));
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    qqLoading[partner] = false;
  }
}

async function clearAvatar(partner) {
  if (!(await confirmDialog(t("admin.confirmClearAvatar", { name: partner === "partner_a" ? t("adminAccounts.partnerA") : t("adminAccounts.partnerB") }), { danger: true }))) {
    return;
  }

  busy.value = true;
  try {
    if (partner === "partner_a") {
      settingsForm.partner_a_avatar = null;
      await updateSettings({ partner_a_avatar: null });
    } else {
      settingsForm.partner_b_avatar = null;
      await updateSettings({ partner_b_avatar: null });
    }
    showMessage?.(t("admin.avatarCleared"));
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function loadSettings() {
  try {
    const data = await fetchSettings();
    settingsForm.site_name         = data.site_name ?? DEFAULT_SETTINGS.site_name;
    settingsForm.love_start_date   = toDatetimeLocal(data.love_start_date);
    settingsForm.uploads_root      = data.uploads_root ?? DEFAULT_SETTINGS.uploads_root;
    settingsForm.articles_path     = data.articles_path ?? DEFAULT_SETTINGS.articles_path;
    settingsForm.albums_path       = data.albums_path ?? DEFAULT_SETTINGS.albums_path;
    settingsForm.avatar_path       = data.avatar_path ?? DEFAULT_SETTINGS.avatar_path;
    settingsForm.timeline_path     = data.timeline_path ?? DEFAULT_SETTINGS.timeline_path;
    settingsForm.videos_path       = data.videos_path ?? DEFAULT_SETTINGS.videos_path;
    settingsForm.allow_registration = Boolean(data.allow_registration);
    settingsForm.partner_a_avatar  = data.partner_a_avatar ?? null;
    settingsForm.partner_b_avatar  = data.partner_b_avatar ?? null;
    settingsForm.max_image_kb      = data.max_image_kb ?? DEFAULT_SETTINGS.max_image_kb;
    settingsForm.thumb_width       = data.thumb_width ?? DEFAULT_SETTINGS.thumb_width;
    settingsForm.compress_quality  = data.compress_quality ?? DEFAULT_SETTINGS.compress_quality;
    settingsForm.strip_exif        = Boolean(data.strip_exif ?? DEFAULT_SETTINGS.strip_exif);
    settingsForm.allowed_image_types = data.allowed_image_types ?? DEFAULT_SETTINGS.allowed_image_types;
  } catch (error) {
    showMessage?.(parseError(error));
  }
}

async function saveSettings() {
  busy.value = true;
  try {
    await updateSettings({
      site_name: String(settingsForm.site_name ?? "").trim(),
      love_start_date: toBackendIso(settingsForm.love_start_date),
      uploads_root: String(settingsForm.uploads_root ?? "").trim(),
      articles_path: String(settingsForm.articles_path ?? "").trim(),
      albums_path: String(settingsForm.albums_path ?? "").trim(),
      avatar_path: String(settingsForm.avatar_path ?? "").trim(),
      timeline_path: String(settingsForm.timeline_path ?? "").trim(),
      videos_path: String(settingsForm.videos_path ?? "").trim(),
      allow_registration: Boolean(settingsForm.allow_registration),
    });
    showMessage?.(t("admin.siteSettingsSaved"));
    await loadSettings();
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function saveMediaPolicy() {
  busy.value = true;
  try {
    await updateSettings({
      max_image_kb: Number(settingsForm.max_image_kb),
      thumb_width: Number(settingsForm.thumb_width),
      compress_quality: Number(settingsForm.compress_quality),
      strip_exif: Boolean(settingsForm.strip_exif),
      allowed_image_types: settingsForm.allowed_image_types,
    });
    showMessage?.(t("admin.mediaPolicySaved"));
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    busy.value = false;
  }
}

// ── Storage stats ─────────────────────────────────────────────────────────
const dirLabel = {
  albums:   t("admin.dirAlbums"),
  articles: t("admin.dirArticles"),
  avatars:  t("admin.dirAvatars"),
  timeline: t("admin.dirTimeline"),
  videos:   t("admin.dirVideos"),
};

const DIR_COLORS = ["#8f9bff", "#ff8ab5", "#59c7b9", "#f9a875", "#a78bfa", "#fb7185"];
function dirColor(name) {
  const names = Object.keys(stats.value?.directories || {});
  const idx = names.indexOf(name) % DIR_COLORS.length;
  return DIR_COLORS[idx];
}

function barPct(bytes) {
  const max = Math.max(...Object.values(stats.value?.directories || {}).map((d) => d.bytes), 1);
  return Math.round((bytes / max) * 100);
}

function fmtBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(1)} ${units[i]}`;
}

async function loadStats() {
  statsLoading.value = true;
  try {
    stats.value = await fetchStorageStats();
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    statsLoading.value = false;
  }
}

// ── System Health ─────────────────────────────────────────────────────────
async function loadSystemHealth() {
  healthLoading.value = true;
  remediateNote.value = "";
  try {
    const [health, history] = await Promise.all([
      fetchSystemHealth(),
      fetchHealthHistory({ hours: 24, limit: 48 }).catch(() => ({ items: [], total: 0 }))
    ]);
    systemHealth.value = health;
    healthHistory.value = history.items || [];
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    healthLoading.value = false;
  }
}

async function onRemediateNow() {
  remediateLoading.value = true;
  remediateNote.value = "";
  try {
    const result = await remediateHealthNow();
    if (result?.snapshot) systemHealth.value = result.snapshot;
    if (result?.note) {
      remediateNote.value = result.note;
      showMessage?.(result.note);
    } else {
      showMessage?.(t("admin.systemHealthy"));
    }
    // Refresh history so the new snapshot shows up in the trend.
    const history = await fetchHealthHistory({ hours: 24, limit: 48 }).catch(() => null);
    if (history) healthHistory.value = history.items || [];
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    remediateLoading.value = false;
  }
}

// Sparkline geometry for the score trend. Returns SVG path data + point coords.
const trendPoints = computed(() => {
  const items = healthHistory.value;
  if (!items.length) return { path: "", points: [], width: 0, height: 0 };
  const width = 100;
  const height = 32;
  const n = items.length;
  const step = n > 1 ? width / (n - 1) : 0;
  const coords = items.map((item, i) => ({
    x: i * step,
    y: height - (Math.max(0, Math.min(100, item.health_score)) / 100) * height,
    status: item.overall_status,
    score: item.health_score,
    remediated: item.remediated
  }));
  const path = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ");
  return { path, points: coords, width, height };
});

function getScoreClass(score) {
  if (score >= 90) return "score-excellent";
  if (score >= 70) return "score-good";
  if (score >= 50) return "score-warning";
  return "score-critical";
}

function getStatusText(status) {
  const statusMap = {
    healthy: t("admin.statusHealthy"),
    degraded: t("admin.statusDegraded"),
    unhealthy: t("admin.statusUnhealthy")
  };
  return statusMap[status] || status;
}

function getCheckStatusText(status) {
  const statusMap = {
    ok: t("admin.checkOk"),
    warning: t("admin.checkWarning"),
    error: t("admin.checkError")
  };
  return statusMap[status] || status;
}

function getComponentIcon(component) {
  const iconMap = {
    database: "🗄️",
    redis: "⚡",
    disk_space: "💾",
    memory: "🧠",
    cpu: "⚙️",
    uploads_directory: "📁"
  };
  return iconMap[component] || "📊";
}

function getComponentName(component) {
  const nameMap = {
    database: t("admin.componentDatabase"),
    redis: t("admin.componentRedis"),
    disk_space: t("admin.componentDiskSpace"),
    memory: t("admin.componentMemory"),
    cpu: t("admin.componentCpu"),
    uploads_directory: t("admin.componentUploadsDir")
  };
  return nameMap[component] || component;
}

function formatUptime(seconds) {
  if (!seconds) return t("admin.uptimeUnknown");

  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) return t("admin.uptimeDays", { days, hours });
  if (hours > 0) return t("admin.uptimeHours", { hours, minutes });
  return t("admin.uptimeMinutes", { minutes });
}

function formatTimestamp(timestamp) {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

onMounted(() => {
  loadSettings();
  loadStats();
  loadSystemHealth();
});
</script>

<style scoped>
.admin-root { display: grid; gap: 1.5rem; }

.section-hint {
  font-size: 0.75rem;
  color: #94a3b8;
}

/* Form grid */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
.field-label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.78rem;
  color: #475569;
  font-weight: 600;
}
.col-1 { grid-column: span 1; }
.col-2 { grid-column: span 2; }

/* Policy grid */
.policy-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.85rem;
  margin-bottom: 1rem;
}
.policy-card {
  display: flex;
  gap: 0.75rem;
  background: rgb(248 250 255 / 0.85);
  border: 1px solid rgb(148 163 184 / 0.28);
  border-radius: 14px;
  padding: 1rem;
  align-items: flex-start;
  transition: box-shadow 0.18s;
}
.policy-card:hover { box-shadow: 0 4px 18px rgb(143 155 255 / 0.15); }
.policy-card--wide { grid-column: span 2; }
.policy-icon { font-size: 1.5rem; flex-shrink: 0; line-height: 1; }
.policy-body { display: grid; gap: 0.25rem; flex: 1; }
.policy-title { margin: 0; font-size: 0.88rem; font-weight: 700; color: #1e293b; }
.policy-desc  { margin: 0; font-size: 0.76rem; color: #64748b; line-height: 1.5; }

.policy-control {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.4rem;
}
.input-sm { width: 90px; padding: 0.35rem 0.6rem; font-size: 0.85rem; }
.unit { font-size: 0.78rem; color: #64748b; }

/* Quality bar */
.quality-bar {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: rgb(148 163 184 / 0.25);
  overflow: hidden;
}
.quality-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #8f9bff, #ff8ab5);
  transition: width 0.3s ease;
}

/* Toggle switch */
.toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  margin-top: 0.4rem;
  cursor: pointer;
}
.toggle input { display: none; }
.toggle-track {
  width: 38px;
  height: 22px;
  border-radius: 999px;
  background: #cbd5e1;
  position: relative;
  transition: background 0.2s;
}
.toggle input:checked ~ .toggle-track { background: linear-gradient(120deg, #8f9bff, #ff8ab5); }
.toggle-thumb {
  position: absolute;
  top: 3px; left: 3px;
  width: 16px; height: 16px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 4px rgb(0 0 0 / 0.2);
  transition: transform 0.2s;
}
.toggle input:checked ~ .toggle-track .toggle-thumb { transform: translateX(16px); }
.toggle-label { font-size: 0.8rem; color: #475569; font-weight: 600; }

/* Type chips */
.type-toggles { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }
.type-chip {
  padding: 0.3rem 0.85rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  border: 1px solid rgb(148 163 184 / 0.4);
  background: rgb(248 250 255 / 0.9);
  color: #64748b;
  cursor: pointer;
  transition: background 0.18s, color 0.18s, border-color 0.18s;
  user-select: none;
}
.type-chip--on {
  background: linear-gradient(120deg, #8f9bff33, #ff8ab533);
  border-color: #8f9bff;
  color: #4f5ecf;
}

/* Storage stats */
.stats-layout { display: grid; gap: 1rem; }
.stats-total {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
}
.stats-total-val { font-size: 1.8rem; font-weight: 800; color: #1e293b; }
.stats-total-label { font-size: 0.82rem; color: #64748b; }

.dir-bars { display: grid; gap: 0.55rem; }
.dir-row {
  display: grid;
  grid-template-columns: 90px 1fr 80px 70px;
  align-items: center;
  gap: 0.6rem;
}
.dir-name { font-size: 0.8rem; font-weight: 600; color: #334155; }
.bar-wrap { height: 8px; border-radius: 999px; background: rgb(148 163 184 / 0.2); overflow: hidden; }
.bar-fill { height: 100%; border-radius: 999px; transition: width 0.4s ease; }
.dir-size  { font-size: 0.78rem; color: #475569; text-align: right; }
.dir-count { font-size: 0.72rem; color: #94a3b8; }

.mt-1 { margin-top: 0.25rem; }
.muted-tip { color: #94a3b8; font-size: 0.85rem; margin: 0; }

/* System Health Section */
.health-layout {
  display: grid;
  gap: 1.5rem;
}

.health-score-card {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 1.5rem;
  background: linear-gradient(135deg, rgba(143, 155, 255, 0.08), rgba(255, 138, 181, 0.08));
  border-radius: 16px;
  border: 1px solid rgba(143, 155, 255, 0.2);
}

.score-circle {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.score-circle::before {
  content: "";
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  padding: 4px;
  background: linear-gradient(135deg, currentColor, transparent);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
}

.score-excellent {
  background: linear-gradient(135deg, #10b981, #059669);
  color: #10b981;
}

.score-good {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #3b82f6;
}

.score-warning {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: #f59e0b;
}

.score-critical {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: #ef4444;
}

.score-value {
  font-size: 3rem;
  font-weight: 800;
  color: white;
  line-height: 1;
}

.score-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  margin-top: 0.25rem;
}

.score-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.5rem 1rem;
  border-radius: 999px;
  font-size: 0.9rem;
  font-weight: 700;
  width: fit-content;
}

.status-healthy {
  background: linear-gradient(135deg, #d1fae5, #a7f3d0);
  color: #065f46;
}

.status-degraded {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #92400e;
}

.status-unhealthy {
  background: linear-gradient(135deg, #fee2e2, #fecaca);
  color: #991b1b;
}

.uptime-text {
  font-size: 0.85rem;
  color: #64748b;
  font-weight: 600;
}

.checks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
}

.check-card {
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid;
  background: white;
  transition: transform 0.2s, box-shadow 0.2s;
}

.check-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
}

.check-ok {
  border-color: #86efac;
  background: linear-gradient(135deg, rgba(134, 239, 172, 0.1), rgba(167, 243, 208, 0.05));
}

.check-warning {
  border-color: #fcd34d;
  background: linear-gradient(135deg, rgba(252, 211, 77, 0.1), rgba(253, 230, 138, 0.05));
}

.check-error {
  border-color: #fca5a5;
  background: linear-gradient(135deg, rgba(252, 165, 165, 0.1), rgba(254, 202, 202, 0.05));
}

.check-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.check-icon {
  font-size: 1.25rem;
}

.check-name {
  flex: 1;
  font-size: 0.85rem;
  font-weight: 700;
  color: #1e293b;
}

.check-status-badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
}

.badge-ok {
  background: #d1fae5;
  color: #065f46;
}

.badge-warning {
  background: #fef3c7;
  color: #92400e;
}

.badge-error {
  background: #fee2e2;
  color: #991b1b;
}

.check-message {
  font-size: 0.8rem;
  color: #475569;
  line-height: 1.5;
  margin-bottom: 0.25rem;
}

.check-response-time {
  font-size: 0.7rem;
  color: #94a3b8;
  font-weight: 600;
}

.recommendations-section {
  padding: 1.25rem;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.05), rgba(147, 197, 253, 0.05));
  border-radius: 12px;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.recommendations-title {
  margin: 0 0 0.75rem 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: #1e293b;
}

.recommendations-list {
  margin: 0;
  padding-left: 1.25rem;
  display: grid;
  gap: 0.5rem;
}

.recommendation-item {
  font-size: 0.82rem;
  color: #475569;
  line-height: 1.6;
}

.health-timestamp {
  text-align: center;
  font-size: 0.75rem;
  color: #94a3b8;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(148, 163, 184, 0.2);
}

.health-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.health-trend {
  padding: 1rem 1.25rem;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(168, 85, 247, 0.05));
  border-radius: 12px;
  border: 1px solid rgba(99, 102, 241, 0.18);
  display: grid;
  gap: 0.55rem;
}
.health-trend-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.health-trend-head .recommendations-title { margin: 0; }
.health-trend-meta {
  font-size: 0.72rem;
  color: var(--text-soft);
}
.health-trend-chart {
  width: 100%;
  height: 64px;
  background: rgba(255, 255, 255, 0.55);
  border-radius: 8px;
}
.trend-line {
  fill: none;
  stroke: #6366f1;
  stroke-width: 1.2;
  stroke-linejoin: round;
  stroke-linecap: round;
}
.trend-dot.status-healthy { fill: #16a34a; }
.trend-dot.status-degraded { fill: #f59e0b; }
.trend-dot.status-unhealthy { fill: #dc2626; }
.health-trend-legend {
  display: flex;
  gap: 0.85rem;
  flex-wrap: wrap;
  font-size: 0.74rem;
  color: var(--text-soft);
}
.legend-item { display: inline-flex; align-items: center; gap: 0.35rem; }
.legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
}
.legend-dot.status-healthy { background: #16a34a; }
.legend-dot.status-degraded { background: #f59e0b; }
.legend-dot.status-unhealthy { background: #dc2626; }
.legend-dot.remediated {
  background: transparent;
  border: 2px solid #6366f1;
  width: 9px;
  height: 9px;
}

.remediation-note {
  margin: 0;
  padding: 0.55rem 0.85rem;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px dashed rgba(99, 102, 241, 0.3);
  color: #4338ca;
  font-size: 0.82rem;
}

/* Couple Avatars Admin Section */
.couple-avatars-admin {
  background: linear-gradient(135deg, rgba(255, 182, 193, 0.08), rgba(173, 216, 230, 0.08));
  border: 1px solid rgba(255, 138, 181, 0.2);
  border-radius: 14px;
  padding: 1.5rem;
  margin-bottom: 0.75rem;
}

.subsection-title {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  font-weight: 700;
  color: #1e293b;
}

.avatars-upload-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

.avatar-upload-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  align-items: center;
}

.avatar-upload-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #475569;
}

.avatar-preview-wrapper {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  overflow: hidden;
  border: 3px solid #fff;
  box-shadow: 0 4px 12px rgba(143, 155, 255, 0.2);
}

.avatar-preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-preview-placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #8f9bff, #ff8ab5);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.5rem;
  font-weight: 800;
  color: white;
}

.avatar-upload-controls {
  display: flex;
  gap: 0.5rem;
}

.btn-upload,
.btn-clear {
  padding: 0.4rem 1rem;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-upload {
  background: linear-gradient(120deg, #8f9bff, #ff8ab5);
  color: white;
}

.btn-upload:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(143, 155, 255, 0.3);
}

.btn-upload:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-clear {
  background: #f1f5f9;
  color: #64748b;
  border: 1px solid #cbd5e1;
}

.btn-clear:hover:not(:disabled) {
  background: #fee2e2;
  color: #dc2626;
  border-color: #fca5a5;
}

.btn-clear:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.avatar-qq-row {
  display: flex;
  gap: 0.4rem;
  width: 100%;
  max-width: 240px;
}

.qq-input {
  flex: 1;
  min-width: 0;
  padding: 0.4rem 0.65rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font-size: 0.8rem;
  background: #fff;
  color: #1e293b;
}

.qq-input:focus {
  outline: none;
  border-color: #8f9bff;
  box-shadow: 0 0 0 2px rgba(143, 155, 255, 0.2);
}

.btn-qq {
  flex-shrink: 0;
  padding: 0.4rem 0.8rem;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 600;
  border: 1px solid #12b886;
  background: #e6fcf5;
  color: #0ca678;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-qq:hover:not(:disabled) {
  background: #0ca678;
  color: #fff;
}

.btn-qq:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.avatar-hint {
  margin: 1rem 0 0;
  font-size: 0.78rem;
  color: #94a3b8;
  text-align: center;
}

@media (max-width: 640px) {
  .form-grid { grid-template-columns: 1fr; }
  .col-2 { grid-column: span 1; }
  .policy-grid { grid-template-columns: 1fr; }
  .policy-card--wide { grid-column: span 1; }
  .dir-row { grid-template-columns: 70px 1fr 70px; }
  .dir-count { display: none; }
  .avatars-upload-grid { grid-template-columns: 1fr; }
  .avatar-preview-wrapper {
    width: 100px;
    height: 100px;
  }
  .avatar-preview-placeholder {
    font-size: 2rem;
  }
}
</style>
