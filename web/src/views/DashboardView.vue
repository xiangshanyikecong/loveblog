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
    <section
      v-if="hasCouple"
      class="home-hero glass-card"
      :class="{ 'home-hero--personal': isLoggedInPartner }"
    >
      <div v-if="isLoggedInPartner" class="hero-greeting">
        <p class="hero-greeting-text">{{ greeting }}，{{ myNickname }}</p>
        <p class="hero-greeting-sub">{{ t('dashboard.greetingSub') }}</p>
      </div>
      <div class="hero-couple">
        <div class="hero-avatar-wrapper">
          <img
            v-if="couple.partner_a && couple.partner_a.avatar"
            :src="getAvatarUrl(couple.partner_a.avatar)"
            alt="Partner A"
            class="hero-avatar"
          />
          <div v-else class="hero-avatar-placeholder">{{ initialOf(couple.partner_a, 'A') }}</div>
          <div class="hero-avatar-name">{{ (couple.partner_a && couple.partner_a.nickname) || 'Partner A' }}</div>
        </div>
        <div class="hero-heart" aria-hidden="true">
          <Heart :size="30" :stroke-width="1.8" fill="currentColor" />
        </div>
        <div class="hero-avatar-wrapper">
          <img
            v-if="couple.partner_b && couple.partner_b.avatar"
            :src="getAvatarUrl(couple.partner_b.avatar)"
            alt="Partner B"
            class="hero-avatar"
          />
          <div v-else class="hero-avatar-placeholder">{{ initialOf(couple.partner_b, 'B') }}</div>
          <div class="hero-avatar-name">{{ (couple.partner_b && couple.partner_b.nickname) || 'Partner B' }}</div>
        </div>
      </div>
      <p class="hero-together">
        {{ t('dashboard.togetherDays', { n: dashboard.love_clock.days }) }}
      </p>
    </section>

    <div class="section-header">
      <div>
        <h2>{{ isLoggedInPartner ? t('dashboard.titlePartner') : t('dashboard.titleGuest') }}</h2>
        <p class="section-intro">
          {{ isLoggedInPartner ? t('dashboard.introPartner') : t('dashboard.introGuest') }}
        </p>
      </div>
      <button class="ghost-btn" @click="reloadDashboard">{{ t('dashboard.refresh') }}</button>
    </div>

    <section v-if="!hasCouple" class="guest-summary glass-card">
      <EmptyState
        :icon="Heart"
        :title="t('dashboard.guestEmptyTitle')"
        :description="t('dashboard.guestEmptyDesc')"
        :action-label="t('dashboard.guestEmptyAction')"
        action-to="/login"
      />
    </section>

    <section v-if="memories.length" class="glass-card section-block memories-banner">
      <div class="section-header">
        <h2 class="memory-title">{{ t('dashboard.memoriesTitle', { n: memories.length }) }}</h2>
      </div>
      <div class="memories-scroll">
        <div v-for="m in memories" :key="m.mid" class="memory-item">
          <p class="memory-meta">{{ t('dashboard.memoryMeta', { year: new Date(m.timestamp).getFullYear() }) }}</p>
          <p class="memory-text">{{ m.content }}</p>
        </div>
      </div>
    </section>

    <div v-if="hasCouple" class="overview-grid">
      <article class="stat-card glass-card">
        <div class="stat-icon stat-icon--article">文</div>
        <div class="stat-info">
          <h3>{{ dashboard.stats.article_count }}</h3>
          <p>{{ t('dashboard.statArticles') }}</p>
        </div>
      </article>

      <article class="stat-card glass-card">
        <div class="stat-icon stat-icon--album">册</div>
        <div class="stat-info">
          <h3>{{ dashboard.stats.album_count }}</h3>
          <p>{{ t('dashboard.statAlbums') }}</p>
        </div>
      </article>

      <article class="stat-card glass-card">
        <div class="stat-icon stat-icon--event">事</div>
        <div class="stat-info">
          <h3>{{ dashboard.stats.event_count }}</h3>
          <p>{{ t('dashboard.statEvents') }}</p>
        </div>
      </article>
    </div>

    <div v-if="hasCouple" class="dashboard-grid">
      <section class="relationship-summary glass-card">
        <div class="relationship-summary-head">
          <div>
            <p class="relationship-summary-label">{{ t('dashboard.togetherLabel') }}</p>
            <h2>{{ t('dashboard.dayN', { n: dashboard.love_clock.days }) }}</h2>
          </div>
          <Heart class="relationship-summary-icon" :size="28" :stroke-width="1.8" fill="currentColor" aria-hidden="true" />
        </div>
        <div class="relationship-summary-body">
          <div class="love-timer">
            <span class="love-timer-number">{{ pad2(dashboard.love_clock.hours) }}</span>
            <span class="love-timer-label">{{ t('dashboard.hours') }}</span>
            <span class="love-timer-number">{{ pad2(dashboard.love_clock.minutes) }}</span>
            <span class="love-timer-label">{{ t('dashboard.minutes') }}</span>
            <span class="love-timer-number">{{ pad2(dashboard.love_clock.seconds) }}</span>
            <span class="love-timer-label">{{ t('dashboard.seconds') }}</span>
          </div>
        </div>
      </section>

      <CountdownCard :event="validCountdownEvent" :loading="busy" />
    </div>

    <section class="focus-section">
      <div class="section-header">
        <h2>{{ t('dashboard.focusTitle') }}</h2>
      </div>
      <div class="focus-grid">
        <router-link to="/articles" class="focus-card focus-card--content">
          <span class="focus-card-icon"><BookOpen :size="22" :stroke-width="1.8" aria-hidden="true" /></span>
          <div class="focus-card-copy">
            <p class="focus-card-label">{{ t('dashboard.focusContentLabel') }}</p>
            <h3>{{ t('dashboard.focusContentTitle') }}</h3>
            <p class="focus-card-desc">{{ t('dashboard.focusContentDesc') }}</p>
          </div>
          <ArrowUpRight class="focus-card-arrow" :size="18" :stroke-width="1.8" aria-hidden="true" />
        </router-link>
        <router-link to="/events" class="focus-card focus-card--memories">
          <span class="focus-card-icon"><CalendarHeart :size="22" :stroke-width="1.8" aria-hidden="true" /></span>
          <div class="focus-card-copy">
            <p class="focus-card-label">{{ t('dashboard.focusMemoriesLabel') }}</p>
            <h3>{{ t('dashboard.focusMemoriesTitle') }}</h3>
            <p class="focus-card-desc">{{ t('dashboard.focusMemoriesDesc') }}</p>
          </div>
          <ArrowUpRight class="focus-card-arrow" :size="18" :stroke-width="1.8" aria-hidden="true" />
        </router-link>
        <router-link to="/messages" class="focus-card focus-card--messages">
          <span class="focus-card-icon"><MessageCircle :size="22" :stroke-width="1.8" aria-hidden="true" /></span>
          <div class="focus-card-copy">
            <p class="focus-card-label">{{ t('dashboard.focusMessagesLabel') }}</p>
            <h3>{{ t('dashboard.focusMessagesTitle') }}</h3>
            <p class="focus-card-desc">{{ t('dashboard.focusMessagesDesc') }}</p>
          </div>
          <ArrowUpRight class="focus-card-arrow" :size="18" :stroke-width="1.8" aria-hidden="true" />
        </router-link>
        <router-link
          v-if="canManageContent"
          to="/cottage"
          class="focus-card focus-card--cottage"
        >
          <span class="focus-card-icon"><House :size="22" :stroke-width="1.8" aria-hidden="true" /></span>
          <div class="focus-card-copy">
            <p class="focus-card-label">{{ t('dashboard.focusCottageLabel') }}</p>
            <h3>{{ t('dashboard.focusCottageTitle') }}</h3>
            <p class="focus-card-desc">{{ t('dashboard.focusCottageDesc') }}</p>
          </div>
          <ArrowUpRight class="focus-card-arrow" :size="18" :stroke-width="1.8" aria-hidden="true" />
        </router-link>
      </div>
    </section>

    <section v-if="hasCouple || dashboard.recent_events.length" class="content-section-inner glass-card">
      <div class="section-header">
        <h2>{{ t('dashboard.recentEventsTitle') }}</h2>
      </div>

      <div v-if="dashboard.recent_events.length" class="events-list">
        <article
          v-for="(item, index) in dashboard.recent_events"
          :key="item.eid"
          class="event-pill"
          :style="eventGradient(index)"
        >
          <div class="event-pill-main">
            <p class="event-pill-title">{{ item.title }}</p>
            <p class="event-pill-desc">
              {{ item.type }}
              <span v-if="item.is_important"> · {{ t('dashboard.eventImportant') }}</span>
              <span v-if="item.is_yearly_repeat"> · {{ t('dashboard.eventYearly') }}</span>
            </p>
          </div>
          <div class="event-pill-meta">
            <p class="event-pill-date">{{ item.date }}</p>
            <p class="event-pill-days">{{ eventStatusText(item) }}</p>
          </div>
        </article>
      </div>
      <EmptyState
        v-else
        :icon="CalendarHeart"
        :title="t('dashboard.noEventsTitle')"
        :description="t('dashboard.noEventsDesc')"
        :action-label="t('dashboard.noEventsAction')"
        action-to="/events"
      />
    </section>

    <div v-if="hasCouple || dashboard.latest_articles.length || dashboard.latest_albums.length || token" class="summary-grid">
      <section v-if="hasCouple || dashboard.latest_articles.length" class="glass-card section-block">
        <div class="section-header">
          <h2>{{ t('dashboard.latestArticles') }}</h2>
          <router-link to="/articles" class="summary-link">{{ t('dashboard.allArticles') }}</router-link>
        </div>
        <ul v-if="dashboard.latest_articles.length" class="simple-list">
          <li v-for="item in dashboard.latest_articles" :key="item.aid">
            <span>{{ item.title }}</span>
            <span v-if="item.partner_can_edit" class="pill pill--mint">{{ t('dashboard.coEdit') }}</span>
          </li>
        </ul>
        <EmptyState
          v-else
          :icon="FileText"
          :title="t('dashboard.noArticlesTitle')"
          :description="t('dashboard.noArticlesDesc')"
          :action-label="t('dashboard.noArticlesAction')"
          action-to="/articles"
        />
      </section>

      <section v-if="hasCouple || dashboard.latest_albums.length" class="glass-card section-block">
        <div class="section-header">
          <h2>{{ t('dashboard.latestAlbums') }}</h2>
          <router-link to="/albums" class="summary-link">{{ t('dashboard.allAlbums') }}</router-link>
        </div>
        <ul v-if="dashboard.latest_albums.length" class="simple-list">
          <li v-for="item in dashboard.latest_albums" :key="item.alb_id">
            <span>{{ item.title }}</span>
            <span v-if="item.is_encrypted" class="pill pill--gold">{{ t('dashboard.encrypted') }}</span>
          </li>
        </ul>
        <EmptyState
          v-else
          :icon="Image"
          :title="t('dashboard.noAlbumsTitle')"
          :description="t('dashboard.noAlbumsDesc')"
          :action-label="t('dashboard.noAlbumsAction')"
          action-to="/albums"
        />
      </section>

      <MessageBoard v-if="hasCouple || token" :title="t('dashboard.latestMessages')" :max-items="6" open-page-path="/messages" :show-composer="false" />
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, onUnmounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { ArrowUpRight, BookOpen, CalendarHeart, FileText, Heart, House, Image, MessageCircle } from "@lucide/vue";
import CountdownCard from "../components/CountdownCard.vue";
import EmptyState from "../components/EmptyState.vue";
import MessageBoard from "../components/MessageBoard.vue";
import { fetchDashboard, fetchMemories, resolveAssetUrl } from "../lib/api";
import { useAuth } from "../stores/auth";
import { eventGradient, eventStatusText, pad2, parseError } from "../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage");
const { token, canManageContent, currentUserRole } = useAuth();

