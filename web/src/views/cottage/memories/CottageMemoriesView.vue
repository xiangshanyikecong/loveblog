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
  <div class="content-section cottage-memories">
    <header class="memories-header">
      <div>
        <h2>{{ t('cottageMemories.title') }}</h2>
        <p>{{ t('cottageMemories.subtitle') }}</p>
      </div>
      <router-link to="/cottage" class="memories-back">{{ t('cottageMemories.back') }}</router-link>
    </header>

    <section v-if="loading" class="glass-card section-block empty-text">{{ t('cottageMemories.loading') }}</section>

    <section v-else-if="!groups.length" class="glass-card section-block memories-empty">
      <span class="memories-empty-emoji" aria-hidden="true">🌱</span>
      <p>{{ t('cottageMemories.empty') }}</p>
    </section>

    <template v-else>
      <p class="memories-date">
        {{ t('cottageMemories.dateLabel') }}<template v-if="dateText"> · {{ dateText }}</template>
      </p>

      <article v-for="g in groups" :key="g.year" class="glass-card memory-year-card">
        <header class="memory-year-head">
          <span class="memory-year-badge">{{ g.label }}</span>
          <span class="memory-year-num">{{ g.year }}</span>
        </header>

        <section v-if="g.articles.length" class="memory-block">
          <h3 class="memory-block-title">{{ t('cottageMemories.articles') }}</h3>
          <router-link
            v-for="a in g.articles"
            :key="a.aid"
            :to="`/articles/${a.aid}`"
            class="memory-article"
          >
            <p class="memory-article-title">{{ a.title }}</p>
            <p v-if="a.excerpt" class="memory-article-excerpt">{{ a.excerpt }}</p>
          </router-link>
          <p v-if="g.totals.articles > g.articles.length" class="memory-more">
            {{ t('cottageMemories.moreItems', { count: g.totals.articles }) }}
          </p>
        </section>

        <section v-if="g.albums.length" class="memory-block">
          <h3 class="memory-block-title">{{ t('cottageMemories.albums') }}</h3>
          <div class="memory-albums">
            <router-link
              v-for="alb in g.albums"
              :key="alb.alb_id"
              :to="`/albums/${alb.alb_id}`"
              class="memory-album"
            >
              <img v-if="alb.cover_url" :src="alb.cover_url" :alt="alb.title" class="memory-album-cover" />
              <span v-else class="memory-album-cover memory-album-placeholder" aria-hidden="true">🖼️</span>
              <p class="memory-album-title">{{ alb.title }}</p>
            </router-link>
          </div>
          <p v-if="g.totals.albums > g.albums.length" class="memory-more">
            {{ t('cottageMemories.moreItems', { count: g.totals.albums }) }}
          </p>
        </section>

        <section v-if="g.songs.length" class="memory-block">
          <h3 class="memory-block-title">{{ t('cottageMemories.songs') }}</h3>
          <ul class="memory-songs">
            <li v-for="s in g.songs" :key="s.song_id" class="memory-song">
              <img v-if="s.cover_url" :src="s.cover_url" :alt="s.name" class="memory-song-cover" />
              <span v-else class="memory-song-cover memory-song-placeholder" aria-hidden="true">🎵</span>
              <div class="memory-song-meta">
                <p class="memory-song-name">{{ s.name }}</p>
                <p v-if="artistsText(s.artists)" class="memory-song-artists">{{ artistsText(s.artists) }}</p>
              </div>
            </li>
          </ul>
          <p v-if="g.totals.songs > g.songs.length" class="memory-more">
            {{ t('cottageMemories.moreItems', { count: g.totals.songs }) }}
          </p>
        </section>
      </article>
    </template>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { fetchOnThisDay } from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

const currentYear = new Date().getFullYear();
const data = ref(null);
const loading = ref(true);

const groups = computed(() => {
  const years = Array.isArray(data.value?.years) ? data.value.years : [];
  return years.map((entry) => {
    const diff = currentYear - entry.year;
    const label =
      diff === 1
        ? t('cottageMemories.oneYearAgo')
        : diff > 1
          ? t('cottageMemories.yearsAgo', { years: diff })
          : String(entry.year);
    return {
      year: entry.year,
      label,
      articles: entry.articles || [],
      albums: entry.albums || [],
      songs: entry.songs || [],
      totals: entry.totals || { articles: 0, albums: 0, songs: 0 }
    };
  });
});

