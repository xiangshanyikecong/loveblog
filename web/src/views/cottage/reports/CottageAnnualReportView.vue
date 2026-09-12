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
  <div class="content-section cottage-annual">
    <header class="annual-header">
      <div>
        <h2>{{ t('cottageAnnualReport.title') }}</h2>
        <p>{{ t('cottageAnnualReport.subtitle') }}</p>
      </div>
      <router-link to="/cottage" class="annual-back">{{ t('cottageAnnualReport.back') }}</router-link>
    </header>

    <section class="glass-card section-block year-controls">
      <button
        class="year-btn"
        type="button"
        :aria-label="t('cottageAnnualReport.prevYear')"
        @click="shiftYear(-1)"
      >‹</button>
      <div class="year-big">{{ year }}</div>
      <button
        class="year-btn"
        type="button"
        :aria-label="t('cottageAnnualReport.nextYear')"
        :disabled="year >= currentYear"
        @click="shiftYear(1)"
      >›</button>
    </section>

    <section v-if="loading" class="glass-card section-block empty-text">{{ t('cottageAnnualReport.loading') }}</section>

    <template v-else-if="report">
      <section v-if="report.couple_since" class="glass-card section-block couple-card">
        <p class="couple-days">{{ t('cottageAnnualReport.coupleSince', { days: report.days_together ?? 0 }) }}</p>
        <p class="couple-since">{{ t('cottageAnnualReport.sinceDate', { date: sinceText }) }}</p>
      </section>

      <section class="annual-stats">
        <article v-for="card in statCards" :key="card.key" class="glass-card annual-stat">
          <span>{{ card.value }}</span>
          <p>{{ card.label }}</p>
        </article>
      </section>

      <template v-if="hasData">
        <section class="glass-card section-block annual-block">
          <h3>{{ t('cottageAnnualReport.monthlyTitle') }}</h3>
          <div class="monthly-legend">
            <span class="legend-item"><i class="legend-dot dot-articles"></i>{{ t('cottageAnnualReport.articlesLabel') }}</span>
            <span class="legend-item"><i class="legend-dot dot-songs"></i>{{ t('cottageAnnualReport.songsLabel') }}</span>
            <span class="legend-item"><i class="legend-dot dot-checkins"></i>{{ t('cottageAnnualReport.checkinsLabel') }}</span>
          </div>
          <div class="monthly-chart">
            <div v-for="m in monthly" :key="m.month" class="month-col">
              <div class="month-bars" :title="monthTitle(m)">
                <i class="bar bar-articles" :style="{ height: barHeight(m.articles) }"></i>
                <i class="bar bar-songs" :style="{ height: barHeight(m.songs) }"></i>
                <i class="bar bar-checkins" :style="{ height: barHeight(m.checkins) }"></i>
              </div>
              <span class="month-label">{{ m.month }}</span>
            </div>
          </div>
        </section>

        <section class="annual-grid">
          <article class="glass-card section-block annual-block">
            <h3>{{ t('cottageAnnualReport.topSongsTitle') }}</h3>
            <ol v-if="topSongs.length" class="top-songs">
              <li v-for="(song, index) in topSongs" :key="song.song_id" class="top-song">
                <span class="top-song-rank" :class="{ top: index < 3 }">{{ index + 1 }}</span>
                <img v-if="song.cover_url" :src="song.cover_url" :alt="song.name" class="top-song-cover" />
                <span v-else class="top-song-cover top-song-placeholder" aria-hidden="true">🎵</span>
                <div class="top-song-meta">
                  <p class="top-song-name">{{ song.name }}</p>
                  <p v-if="artistsText(song.artists)" class="top-song-artists">{{ artistsText(song.artists) }}</p>
                </div>
                <span class="top-song-count">{{ t('cottageAnnualReport.playCount', { count: song.play_count ?? 0 }) }}</span>
              </li>
            </ol>
            <p v-else class="empty-text">{{ t('cottageAnnualReport.emptyYear') }}</p>
          </article>

          <article class="glass-card section-block annual-block">
            <h3>{{ t('cottageAnnualReport.highlightsTitle') }}</h3>
            <ul v-if="highlights.length" class="highlight-list">
              <li v-for="(item, index) in highlights" :key="index" class="highlight-item">
                <span class="highlight-bullet" aria-hidden="true">✨</span>
                <p>{{ item }}</p>
              </li>
            </ul>
            <p v-else class="empty-text">{{ t('cottageAnnualReport.emptyYear') }}</p>
          </article>
        </section>
      </template>

      <section v-else class="glass-card section-block annual-empty">
        <span class="annual-empty-emoji" aria-hidden="true">📮</span>
        <p>{{ t('cottageAnnualReport.emptyYear') }}</p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { fetchAnnualReport } from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