const dashboard = reactive({
  love_clock: { days: 0, hours: 0, minutes: 0, seconds: 0 },
  stats: { article_count: 0, album_count: 0, event_count: 0, message_count: 0 },
  couple: { partner_a: null, partner_b: null },
  recent_events: [],
  latest_articles: [],
  latest_albums: []
});

const couple = computed(() => dashboard.couple || { partner_a: null, partner_b: null });
const hasCouple = computed(() => Boolean(couple.value.partner_a || couple.value.partner_b));
const isLoggedInPartner = computed(() => canManageContent.value);

const greeting = computed(() => {
  const hour = new Date().getHours();
  if (hour < 6) return t("dashboard.greetingLateNight");
  if (hour < 9) return t("dashboard.greetingMorning");
  if (hour < 12) return t("dashboard.greetingForenoon");
  if (hour < 14) return t("dashboard.greetingNoon");
  if (hour < 18) return t("dashboard.greetingAfternoon");
  return t("dashboard.greetingEvening");
});

const myNickname = computed(() => {
  if (currentUserRole.value === "PartnerA") return couple.value.partner_a?.nickname || t("dashboard.defaultNickname");
  if (currentUserRole.value === "PartnerB") return couple.value.partner_b?.nickname || t("dashboard.defaultNickname");
  return t("dashboard.defaultNickname");
});

