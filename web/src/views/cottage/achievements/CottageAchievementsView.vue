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
  <div class="content-section cottage-achievements">
    <header class="achievements-header">
      <div>
        <h2>{{ t('cottageAchievements.title') }}</h2>
        <p>{{ t('cottageAchievements.subtitle') }}</p>
      </div>
      <router-link to="/cottage" class="achievements-back">{{ t('cottageAchievements.back') }}</router-link>
    </header>

    <section v-if="loading" class="glass-card section-block empty-text">{{ t('cottageAchievements.loading') }}</section>

    <EmptyState
      v-else-if="loadFailed"
      tone="error"
      :title="t('cottageAchievements.loadFailed')"
      :action-label="t('common.retry')"
      @action="load"
    />

    <template v-else-if="summary">
      <!-- 等级卡 -->
      <section class="glass-card section-block level-card">
        <div class="level-main">
          <div class="level-ring" aria-hidden="true">
            <span class="level-num">Lv.{{ summary.level.level }}</span>
          </div>
          <div class="level-meta">
            <p class="level-title">{{ summary.level.title }}</p>
            <p class="level-points">{{ t('cottageAchievements.points', { n: summary.level.points }) }}</p>
          </div>
        </div>
        <div class="level-progress">
          <div
            class="level-progress-bar"
            role="progressbar"
            :aria-valuenow="summary.level.progress_percent"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <span class="level-progress-fill" :style="{ width: `${Math.min(100, Math.max(0, summary.level.progress_percent))}%` }"></span>
          </div>
          <p class="level-progress-hint">
            <template v-if="summary.level.next_level_points != null">
              {{ t('cottageAchievements.nextLevel', { title: summary.level.next_level_title || '', points: Math.max(0, summary.level.next_level_points - summary.level.points) }) }}
            </template>
            <template v-else>{{ t('cottageAchievements.maxLevel') }}</template>
          </p>
        </div>
      </section>

      <!-- 关键统计 -->
      <section class="glass-card section-block">
        <h3>{{ t('cottageAchievements.statsTitle') }}</h3>
        <div class="stats-grid">
          <div v-for="card in statCards" :key="card.key" class="stat-cell">
            <span>{{ card.value }}</span>
            <p>{{ card.label }}</p>
          </div>
        </div>
      </section>

      <!-- 徽章 -->
      <section class="glass-card section-block">
        <div class="badges-head">
          <h3>{{ t('cottageAchievements.badgesTitle') }}</h3>
          <span>{{ t('cottageAchievements.badgesCount', { done: achievedCount, total: summary.badges.length }) }}</span>
        </div>
        <div v-if="summary.badges.length" class="badges-grid">
          <article
            v-for="badge in summary.badges"
            :key="badge.code"
            class="badge-card"
            :class="[`tier-${badge.tier || 'none'}`, { locked: !badge.achieved }]"
          >
            <span class="badge-icon" aria-hidden="true">{{ badge.icon }}</span>
            <div class="badge-body">
              <p class="badge-name">
                {{ badge.name }}
                <span v-if="badge.achieved && badge.tier && badge.tier !== 'none'" class="badge-tier">{{ tierLabel(badge.tier) }}</span>
              </p>
              <p class="badge-desc">{{ badge.description }}</p>
              <span v-if="badge.achieved" class="badge-done">{{ t('cottageAchievements.achieved') }}</span>
              <div v-else-if="badge.next_target" class="badge-progress">
                <div class="badge-progress-bar">
                  <span :style="{ width: `${badgePercent(badge)}%` }"></span>
                </div>
                <small>{{ t('cottageAchievements.badgeProgress', { current: badge.current, target: badge.next_target }) }}</small>
              </div>
            </div>
          </article>
        </div>
        <p v-else class="empty-text">{{ t('cottageAchievements.emptyBadges') }}</p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import EmptyState from "../../../components/EmptyState.vue";
import { fetchCottageAchievements } from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

const summary = ref(null);
const loading = ref(true);
const loadFailed = ref(false);

const achievedCount = computed(
  () => (summary.value?.badges || []).filter((badge) => badge.achieved).length
);

const statCards = computed(() => {
  const stats = summary.value?.stats || {};
  return [
    { key: "love_days", label: t("cottageAchievements.statLoveDays"), value: stats.love_days || 0 },
    { key: "checkin_streak_days", label: t("cottageAchievements.statCheckinStreak"), value: stats.checkin_streak_days || 0 },
    { key: "mood_streak_days", label: t("cottageAchievements.statMoodStreak"), value: stats.mood_streak_days || 0 },
    { key: "articles", label: t("cottageAchievements.statArticles"), value: stats.articles || 0 },
    { key: "albums", label: t("cottageAchievements.statAlbums"), value: stats.albums || 0 },
    { key: "moments", label: t("cottageAchievements.statMoments"), value: stats.moments || 0 },
    { key: "capsules", label: t("cottageAchievements.statCapsules"), value: stats.capsules || 0 },
    { key: "chat_messages", label: t("cottageAchievements.statChatMessages"), value: stats.chat_messages || 0 },
    { key: "wishes_completed", label: t("cottageAchievements.statWishesCompleted"), value: stats.wishes_completed || 0 },
    { key: "games_played", label: t("cottageAchievements.statGames"), value: stats.games_played || 0 }
  ];
});

