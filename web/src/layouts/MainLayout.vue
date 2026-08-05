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
  <div class="page-shell">
    <header class="top-nav">
      <div class="top-nav-inner">
        <router-link to="/" class="top-nav-logo">
          <span class="top-nav-logo-main">{{ t('layout.appName') }}</span>
          <span class="top-nav-logo-sub">{{ t('layout.appSubtitle') }}</span>
        </router-link>

        <nav class="top-nav-links" :aria-label="t('nav.home')">
          <router-link
            v-for="tab in primaryTabs"
            :key="tab.name"
            :to="tab.path"
            :class="['top-tab', isTabActive(tab) && 'top-tab--active']"
            @click="closeMobileNav"
          >
            {{ tab.label }}
          </router-link>
        </nav>

        <div class="top-nav-actions">
          <LanguageSwitcher />
          <router-link
            v-if="canManageContent"
            to="/privacy"
            class="nav-icon-link"
            :aria-label="t('nav.privacyCenter')"
            :title="t('nav.privacyCenter')"
          >
            <ShieldCheck :size="19" :stroke-width="2" aria-hidden="true" />
          </router-link>
          <button
            type="button"
            class="nav-menu-button"
            :aria-expanded="mobileNavOpen"
            aria-controls="mobile-primary-navigation"
            :aria-label="mobileNavOpen ? t('nav.closeNav') : t('nav.openNav')"
            :title="mobileNavOpen ? t('nav.closeNav') : t('nav.openNav')"
            @click="mobileNavOpen = !mobileNavOpen"
          >
            <X v-if="mobileNavOpen" :size="20" :stroke-width="2" aria-hidden="true" />
            <Menu v-else :size="20" :stroke-width="2" aria-hidden="true" />
          </button>
          <div class="top-nav-user">
            <router-link v-if="canManageContent" to="/admin" class="top-nav-link text-decoration-none">{{ t('nav.admin') }}</router-link>
            <button v-if="token" class="top-nav-link" @click="handleLogout">{{ t('nav.logout') }}</button>
            <router-link v-else to="/login" class="top-nav-link text-decoration-none">{{ t('nav.login') }}</router-link>
          </div>
        </div>
      </div>

      <nav v-if="mobileNavOpen" id="mobile-primary-navigation" class="mobile-nav-panel" aria-label="Mobile primary navigation">
        <router-link
          v-for="tab in primaryTabs"
          :key="tab.name"
          :to="tab.path"
          :class="['mobile-nav-link', isTabActive(tab) && 'mobile-nav-link--active']"
          @click="closeMobileNav"
        >
          {{ tab.label }}
        </router-link>
      </nav>
    </header>

    <main class="page-main">
      <section v-if="route.name === 'dashboard' && !canManageContent" class="hero-banner">
        <div class="hero-content">
          <p class="hero-kicker">{{ t('layout.heroKicker') }}</p>
          <h1>{{ t('layout.heroTitle') }}</h1>
          <p class="hero-desc">
            {{ t('layout.heroDesc') }}
          </p>
        </div>
      </section>

      <router-view />

      <p
        v-if="message"
        :class="['global-message', `global-message--${message.tone}`]"
        :role="message.tone === 'error' ? 'alert' : 'status'"
        :aria-live="message.tone === 'error' ? 'assertive' : 'polite'"
      >
        {{ message.text }}
      </p>

      <footer class="legal-footer">
        <router-link to="/licenses">{{ t('nav.licenses') }}</router-link>
      </footer>
    </main>

    <ListenMiniPlayer v-if="canManageContent" />
  </div>
</template>