function initialOf(member, fallback) {
  const nickname = member?.nickname?.trim();
  return nickname ? nickname.charAt(0).toUpperCase() : fallback;
}

const busy = ref(false);
const memories = ref([]);

const validCountdownEvent = computed(() => {
  const now = new Date();
  now.setHours(0, 0, 0, 0);

  return (
    dashboard.recent_events.find((event) => {
      if (event.is_yearly_repeat) {
        return true;
      }
      const target = new Date(`${event.date}T00:00:00`);
      return target.getTime() >= now.getTime();
    }) || null
  );
});

let clockInterval = null;

function tickLoveClock() {
  if (!dashboard.love_clock) {
    return;
  }

  dashboard.love_clock.seconds += 1;
  if (dashboard.love_clock.seconds >= 60) {
    dashboard.love_clock.seconds = 0;
    dashboard.love_clock.minutes += 1;
    if (dashboard.love_clock.minutes >= 60) {
      dashboard.love_clock.minutes = 0;
      dashboard.love_clock.hours += 1;
      if (dashboard.love_clock.hours >= 24) {
        dashboard.love_clock.hours = 0;
        dashboard.love_clock.days += 1;
      }
    }
  }
}

function getAvatarUrl(path) {
  return resolveAssetUrl(path);
}

async function reloadDashboard() {
  busy.value = true;
  try {
    const data = await fetchDashboard();
    dashboard.love_clock = data.love_clock;
    dashboard.stats = data.stats;
    dashboard.couple = data.couple || { partner_a: null, partner_b: null };
    dashboard.recent_events = data.recent_events || [];
    dashboard.latest_articles = data.latest_articles || [];
    dashboard.latest_albums = data.latest_albums || [];
  } catch (error) {
    showMessage(parseError(error), "error");
  } finally {
    busy.value = false;
  }
}