const currentYear = new Date().getFullYear();
const year = ref(currentYear);
const report = ref(null);
const loading = ref(true);

const statCards = computed(() => {
  const stats = report.value?.stats || {};
  return [
    { key: "articles", label: t('cottageAnnualReport.statArticles'), value: stats.articles || 0 },
    { key: "albums", label: t('cottageAnnualReport.statAlbums'), value: stats.albums || 0 },
    { key: "photos", label: t('cottageAnnualReport.statPhotos'), value: stats.photos || 0 },
    { key: "checkins", label: t('cottageAnnualReport.statCheckins'), value: stats.checkins || 0 },
    { key: "messages", label: t('cottageAnnualReport.statMessages'), value: stats.messages || 0 },
    { key: "songs_played", label: t('cottageAnnualReport.statSongs'), value: stats.songs_played || 0 },
    { key: "songs_minutes", label: t('cottageAnnualReport.statSongsMinutes'), value: stats.songs_minutes || 0 },
    { key: "capsules_created", label: t('cottageAnnualReport.statCapsules'), value: stats.capsules_created || 0 },
    { key: "wishes_completed", label: t('cottageAnnualReport.statWishes'), value: stats.wishes_completed || 0 }
  ];
});

const monthly = computed(() => {
  const list = Array.isArray(report.value?.monthly) ? report.value.monthly : [];
  const filled = Array.from({ length: 12 }, (_, i) => {
    const found = list.find((m) => Number(m.month) === i + 1);
    return {
      month: i + 1,
      articles: found?.articles || 0,
      songs: found?.songs || 0,
      checkins: found?.checkins || 0
    };
  });
  return filled;
});

const monthlyMax = computed(() =>
  monthly.value.reduce((max, m) => Math.max(max, m.articles, m.songs, m.checkins), 0)
);

const topSongs = computed(() => report.value?.top_songs || []);
const highlights = computed(() => report.value?.highlights || []);

const hasData = computed(() => {
  if (!report.value) return false;
  const stats = report.value.stats || {};
  const anyStat = Object.values(stats).some((v) => Number(v) > 0);
  return anyStat || topSongs.value.length > 0 || highlights.value.length > 0;
});

const sinceText = computed(() => {
  const raw = report.value?.couple_since;
  if (!raw) return "";
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? String(raw).slice(0, 10) : date.toLocaleDateString("zh-CN");
});

function shiftYear(delta) {
  const next = year.value + delta;
  if (next > currentYear || next < 1970) return;
  year.value = next;
  load();
}

function barHeight(value) {
  if (monthlyMax.value <= 0) return "4px";
  const ratio = Math.max(Number(value) || 0, 0) / monthlyMax.value;
  return `${Math.max(ratio * 100, 3)}%`;
}

function monthTitle(m) {
  return `${m.month} · ${t('cottageAnnualReport.articlesLabel')} ${m.articles} / ${t('cottageAnnualReport.songsLabel')} ${m.songs} / ${t('cottageAnnualReport.checkinsLabel')} ${m.checkins}`;
}

function artistsText(artists) {
  if (Array.isArray(artists)) return artists.filter(Boolean).join(" / ");
  return String(artists || "").trim();
}

