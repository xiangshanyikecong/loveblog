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
  <div class="admin-shell">
    <aside class="admin-sidebar">
      <div class="sidebar-brand">
        <router-link to="/" class="brand-link">
          <span class="brand-main">{{ t('adminLayout.brandMain') }}</span>
          <span class="brand-sub">Love Node Admin</span>
        </router-link>
      </div>

      <nav class="sidebar-nav">
        <router-link to="/admin" class="nav-item" exact-active-class="nav-item--active">
          {{ t('adminLayout.siteSettings') }}
        </router-link>
        <router-link to="/admin/articles" class="nav-item" active-class="nav-item--active">
          {{ t('adminLayout.articles') }}
        </router-link>
        <router-link to="/admin/albums" class="nav-item" active-class="nav-item--active">
          {{ t('adminLayout.albums') }}
        </router-link>
        <router-link to="/admin/messages" class="nav-item" active-class="nav-item--active">
          {{ t('adminLayout.messages') }}
        </router-link>
        <router-link to="/admin/timeline" class="nav-item" active-class="nav-item--active">
          {{ t('adminLayout.timeline') }}
        </router-link>
        <router-link to="/admin/capsules" class="nav-item" active-class="nav-item--active">
          {{ t('adminLayout.capsules') }}
        </router-link>
        <router-link to="/admin/accounts" class="nav-item" active-class="nav-item--active">
          {{ t('adminLayout.accounts') }}
        </router-link>
        <router-link to="/admin/export" class="nav-item" active-class="nav-item--active">
          {{ t('adminLayout.export') }}
        </router-link>
        <router-link to="/admin/security" class="nav-item" active-class="nav-item--active">
          {{ t('adminLayout.security') }}
        </router-link>
        <router-link to="/admin/recycle-bin" class="nav-item" active-class="nav-item--active">
          {{ t('adminLayout.recycleBin') }}
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <router-link to="/" class="nav-item">
          {{ t('adminLayout.backToFrontend') }}
        </router-link>
      </div>
    </aside>

    <main class="admin-main">
      <header class="admin-header">
        <div class="header-left">
          <h1 class="page-title">{{ t('adminLayout.pageTitle') }}</h1>
        </div>
        <div class="header-right">
          <span class="admin-role">{{ token ? t('adminLayout.loggedIn') : t('adminLayout.loggedOut') }}</span>
          <button class="text-btn" @click="handleLogout">{{ t('adminLayout.logout') }}</button>
        </div>
      </header>

      <div class="admin-content">
        <router-view />
        <p v-if="message" class="global-message">
          {{ message }}
        </p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, provide } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useAuth } from "../stores/auth";

const { t } = useI18n();
const router = useRouter();
const { token, logout } = useAuth();

const message = ref("");

function showMessage(msg) {
  message.value = msg;
  setTimeout(() => {
    if (message.value === msg) {
      message.value = "";
    }
  }, 5000);
}

provide("showMessage", showMessage);

async function handleLogout() {
  await logout();
  router.push("/");
}
</script>

<style scoped>
.admin-shell {
  display: flex;
  height: 100vh;
  background-color: #f4f6f8;
  font-family: "Segoe UI", sans-serif;
  color: #334155;
}

.admin-sidebar {
  width: 250px;
  background-color: #ffffff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
}

.sidebar-brand {
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.brand-link {
  text-decoration: none;
  display: flex;
  flex-direction: column;
}

.brand-main {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
}

.brand-sub {
  font-size: 0.75rem;
  color: #64748b;
  letter-spacing: 0.05em;
  margin-top: 0.2rem;
}

.sidebar-nav {
  padding: 1.5rem 1rem;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.nav-item {
  text-decoration: none;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  color: #475569;
  font-weight: 500;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.nav-item:hover {
  background-color: #f1f5f9;
  color: #0f172a;
}

.nav-item--active {
  background-color: #e0e7ff;
  color: #4338ca;
  font-weight: 600;
}

.sidebar-footer {
  padding: 1.5rem 1rem;
  border-top: 1px solid #e2e8f0;
}

.admin-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.admin-header {
  height: 70px;
  background-color: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2rem;
}

.page-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: #1e293b;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.admin-role {
  font-size: 0.85rem;
  color: #64748b;
}

.text-btn {
  background: transparent;
  border: none;
  color: #ef4444;
  cursor: pointer;
  font-weight: 500;
}

.text-btn:hover {
  text-decoration: underline;
}

.admin-content {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
}

.global-message {
  margin-top: 1rem;
  border-radius: 8px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1e40af;
  padding: 0.75rem 1rem;
  font-size: 0.9rem;
}

@media (max-width: 768px) {
  .admin-shell {
    flex-direction: column;
    height: auto;
    min-height: 100vh;
  }

  .admin-sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid #e2e8f0;
  }

  .sidebar-brand {
    padding: 0.9rem 1rem;
  }

  .sidebar-nav {
    flex-direction: row;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    padding: 0.6rem 0.8rem;
    gap: 0.4rem;
  }

  .sidebar-nav::-webkit-scrollbar {
    display: none;
  }

  .nav-item {
    white-space: nowrap;
    flex-shrink: 0;
    padding: 0.55rem 0.8rem;
  }

  .sidebar-footer {
    display: none;
  }

  .admin-header {
    height: auto;
    padding: 0.8rem 1rem;
  }

  .admin-content {
    padding: 1rem;
  }
}
</style>
