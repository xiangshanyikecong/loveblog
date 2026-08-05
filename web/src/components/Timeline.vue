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
  <section class="timeline-wrap">
    <div class="timeline-head">
      <h2>{{ t("timeline.title") }}</h2>
      <button class="head-btn" @click="$emit('refresh')">{{ t("timeline.refresh") }}</button>
    </div>

    <p class="meta">{{ t("timeline.meta", { total, page }) }}</p>

    <div v-if="loading" class="state-box">{{ t("timeline.loading") }}</div>
    <div v-else-if="items.length === 0" class="state-box">{{ t("timeline.empty") }}</div>

    <ul v-else class="timeline-list">
      <li v-for="item in items" :key="item.mid" class="timeline-item">
        <div class="item-head">
          <span class="author">{{ item.author_nickname }}</span>
          <span class="time">{{ formatTime(item.timestamp) }}</span>
        </div>
        <p class="content">{{ item.content }}</p>
        <p v-if="item.location" class="location">{{ t("timeline.location") }}{{ item.location }}</p>
        <div v-if="item.media_urls?.length" class="media-row">
          <a v-for="media in item.media_urls" :key="media" :href="resolveAssetUrl(media)" target="_blank" rel="noopener noreferrer">{{ t("timeline.mediaLink") }}</a>
        </div>
      </li>
    </ul>

    <div class="pager">
      <button :disabled="loading || page <= 1" @click="$emit('prev')">{{ t("timeline.prevPage") }}</button>
      <button :disabled="loading || !hasNext" @click="$emit('next')">{{ t("timeline.nextPage") }}</button>
    </div>
  </section>
</template>

<script setup>
import { resolveAssetUrl } from "../lib/api";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

defineProps({
  items: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  page: {
    type: Number,
    default: 1
  },
  total: {
    type: Number,
    default: 0
  },
  hasNext: {
    type: Boolean,
    default: false
  }
});

defineEmits(["refresh", "prev", "next"]);

function formatTime(raw) {
  const time = new Date(raw);
  return Number.isNaN(time.getTime()) ? raw : time.toLocaleString();
}
</script>

<style scoped>
.timeline-wrap {
  border-radius: 22px;
  padding: 1rem;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.9), rgba(244, 249, 255, 0.86));
  border: 1px solid rgba(148, 163, 184, 0.25);
  box-shadow: 0 16px 30px rgba(15, 23, 42, 0.09);
}

.timeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}

.timeline-head h2 {
  margin: 0;
  font-size: 1rem;
  color: #334155;
}

.head-btn {
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: #475569;
  font-size: 0.76rem;
  padding: 0.32rem 0.8rem;
  cursor: pointer;
}

.meta {
  margin: 0.55rem 0 0;
  font-size: 0.75rem;
  color: #64748b;
}

.state-box {
  margin-top: 0.8rem;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px dashed rgba(148, 163, 184, 0.4);
  padding: 0.75rem;
  font-size: 0.82rem;
  color: #64748b;
}

.timeline-list {
  list-style: none;
  margin: 0.8rem 0 0;
  padding: 0;
  display: grid;
  gap: 0.65rem;
}

.timeline-item {
  border-radius: 14px;
  border: 1px solid rgba(203, 213, 225, 0.45);
  background: rgba(255, 255, 255, 0.76);
  padding: 0.7rem 0.8rem;
}

.item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}

.author {
  font-size: 0.83rem;
  font-weight: 600;
  color: #374151;
}

.time {
  font-size: 0.73rem;
  color: #64748b;
}

.content {
  margin: 0.45rem 0 0;
  font-size: 0.84rem;
  color: #334155;
  white-space: pre-wrap;
}

.location {
  margin: 0.35rem 0 0;
  font-size: 0.75rem;
  color: #64748b;
}

.media-row {
  margin-top: 0.45rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.media-row a {
  border-radius: 999px;
  padding: 0.2rem 0.62rem;
  font-size: 0.7rem;
  text-decoration: none;
  color: #3b0764;
  background: #f3e8ff;
}

.pager {
  margin-top: 0.8rem;
  display: flex;
  justify-content: flex-end;
  gap: 0.45rem;
}

.pager button {
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.72);
  color: #475569;
  font-size: 0.75rem;
  padding: 0.35rem 0.6rem;
}

.pager button:disabled {
  opacity: 0.45;
}
</style>
