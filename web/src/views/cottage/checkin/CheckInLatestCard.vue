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
  <article class="glass-card section-block checkin-card">
    <p v-if="loading" class="checkin-empty">{{ t('checkInLatestCard.loading') }}</p>

    <template v-else-if="!item">
      <p class="checkin-empty">{{ t('checkInLatestCard.partnerEmpty') }}</p>
    </template>

    <template v-else>
      <header class="checkin-meta">
        <span class="checkin-author">{{ item.author_nickname }}</span>
        <span class="checkin-time">{{ relativeTime(item.created_at) }}</span>
      </header>

      <p v-if="item.content" class="checkin-content">{{ item.content }}</p>

      <div v-if="item.media_urls && item.media_urls.length" class="checkin-media">
        <a
          v-for="url in item.media_urls"
          :key="url"
          :href="resolveAssetUrl(url)"
          target="_blank"
          rel="noopener noreferrer"
          class="checkin-media-tile"
        >
          <img :src="resolveAssetUrl(url)" alt="" loading="lazy" />
        </a>
      </div>

      <p v-if="locationLine" class="checkin-location">
        <span class="checkin-location-icon">📍</span>
        <span class="checkin-location-text">{{ locationLine }}</span>
        <span v-if="showNominatimHint" class="checkin-location-hint">
          {{ t('checkInLatestCard.nominatimHint') }}
        </span>
      </p>

      <p v-else-if="item.location_status === 'permission_denied'" class="checkin-location-state">
        {{ t('checkInLatestCard.permissionDenied') }}
      </p>
      <p v-else-if="item.location_status === 'lookup_failed'" class="checkin-location-state">
        {{ t('checkInLatestCard.lookupFailed') }}
      </p>
      <!-- omitted: render no location row at all -->
    </template>
  </article>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { resolveAssetUrl } from "../../../lib/api";

const { t } = useI18n();

const props = defineProps({
  item: { type: Object, default: null },
  loading: { type: Boolean, default: false }
});

const locationLine = computed(() => {
  if (!props.item) return "";
  if (props.item.location_status !== "resolved") return "";
  return props.item.location_text || "";
});

const showNominatimHint = computed(() => {
  return (
    props.item &&
    props.item.location_status === "resolved" &&
    props.item.location_provider === "nominatim"
  );
});

function relativeTime(iso) {
  if (!iso) return "";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return "";
  const diffSec = Math.floor((Date.now() - ts) / 1000);
  if (diffSec < 60) return t('checkInLatestCard.justNow');
  if (diffSec < 3600) return t('checkInLatestCard.minutesAgo', { n: Math.floor(diffSec / 60) });
  if (diffSec < 86400) return t('checkInLatestCard.hoursAgo', { n: Math.floor(diffSec / 3600) });
  if (diffSec < 86400 * 7) return t('checkInLatestCard.daysAgo', { n: Math.floor(diffSec / 86400) });
  return new Date(iso).toLocaleString();
}
</script>

<style scoped>
.checkin-card {
  padding: 1.2rem 1.4rem;
  display: grid;
  gap: 0.7rem;
}

.checkin-empty {
  margin: 0;
  text-align: center;
  color: #94a3b8;
  font-size: 0.92rem;
  padding: 0.6rem 0;
}

.checkin-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}

.checkin-author {
  font-size: 0.95rem;
  font-weight: 600;
  color: #2f3754;
}

.checkin-time {
  font-size: 0.78rem;
  color: #94a3b8;
}

.checkin-content {
  margin: 0;
  font-size: 0.94rem;
  line-height: 1.65;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
}

.checkin-media {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 0.45rem;
}

.checkin-media-tile {
  display: block;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.16);
}

.checkin-media-tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.checkin-location {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.86rem;
  color: #475569;
}

.checkin-location-icon {
  font-size: 0.95rem;
}

.checkin-location-text {
  color: #334155;
}

.checkin-location-hint {
  color: #94a3b8;
  font-size: 0.76rem;
}

.checkin-location-state {
  margin: 0;
  font-size: 0.84rem;
  color: #94a3b8;
  font-style: italic;
}

@media (max-width: 768px) {
  .checkin-media {
    grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  }
}
</style>