<script setup>
import { computed, provide, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { Menu, ShieldCheck, X } from "@lucide/vue";
import { useAuth } from "../stores/auth";
import ListenMiniPlayer from "../views/cottage/listen/ListenMiniPlayer.vue";
import LanguageSwitcher from "../components/LanguageSwitcher.vue";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const { token, canManageContent, logout } = useAuth();

const message = ref(null);
const mobileNavOpen = ref(false);
let messageTimer = null;

function showMessage(text, tone = "info") {
  const msg = String(text || "").trim();
  if (!msg) return;

  message.value = { text: msg, tone };
  clearTimeout(messageTimer);
  messageTimer = setTimeout(() => {
    message.value = null;
  }, 5000);
}

provide("showMessage", showMessage);

const allTabs = computed(() => [
  { name: "dashboard", path: "/", label: t("nav.home") },
  { name: "articles", path: "/articles", label: t("nav.articles") },
  { name: "events", path: "/events", label: t("nav.events") },
  { name: "messages", path: "/messages", label: t("nav.messages") },
  { name: "albums", path: "/albums", label: t("nav.albums") },
  { name: "timeline", path: "/timeline", label: t("nav.timeline") },
  { name: "search", path: "/search", label: t("nav.search") },
  { name: "notifications", path: "/notifications", label: t("nav.notifications"), requiresAuth: true },
  { name: "capsules", path: "/capsules", label: t("nav.capsules"), requiresPartner: true },
  { name: "cottage", path: "/cottage", label: t("nav.cottage"), requiresPartner: true }
]);

function canShowTab(tab) {
  if (tab.requiresPartner && !canManageContent.value) {
    return false;
  }
  if (tab.requiresAuth && !token.value) {
    return false;
  }
  return true;
}

const primaryTabs = computed(() => {
  const names = ["dashboard", "articles", "events", "messages", "cottage"];
  return allTabs.value.filter((tab) => names.includes(tab.name) && canShowTab(tab));
});

const groupedRoutes = {
  dashboard: ["dashboard"],
  articles: ["articles", "article-detail", "article-editor", "search", "albums", "album-detail"],
  events: ["events", "timeline", "capsules"],
  messages: ["messages", "notifications"],
  cottage: [
    "cottage",
    "cottage-check-in",
    "cottage-check-in-history",
    "cottage-listen",
    "cottage-chat",
    "cottage-mood",
    "cottage-questions",
    "cottage-plans",
    "cottage-reminders",
    "cottage-reports",
    "cottage-wishlist",
    "cottage-watch"
  ]
};

function isTabActive(tab) {
  const names = groupedRoutes[tab.name] || [tab.name];
  return names.includes(route.name);
}

function closeMobileNav() {
  mobileNavOpen.value = false;
}

async function handleLogout() {
  const serverEnded = await logout();
  showMessage(
    serverEnded ? t("auth.logoutSuccess") : t("auth.logoutPartialFail"),
    serverEnded ? "info" : "error"
  );
  router.push("/");
}
</script>

<style scoped>
.page-shell {
  min-height: 100vh;
}

.top-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 30;
  backdrop-filter: blur(14px);
  background: rgb(255 255 255 / 0.9);
  border-bottom: 1px solid var(--border-subtle);
}

.top-nav-inner {
  max-width: 1260px;
  margin: 0 auto;
  min-height: 68px;
  padding: 0.65rem 1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.top-nav-logo {
  flex-shrink: 0;
  text-decoration: none;
  display: flex;
  flex-direction: column;
}

.top-nav-logo-main {
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: 0;
  color: var(--text-main);
}

.top-nav-logo-sub {
  font-size: 0.58rem;
  letter-spacing: 0.08em;
  color: var(--text-soft);
}

.top-nav-links {
  flex: 1;
  display: flex;
  gap: 0.45rem;
  min-width: 0;
}

.top-tab {
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  padding: 0.48rem 0.78rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-soft);
  white-space: nowrap;
  cursor: pointer;
  background: transparent;
  text-decoration: none;
  transition: background 0.15s ease, color 0.15s ease;
}

.top-tab:hover {
  color: var(--text-main);
  background: var(--surface-subtle);
}

.top-tab--active {
  color: var(--brand-strong);
  border-color: #efc3d1;
  background: var(--brand-soft);
}

.top-nav-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.top-nav-user {
  flex-shrink: 0;
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.top-nav-link {
  border: 1px solid var(--border-strong);
  background: var(--surface-raised);
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-size: 0.75rem;
  color: var(--text-main);
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
}

.nav-menu-button {
  display: none;
  width: 44px;
  height: 44px;
  align-items: center;
  justify-content: center;
  padding: 0;
  color: var(--text-main);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-control);
  background: var(--surface-raised);
  cursor: pointer;
}