function tierLabel(tier) {
  const map = {
    bronze: "cottageAchievements.tierBronze",
    silver: "cottageAchievements.tierSilver",
    gold: "cottageAchievements.tierGold"
  };
  return map[tier] ? t(map[tier]) : tier;
}

function badgePercent(badge) {
  const target = Number(badge.next_target) || 0;
  if (target <= 0) return 0;
  return Math.min(100, Math.round(((Number(badge.current) || 0) / target) * 100));
}

async function load() {
  loading.value = true;
  loadFailed.value = false;
  try {
    summary.value = await fetchCottageAchievements();
  } catch (error) {
    loadFailed.value = true;
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.cottage-achievements {
  display: grid;
  gap: 1rem;
}
.achievements-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.achievements-header h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #2f3754;
}
.achievements-header p {
  margin: 0.35rem 0 0;
  color: var(--text-soft);
  font-size: 0.9rem;
}
.achievements-back {
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

/* 等级卡 */
.level-card {
  display: grid;
  gap: 1rem;
  background: linear-gradient(135deg, rgba(255, 224, 238, 0.85), rgba(232, 234, 255, 0.75));
}
.level-main {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.level-ring {
  width: 76px;
  height: 76px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #ff8ab5, #8f9bff);
  color: #fff;
  box-shadow: 0 10px 22px rgba(255, 138, 181, 0.32);
  flex: 0 0 auto;
}
.level-num {
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: 0.02em;
}
.level-meta {
  min-width: 0;
}
.level-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 800;
  color: #2f3754;
}
.level-points {
  margin: 0.25rem 0 0;
  color: #8a6b7c;
  font-size: 0.85rem;
  font-weight: 600;
}
.level-progress {
  display: grid;
  gap: 0.4rem;
}
.level-progress-bar {
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.75);
  overflow: hidden;
  border: 1px solid rgba(255, 182, 205, 0.55);
}
.level-progress-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #ff8ab5, #8f9bff);
  transition: width 0.4s ease;
}
.level-progress-hint {
  margin: 0;
  color: #8a6b7c;
  font-size: 0.8rem;
}

/* 关键统计 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.7rem;
}
.stat-cell {
  border-radius: 14px;
  padding: 0.8rem 0.9rem;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(203, 213, 225, 0.45);
}
.stat-cell span {
  display: block;
  color: #2f3754;
  font-size: 1.35rem;
  font-weight: 800;
}
.stat-cell p {
  margin: 0.15rem 0 0;
  color: var(--text-soft);
  font-size: 0.78rem;
}

/* 徽章 */
.badges-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  margin-bottom: 0.8rem;
}
.badges-head h3 {
  margin: 0;
  color: #2f3754;
}
.badges-head span {
  color: var(--text-soft);
  font-size: 0.78rem;
}
.badges-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 0.8rem;
}
.badge-card {
  display: flex;
  gap: 0.7rem;
  padding: 0.85rem;
  border-radius: 14px;
  border: 1px solid rgba(203, 213, 225, 0.5);
  background: rgba(255, 255, 255, 0.66);
}
.badge-card.locked {
  opacity: 0.62;
  filter: grayscale(0.5);
}
.badge-card.tier-gold {
  border-color: rgba(234, 179, 8, 0.55);
  background: rgba(254, 249, 195, 0.55);
}
.badge-card.tier-silver {
  border-color: rgba(148, 163, 184, 0.65);
  background: rgba(241, 245, 249, 0.8);
}
.badge-card.tier-bronze {
  border-color: rgba(217, 119, 87, 0.45);
  background: rgba(254, 236, 220, 0.6);
}
.badge-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-size: 1.4rem;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(203, 213, 225, 0.5);
  flex: 0 0 auto;
}
.badge-body {
  min-width: 0;
  flex: 1;
}
.badge-name {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  color: #2f3754;
  font-weight: 700;
  font-size: 0.92rem;
}
.badge-tier {
  border-radius: 999px;
  padding: 0.05rem 0.5rem;
  font-size: 0.68rem;
  font-weight: 700;
}
.tier-gold .badge-tier {
  background: rgba(234, 179, 8, 0.18);
  color: #a16207;
}
.tier-silver .badge-tier {
  background: rgba(100, 116, 139, 0.16);
  color: #475569;
}
.tier-bronze .badge-tier {
  background: rgba(217, 119, 87, 0.16);
  color: #b45309;
}
.badge-desc {
  margin: 0.22rem 0 0;
  color: var(--text-soft);
  font-size: 0.78rem;
  line-height: 1.5;
}
.badge-done {
  display: inline-block;
  margin-top: 0.35rem;
  border-radius: 999px;
  padding: 0.08rem 0.55rem;
  background: rgba(52, 211, 153, 0.16);
  color: #059669;
  font-size: 0.7rem;
  font-weight: 700;
}
.badge-progress {
  display: grid;
  gap: 0.25rem;
  margin-top: 0.45rem;
}
.badge-progress-bar {
  height: 6px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.25);
  overflow: hidden;
}
.badge-progress-bar span {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #ffb1c8, #8f9bff);
}
.badge-progress small {
  color: var(--text-soft);
  font-size: 0.7rem;
}

@media (max-width: 768px) {
  .achievements-header {
    flex-direction: column;
  }
  .achievements-back {
    width: 100%;
    justify-content: center;
  }
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