const dateText = computed(() => {
  const raw = data.value?.date;
  if (!raw) return "";
  const date = new Date(raw);
  return Number.isNaN(date.getTime())
    ? String(raw).slice(0, 10)
    : date.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
});

function artistsText(artists) {
  if (Array.isArray(artists)) return artists.filter(Boolean).join(" / ");
  return String(artists || "").trim();
}

async function load() {
  loading.value = true;
  try {
    data.value = await fetchOnThisDay();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.cottage-memories { display: grid; gap: 1rem; }
.memories-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.memories-header h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #2f3754;
}
.memories-header p { margin: 0.35rem 0 0; color: var(--text-soft); font-size: 0.9rem; }
.memories-back {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  font-size: 0.82rem;
  text-decoration: none;
  white-space: nowrap;
}
.memories-empty {
  display: grid;
  justify-items: center;
  gap: 0.5rem;
  padding: 2.4rem 1.2rem;
  text-align: center;
}
.memories-empty-emoji { font-size: 2.2rem; line-height: 1; }
.memories-empty p { margin: 0; color: var(--text-soft); }
.memories-date {
  margin: 0;
  padding-left: 0.1rem;
  color: var(--text-soft);
  font-size: 0.88rem;
}

/* 年份卡片 */
.memory-year-card {
  display: grid;
  gap: 1.1rem;
  padding: 1.25rem 1.35rem 1.4rem;
  border-radius: 20px;
}
.memory-year-head {
  display: flex;
  align-items: center;
  gap: 0.7rem;
}
.memory-year-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.95rem;
  border-radius: 999px;
  background: linear-gradient(120deg, #ff9ec0, #ffc7d9);
  color: #8c2f56;
  font-size: 0.92rem;
  font-weight: 700;
  box-shadow: 0 6px 14px rgba(255, 158, 192, 0.35);
}
.memory-year-num {
  color: var(--text-soft);
  font-size: 0.88rem;
  letter-spacing: 0.05em;
}

/* 区块 */
.memory-block { display: grid; gap: 0.6rem; }
.memory-block-title {
  margin: 0;
  font-size: 0.95rem;
  color: #2f3754;
  display: flex;
  align-items: center;
  gap: 0.45rem;
}
.memory-block-title::before {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ff8ab5, #f9a8c9);
  box-shadow: 0 2px 6px rgba(255, 138, 181, 0.55);
}

/* 日记 */
.memory-article {
  display: grid;
  gap: 0.25rem;
  padding: 0.7rem 0.9rem;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(255, 240, 246, 0.9), rgba(255, 252, 253, 0.85));
  border: 1px solid rgba(255, 182, 205, 0.45);
  text-decoration: none;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.memory-article:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 20px rgba(255, 138, 181, 0.18);
}
.memory-article-title {
  margin: 0;
  color: #2f3754;
  font-size: 0.95rem;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.memory-article-excerpt {
  margin: 0;
  color: var(--text-soft);
  font-size: 0.82rem;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 相册 */
.memory-albums {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 0.75rem;
}
.memory-album {
  display: grid;
  gap: 0.4rem;
  text-decoration: none;
}
.memory-album-cover {
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  border-radius: 14px;
  border: 1px solid rgba(255, 182, 205, 0.5);
  box-shadow: 0 8px 18px rgba(255, 138, 181, 0.18);
}
.memory-album-placeholder {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1.6rem;
  background: linear-gradient(135deg, #ffe3ee, #fff6fa);
}
.memory-album-title {
  margin: 0;
  color: #2f3754;
  font-size: 0.84rem;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 歌单 */
.memory-songs {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.5rem;
}
.memory-song {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.55rem 0.75rem;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(203, 213, 225, 0.45);
}
.memory-song-cover {
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  object-fit: cover;
}
.memory-song-placeholder {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #ffe3ee, #fff6fa);
}
.memory-song-meta { min-width: 0; }
.memory-song-name {
  margin: 0;
  color: #2f3754;
  font-size: 0.9rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.memory-song-artists {
  margin: 0.1rem 0 0;
  color: var(--text-soft);
  font-size: 0.78rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 更多 */
.memory-more {
  margin: 0.15rem 0 0;
  color: var(--text-soft);
  font-size: 0.78rem;
}

@media (max-width: 768px) {
  .memories-header { flex-direction: column; }
  .memories-back { width: 100%; justify-content: center; }
  .memory-albums { grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); }
}
</style>