async function loadMemories() {
  if (!token.value) {
    memories.value = [];
    return;
  }
  try {
    memories.value = await fetchMemories();
  } catch {
    // Keep the dashboard usable when the optional memory summary is unavailable.
  }
}

onMounted(() => {
  reloadDashboard();
  loadMemories();
  clockInterval = setInterval(tickLoveClock, 1000);
});

onUnmounted(() => {
  if (clockInterval) {
    clearInterval(clockInterval);
  }
});
</script>

<style scoped>
.section-intro {
  margin: 0.35rem 0 0;
  font-size: 0.84rem;
  color: #64748b;
}

.memories-banner {
  background: var(--surface-tint);
  border-color: #efc3d1;
}

.memory-title {
  color: var(--brand-strong);
  font-weight: 800;
}

.memories-scroll {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.memory-item {
  padding-left: 1rem;
  border-left: 3px solid var(--brand);
}

.memory-meta {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--brand-strong);
  margin: 0 0 0.25rem;
}

.memory-text {
  font-size: 0.95rem;
  color: var(--text-main);
  margin: 0;
}

.home-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
  padding: 2rem;
  background: var(--surface-tint);
  border-color: #efc3d1;
  text-align: center;
}

.home-hero--personal {
  background: #fff7fa;
  box-shadow: 0 14px 30px rgb(128 62 85 / 0.1);
}