.nav-icon-link {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  color: var(--text-main);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-control);
  background: var(--surface-raised);
  text-decoration: none;
  transition: color 0.15s ease, border-color 0.15s ease, background 0.15s ease;
}

.nav-icon-link:hover,
.nav-icon-link.router-link-active {
  color: var(--brand-strong);
  border-color: #efc3d1;
  background: var(--brand-soft);
}

.mobile-nav-panel {
  display: none;
}

.page-main {
  max-width: 1260px;
  margin: 0 auto;
  padding: 5rem 1rem 2rem;
}

.hero-banner {
  position: relative;
  border-radius: var(--radius-card);
  overflow: hidden;
  min-height: 230px;
  padding: 2rem;
  background: linear-gradient(130deg, #bd5a7d 0%, #d47e98 56%, #72a49b 100%);
  box-shadow: 0 18px 36px rgb(96 64 77 / 0.18);
}

.hero-content {
  color: #fff;
  max-width: 620px;
}

.hero-kicker {
  margin: 0 0 0.6rem;
  letter-spacing: 0;
  font-size: 0.8rem;
  opacity: 0.9;
}

.hero-content h1 {
  margin: 0;
  font-size: 2.45rem;
  line-height: 1.15;
}

.hero-desc {
  margin: 0.9rem 0 0;
  font-size: 0.94rem;
  line-height: 1.65;
  opacity: 0.94;
}

.global-message {
  position: fixed;
  top: 84px;
  right: 1rem;
  z-index: 40;
  max-width: min(420px, calc(100vw - 2rem));
  margin: 0;
  border-radius: var(--radius-control);
  border: 1px solid #b9d9d2;
  background: #edf8f5;
  color: #23685f;
  font-size: 0.84rem;
  padding: 0.72rem 0.85rem;
  box-shadow: 0 12px 24px rgb(39 57 50 / 0.12);
}

.global-message--error {
  border-color: #efb9c8;
  background: #fff2f5;
  color: #9f3f55;
}

.legal-footer {
  padding: 1.8rem 0 0.4rem;
  text-align: center;
  font-size: 0.76rem;
}

.legal-footer a {
  color: #5c6785;
  text-decoration: none;
}

.legal-footer a:hover {
  color: #2f3754;
  text-decoration: underline;
}

@media (max-width: 768px) {
  .page-main {
    padding-top: 5rem;
  }

  .top-nav-inner {
    min-height: 64px;
    padding: 0.55rem 0.75rem;
    gap: 0.55rem;
  }

  .hero-banner {
    min-height: 218px;
    padding: 1.35rem;
  }

  .hero-content h1 {
    font-size: 1.9rem;
  }

  .top-nav-links {
    display: none;
  }

  .top-nav-actions {
    margin-left: auto;
  }

  .top-nav-user {
    gap: 0.4rem;
  }

  .nav-menu-button {
    display: inline-flex;
  }

  .top-nav-link {
    min-height: 42px;
    display: inline-flex;
    align-items: center;
    padding: 0.4rem 0.7rem;
    font-size: 0.74rem;
  }

  .global-message {
    top: 72px;
    right: 0.75rem;
    left: 0.75rem;
    max-width: none;
  }

  .mobile-nav-panel {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.5rem;
    padding: 0.75rem;
    background: rgb(255 255 255 / 0.98);
    border-bottom: 1px solid var(--border-subtle);
    box-shadow: 0 12px 24px rgb(39 57 50 / 0.1);
  }

  .mobile-nav-link {
    min-height: 48px;
    display: flex;
    align-items: center;
    padding: 0 0.75rem;
    color: var(--text-main);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-control);
    background: var(--surface-raised);
    font-size: 0.86rem;
    font-weight: 700;
    text-decoration: none;
  }

  .mobile-nav-link--active {
    color: var(--brand-strong);
    border-color: #efc3d1;
    background: var(--brand-soft);
  }
}

/* Very narrow phones: drop the logo sub-label to give the scrolling tabs room. */
@media (max-width: 380px) {
  .top-nav-logo-sub {
    display: none;
  }
}
</style>