async function load() {
  loading.value = true;
  try {
    report.value = await fetchAnnualReport(year.value);
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.cottage-annual { display: grid; gap: 1rem; }
.annual-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.annual-header h2 { margin: 0; font-size: 1.4rem; color: #2f3754; }
.annual-header p { margin: 0.35rem 0 0; color: var(--text-soft); font-size: 0.9rem; }
.annual-back {
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

/* 年份切换 */
.year-controls {
  display: grid;
  grid-template-columns: 46px minmax(140px, 220px) 46px;
  gap: 0.85rem;
  align-items: center;
  justify-content: center;
}
.year-btn {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.38);
  background: rgba(255, 255, 255, 0.76);
  color: #3d4665;
  font-size: 1.45rem;
  cursor: pointer;
}
.year-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.year-big {
  text-align: center;
  font-size: 2.1rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  background: linear-gradient(120deg, #ff8ab5, #b48cf2);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

/* 在一起天数 */
.couple-card {
  text-align: center;
  padding: 1.5rem 1.2rem;
  background: linear-gradient(135deg, rgba(255, 224, 238, 0.85), rgba(247, 222, 255, 0.75));
}
.couple-days {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 800;
  color: #a1336b;
}
.couple-since { margin: 0.35rem 0 0; color: #7a5c6e; font-size: 0.88rem; }

/* stats 网格 */
.annual-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}
.annual-stat {
  border-radius: 16px;
  padding: 0.9rem;
  text-align: center;
}
.annual-stat span {
  display: block;
  font-size: 1.55rem;
  font-weight: 800;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.annual-stat p { margin: 0.18rem 0 0; color: var(--text-soft); font-size: 0.78rem; }

.annual-block h3 { margin: 0 0 0.8rem; color: #2f3754; }
.annual-empty {
  display: grid;
  justify-items: center;
  gap: 0.5rem;
  padding: 2.4rem 1.2rem;
  text-align: center;
}
.annual-empty-emoji { font-size: 2.2rem; line-height: 1; }
.annual-empty p { margin: 0; color: var(--text-soft); }

/* 每月条形图 */
.monthly-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.9rem;
  margin-bottom: 0.9rem;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--text-soft);
  font-size: 0.78rem;
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}
.dot-articles { background: #ff8ab5; }
.dot-songs { background: #8f9bff; }
.dot-checkins { background: #34d399; }
.monthly-chart {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 0.35rem;
  align-items: end;
}
.month-col { display: grid; gap: 0.4rem; justify-items: center; }
.month-bars {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  width: 100%;
  height: 140px;
  justify-content: center;
}
.bar {
  display: block;
  width: 7px;
  border-radius: 4px 4px 2px 2px;
  min-height: 3px;
  transition: height 0.3s ease;
}
.bar-articles { background: linear-gradient(180deg, #ffb3cd, #ff8ab5); }
.bar-songs { background: linear-gradient(180deg, #b3bcff, #8f9bff); }
.bar-checkins { background: linear-gradient(180deg, #7ce7c2, #34d399); }
.month-label {
  color: var(--text-soft);
  font-size: 0.72rem;
}

/* 两栏 */
.annual-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

/* 最常一起听 */
.top-songs {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.55rem;
}
.top-song {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(203, 213, 225, 0.45);
  padding: 0.6rem 0.7rem;
}
.top-song-rank {
  flex: 0 0 auto;
  width: 22px;
  text-align: center;
  color: var(--text-soft);
  font-size: 0.85rem;
  font-weight: 700;
}
.top-song-rank.top { color: #e2698f; }
.top-song-cover {
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  object-fit: cover;
}
.top-song-placeholder {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #ffe3ee, #fff6fa);
}
.top-song-meta { flex: 1 1 auto; min-width: 0; }
.top-song-name {
  margin: 0;
  color: #2f3754;
  font-size: 0.9rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top-song-artists {
  margin: 0.1rem 0 0;
  color: var(--text-soft);
  font-size: 0.78rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top-song-count {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 0.18rem 0.6rem;
  background: rgba(220, 75, 120, 0.1);
  color: #dc4b78;
  font-size: 0.74rem;
  font-weight: 700;
}

/* 年度亮点 */
.highlight-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.55rem;
}
.highlight-item {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(255, 240, 246, 0.85), rgba(255, 252, 253, 0.8));
  border: 1px solid rgba(255, 182, 205, 0.45);
  padding: 0.65rem 0.75rem;
}
.highlight-bullet { flex: 0 0 auto; font-size: 0.95rem; line-height: 1.5; }
.highlight-item p {
  margin: 0;
  color: #2f3754;
  font-size: 0.88rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

@media (max-width: 960px) {
  .annual-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .annual-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .annual-header { flex-direction: column; }
  .annual-back { width: 100%; justify-content: center; }
  .annual-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .month-bars { height: 110px; }
  .bar { width: 5px; }
}
</style>