.hero-greeting {
  display: grid;
  gap: 0.3rem;
}

.hero-greeting-text {
  margin: 0;
  font-size: 1.6rem;
  font-weight: 800;
  color: var(--brand-strong);
}

.hero-greeting-sub {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-soft);
}

.hero-couple {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2.5rem;
}

.hero-avatar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
}

.hero-avatar {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  object-fit: cover;
  border: 4px solid #fff;
  box-shadow: 0 8px 20px rgb(67 82 75 / 0.14);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.hero-avatar:hover {
  transform: scale(1.05);
  box-shadow: 0 12px 28px rgb(67 82 75 / 0.2);
}

.hero-avatar-placeholder {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: var(--brand);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 3rem;
  font-weight: 800;
  color: #fff;
  border: 4px solid #fff;
  box-shadow: 0 8px 20px rgb(128 62 85 / 0.18);
}

.hero-avatar-name {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-main);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hero-heart {
  display: grid;
  place-items: center;
  color: var(--brand);
}

.hero-together {
  margin: 0;
  font-size: 1rem;
  color: var(--text-main);
  font-weight: 600;
}

.hero-days {
  font-size: 1.4rem;
  font-weight: 800;
  color: var(--brand-strong);
  margin: 0 0.15rem;
}

.relationship-summary {
  display: grid;
  gap: 1.15rem;
  padding: 1.2rem 1.35rem;
}

.guest-summary {
  border-radius: var(--radius-card);
}

.relationship-summary-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.relationship-summary-label {
  margin: 0;
  color: var(--text-soft);
  font-size: 0.78rem;
  font-weight: 700;
}

.relationship-summary h2 {
  margin: 0.28rem 0 0;
  color: var(--text-main);
  font-size: 1.45rem;
}

.relationship-summary-icon {
  color: var(--brand);
}

.relationship-summary-body {
  display: flex;
  align-items: baseline;
}

.relationship-summary .love-timer {
  margin-top: 0;
}

.focus-section {
  display: grid;
  gap: 1rem;
}

.focus-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.9rem;
}

.focus-card {
  position: relative;
  min-height: 136px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.85rem;
  padding: 1rem;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--surface-raised);
  text-decoration: none;
  color: var(--text-main);
  box-shadow: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.focus-card:hover {
  transform: translateY(-2px);
  border-color: var(--focus-color);
  box-shadow: 0 10px 20px rgb(39 57 50 / 0.09);
}

.focus-card--content {
  --focus-color: #4d8798;
  --focus-wash: #e3f0f4;
}

.focus-card--memories {
  --focus-color: #b34f72;
  --focus-wash: #fbe5ed;
}

.focus-card--messages {
  --focus-color: #3e857b;
  --focus-wash: #e2f2ed;
}

.focus-card--cottage {
  --focus-color: #aa7a36;
  --focus-wash: #f8efd9;
}

.focus-card-icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  color: var(--focus-color);
  border-radius: 12px;
  background: var(--focus-wash);
}

.focus-card-copy {
  min-width: 0;
}

.focus-card-label {
  margin: 0;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0;
  color: var(--focus-color);
}

.focus-card h3 {
  margin: 0.22rem 0 0;
  font-size: 1rem;
  line-height: 1.35;
}

.focus-card-desc {
  margin: 0.38rem 0 0;
  font-size: 0.8rem;
  line-height: 1.55;
  color: var(--text-soft);
}

.focus-card-arrow {
  color: var(--text-soft);
}

.summary-link {
  font-size: 0.78rem;
  color: var(--brand-strong);
  text-decoration: none;
}

@media (max-width: 900px) {
  .focus-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .hero-couple {
    gap: 1.5rem;
  }

  .hero-avatar,
  .hero-avatar-placeholder {
    width: 90px;
    height: 90px;
  }

  .hero-avatar-placeholder {
    font-size: 2.2rem;
  }

  .hero-greeting-text {
    font-size: 1.35rem;
  }

  .hero-heart {
    font-size: 2rem;
  }

  .focus-grid {
    grid-template-columns: 1fr;
  }
}
</style>
