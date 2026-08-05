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
  <article class="glass-card section-block search">
    <div class="search-tabs">
      <button
        v-for="tab in mainTabs"
        :key="tab.key"
        type="button"
        class="search-tab"
        :class="{ 'search-tab--active': activeTab === tab.key }"
        @click="switchMainTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <p v-if="loginRequired && activeTab !== 'history'" class="search-empty">
      {{ t("listenSearch.loginRequired") }}
    </p>
    <p v-else-if="errorMsg" class="search-error">{{ errorMsg }}</p>

    <!-- Search -->
    <div v-if="activeTab === 'search'" class="search-pane">
      <input
        v-model="keyword"
        class="search-input"
        :placeholder="t('listenSearch.searchPlaceholder')"
        @input="onKeywordInput"
        @keydown.enter.prevent="runSearch"
      />
      <p v-if="loading" class="search-empty">{{ t("listenSearch.searching") }}</p>
      <p v-else-if="!searchItems.length && keyword.trim()" class="search-empty">
        {{ t("listenSearch.noResults") }}
      </p>
      <ListenSongList
        v-else
        :songs="searchItems"
        @append-to-queue="$emit('append-to-queue', $event)"
        @play-now="$emit('play-now', $event)"
      />
    </div>

    <!-- My playlists -->
    <div v-else-if="activeTab === 'playlists' && !loginRequired" class="search-pane">
      <p v-if="loadingPlaylists" class="search-empty">{{ t("listenSearch.loadingPlaylists") }}</p>
      <template v-else-if="!selectedPlaylist">
        <p v-if="!playlists.length" class="search-empty">{{ t("listenSearch.noPlaylists") }}</p>
        <ul v-else class="playlist-grid">
          <li
            v-for="p in playlists"
            :key="p.playlist_id"
            class="playlist-item"
            @click="openPlaylist(p, 'mine')"
          >
            <img v-if="p.cover_url" :src="p.cover_url" alt="" class="playlist-cover" referrerpolicy="no-referrer" />
            <div v-else class="playlist-cover playlist-cover--placeholder">♪</div>
            <div class="playlist-meta">
              <span class="playlist-name">{{ p.name }}</span>
              <span class="playlist-count">{{ t("listenSearch.trackCount", { n: p.track_count }) }}</span>
            </div>
          </li>
        </ul>
      </template>
      <template v-else>
        <button type="button" class="action-btn" @click="closePlaylist">{{ t("listenSearch.backToPlaylists") }}</button>
        <p v-if="loadingTracks" class="search-empty">{{ t("listenSearch.loadingTracks") }}</p>
        <ListenSongList
          v-else
          :songs="playlistTracks"
          @append-to-queue="$emit('append-to-queue', $event)"
          @play-now="$emit('play-now', $event)"
        />
      </template>
    </div>

    <!-- Discover -->
    <div v-else-if="activeTab === 'discover' && !loginRequired" class="search-pane">
      <div class="discover-subtabs">
        <button
          v-for="sub in discoverTabs"
          :key="sub.key"
          type="button"
          class="discover-subtab"
          :class="{ active: discoverTab === sub.key }"
          @click="switchDiscoverTab(sub.key)"
        >
          {{ sub.label }}
        </button>
      </div>

      <p v-if="loadingDiscover" class="search-empty">{{ t("listenSearch.loading") }}</p>

      <template v-else-if="discoverTab === 'recommend'">
        <p v-if="!discoverSongs.length" class="search-empty">{{ t("listenSearch.noRecommend") }}</p>
        <ListenSongList
          v-else
          :songs="discoverSongs"
          @append-to-queue="$emit('append-to-queue', $event)"
          @play-now="$emit('play-now', $event)"
        />
      </template>

      <template v-else-if="discoverTab === 'playlists'">
        <template v-if="!selectedPlaylist">
          <p v-if="!discoverPlaylists.length" class="search-empty">{{ t("listenSearch.noRecommendPlaylists") }}</p>
          <ul v-else class="playlist-grid">
            <li
              v-for="p in discoverPlaylists"
              :key="p.playlist_id"
              class="playlist-item"
              @click="openPlaylist(p, 'discover')"
            >
              <img v-if="p.cover_url" :src="p.cover_url" alt="" class="playlist-cover" referrerpolicy="no-referrer" />
              <div v-else class="playlist-cover playlist-cover--placeholder">♪</div>
              <div class="playlist-meta">
                <span class="playlist-name">{{ p.name }}</span>
                <span class="playlist-count">{{ t("listenSearch.trackCount", { n: p.track_count }) }}</span>
              </div>
            </li>
          </ul>
        </template>
        <template v-else>
          <button type="button" class="action-btn" @click="closePlaylist">{{ t("listenSearch.backToRecommendPlaylists") }}</button>
          <p v-if="loadingTracks" class="search-empty">{{ t("listenSearch.loadingTracks") }}</p>
          <ListenSongList
            v-else
            :songs="playlistTracks"
            @append-to-queue="$emit('append-to-queue', $event)"
            @play-now="$emit('play-now', $event)"
          />
        </template>
      </template>

      <template v-else-if="discoverTab === 'toplist'">
        <template v-if="!selectedToplist">
          <p v-if="!toplists.length" class="search-empty">{{ t("listenSearch.noToplists") }}</p>
          <ul v-else class="playlist-grid">
            <li
              v-for="chart in toplists"
              :key="chart.toplist_id"
              class="playlist-item"
              @click="openToplist(chart)"
            >
              <img v-if="chart.cover_url" :src="chart.cover_url" alt="" class="playlist-cover" referrerpolicy="no-referrer" />
              <div v-else class="playlist-cover playlist-cover--placeholder">♪</div>
              <div class="playlist-meta">
                <span class="playlist-name">{{ chart.name }}</span>
                <span class="playlist-count">{{ chart.update_frequency || t("listenSearch.officialChart") }}</span>
              </div>
            </li>
          </ul>
        </template>
        <template v-else>
          <button type="button" class="action-btn" @click="closeToplist">{{ t("listenSearch.backToToplists") }}</button>
          <p v-if="loadingTracks" class="search-empty">{{ t("listenSearch.loadingTracks") }}</p>
          <ListenSongList
            v-else
            :songs="playlistTracks"
            @append-to-queue="$emit('append-to-queue', $event)"
            @play-now="$emit('play-now', $event)"
          />
        </template>
      </template>
    </div>

    <!-- History -->
    <div v-else-if="activeTab === 'history'" class="search-pane">
      <p v-if="loadingHistory" class="search-empty">{{ t("listenSearch.loadingHistory") }}</p>
      <p v-else-if="!historyItems.length" class="search-empty">{{ t("listenSearch.noHistory") }}</p>
      <ul v-else class="history-list">
        <li v-for="item in historyItems" :key="`${item.song_id}-${item.played_at_ms}`" class="history-item">
          <div class="history-main">
            <span class="search-item-name">{{ item.name || item.song_id }}</span>
            <span class="search-item-artists">{{ (item.artists || []).join(", ") }}</span>
            <span class="history-time">{{ formatPlayedAt(item.played_at_ms) }}</span>
          </div>
          <div class="search-item-actions">
            <button type="button" class="action-btn" @click="$emit('append-to-queue', item)">{{ t("listenSearch.addToQueue") }}</button>
            <button type="button" class="action-btn action-btn--primary" @click="$emit('play-now', item)">{{ t("listenSearch.playNow") }}</button>
          </div>
        </li>
      </ul>
    </div>
  </article>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import {
  listenDiscoverPlaylists,
  listenDiscoverPlaylistTracks,
  listenDiscoverRecommendSongs,
  listenDiscoverToplist,
  listenDiscoverToplistTracks,
  listenHistory,
  listenPlaylists,
  listenPlaylistTracks,
  listenSearch
} from "../../../lib/api";
import ListenSongList from "./ListenSongList.vue";

const { t } = useI18n();

const props = defineProps({
  meLoggedIn: { type: Boolean, default: false }
});

defineEmits(["append-to-queue", "play-now"]);

const mainTabs = computed(() => [
  { key: "search", label: t("listenSearch.tabSearch") },
  { key: "discover", label: t("listenSearch.tabDiscover") },
  { key: "playlists", label: t("listenSearch.tabPlaylists") },
  { key: "history", label: t("listenSearch.tabHistory") }
]);

const discoverTabs = computed(() => [
  { key: "recommend", label: t("listenSearch.tabRecommend") },
  { key: "playlists", label: t("listenSearch.tabRecommendPlaylists") },
  { key: "toplist", label: t("listenSearch.tabToplist") }
]);

const activeTab = ref("search");
const discoverTab = ref("recommend");
const keyword = ref("");
const searchItems = ref([]);
const loading = ref(false);
const loginRequired = ref(false);
const errorMsg = ref("");

const playlists = ref([]);
const loadingPlaylists = ref(false);
const selectedPlaylist = ref(null);
const playlistSource = ref("mine");
const playlistTracks = ref([]);
const loadingTracks = ref(false);

const discoverSongs = ref([]);
const discoverPlaylists = ref([]);
const toplists = ref([]);
const selectedToplist = ref(null);
const loadingDiscover = ref(false);

const historyItems = ref([]);
const loadingHistory = ref(false);

let searchDebounce = null;

function formatPlayedAt(ms) {
  if (!ms) return "";
  const d = new Date(ms);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function onKeywordInput() {
  if (searchDebounce) clearTimeout(searchDebounce);
  searchDebounce = setTimeout(runSearch, 300);
}

async function runSearch() {
  errorMsg.value = "";
  if (!keyword.value.trim()) {
    searchItems.value = [];
    return;
  }
  loading.value = true;
  try {
    const data = await listenSearch({
      keyword: keyword.value.trim(),
      page: 1,
      page_size: 20
    });
    searchItems.value = data.items || [];
    loginRequired.value = false;
  } catch (e) {
    handleError(e);
  } finally {
    loading.value = false;
  }
}

function switchMainTab(key) {
  activeTab.value = key;
  errorMsg.value = "";
  if (key === "playlists" && !playlists.value.length && !loginRequired.value) {
    loadPlaylists();
  } else if (key === "discover" && !loginRequired.value) {
    loadDiscover();
  } else if (key === "history") {
    loadHistory();
  }
}

function switchDiscoverTab(key) {
  discoverTab.value = key;
  closePlaylist();
  closeToplist();
  if (!loginRequired.value) {
    loadDiscover();
  }
}

async function loadPlaylists() {
  loadingPlaylists.value = true;
  errorMsg.value = "";
  try {
    const data = await listenPlaylists();
    playlists.value = data.items || [];
    loginRequired.value = false;
  } catch (e) {
    handleError(e);
  } finally {
    loadingPlaylists.value = false;
  }
}

async function openPlaylist(p, source) {
  selectedPlaylist.value = p;
  playlistSource.value = source;
  loadingTracks.value = true;
  playlistTracks.value = [];
  try {
    const fetchTracks =
      source === "discover" ? listenDiscoverPlaylistTracks : listenPlaylistTracks;
    const data = await fetchTracks(p.playlist_id, { page: 1, page_size: 100 });
    playlistTracks.value = data.items || [];
  } catch (e) {
    handleError(e);
  } finally {
    loadingTracks.value = false;
  }
}

function closePlaylist() {
  selectedPlaylist.value = null;
  playlistTracks.value = [];
}

async function loadDiscover() {
  loadingDiscover.value = true;
  errorMsg.value = "";
  try {
    if (discoverTab.value === "recommend") {
      const data = await listenDiscoverRecommendSongs();
      discoverSongs.value = data.items || [];
    } else if (discoverTab.value === "playlists") {
      const data = await listenDiscoverPlaylists({ limit: 12 });
      discoverPlaylists.value = data.items || [];
    } else if (discoverTab.value === "toplist") {
      const data = await listenDiscoverToplist();
      toplists.value = data.items || [];
    }
    loginRequired.value = false;
  } catch (e) {
    handleError(e);
  } finally {
    loadingDiscover.value = false;
  }
}

async function openToplist(chart) {
  selectedToplist.value = chart;
  loadingTracks.value = true;
  playlistTracks.value = [];
  try {
    const data = await listenDiscoverToplistTracks(chart.toplist_id, { page: 1, page_size: 100 });
    playlistTracks.value = data.items || [];
  } catch (e) {
    handleError(e);
  } finally {
    loadingTracks.value = false;
  }
}

function closeToplist() {
  selectedToplist.value = null;
  playlistTracks.value = [];
}

async function loadHistory() {
  loadingHistory.value = true;
  errorMsg.value = "";
  try {
    const data = await listenHistory({ limit: 50 });
    historyItems.value = data.items || [];
  } catch (e) {
    errorMsg.value = e?.response?.data?.detail?.message || t("listenSearch.errLoadHistory");
  } finally {
    loadingHistory.value = false;
  }
}

function handleError(e) {
  const detail = e?.response?.data?.detail || {};
  if (detail.code === "netease_login_required" || e?.response?.status === 409) {
    loginRequired.value = true;
    errorMsg.value = "";
  } else {
    errorMsg.value = detail.message || t("listenSearch.errRequest");
  }
}

watch(
  () => props.meLoggedIn,
  (logged) => {
    if (logged) {
      loginRequired.value = false;
      errorMsg.value = "";
    }
  }
);
</script>

<style scoped>
.search {
  padding: 1.2rem 1.4rem;
  display: grid;
  gap: 0.85rem;
}

.search-tabs {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.search-tab {
  min-height: 36px;
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(255, 255, 255, 0.7);
  color: #3d4665;
  font-size: 0.84rem;
  cursor: pointer;
}

.search-tab--active {
  border-color: transparent;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
}

.discover-subtabs {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.discover-subtab {
  min-height: 32px;
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.65);
  color: #64748b;
  font-size: 0.8rem;
  cursor: pointer;
}

.discover-subtab.active {
  background: rgba(143, 155, 255, 0.18);
  color: #4f5d8c;
  border-color: rgba(143, 155, 255, 0.45);
}

.search-input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 12px;
  padding: 0.65rem 0.85rem;
  font-size: 0.9rem;
  background: rgba(255, 255, 255, 0.85);
}

.search-empty,
.search-error {
  margin: 0;
  text-align: center;
  color: #94a3b8;
  font-size: 0.86rem;
  padding: 0.6rem 0;
}

.search-error {
  color: #dc2626;
}

:deep(.search-list) {
  max-height: none;
}

.history-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.4rem;
  max-height: 380px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.7rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
}

.history-main {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 0.15rem;
}

.history-time {
  color: #94a3b8;
  font-size: 0.72rem;
}

.search-item-name {
  color: #2f3754;
  font-size: 0.88rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.search-item-artists {
  color: #94a3b8;
  font-size: 0.76rem;
}

.action-btn {
  min-height: 36px;
  padding: 0.32rem 0.65rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(255, 255, 255, 0.85);
  color: #3d4665;
  font-size: 0.78rem;
  cursor: pointer;
}

.action-btn--primary {
  border-color: transparent;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
}

.playlist-grid {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.7rem;
  max-height: 380px;
  overflow-y: auto;
}

.playlist-item {
  cursor: pointer;
  display: grid;
  gap: 0.4rem;
  padding: 0.4rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
  transition: transform 0.12s ease;
}

.playlist-item:hover {
  transform: translateY(-2px);
}

.playlist-cover {
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: 8px;
  object-fit: cover;
  background: rgba(148, 163, 184, 0.18);
}

.playlist-cover--placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.6rem;
  color: rgba(148, 163, 184, 0.7);
}

.playlist-meta {
  display: flex;
  flex-direction: column;
}

.playlist-name {
  font-size: 0.84rem;
  color: #2f3754;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.playlist-count {
  font-size: 0.74rem;
  color: #94a3b8;
}

@media (max-width: 768px) {
  .history-item {
    flex-direction: column;
    align-items: stretch;
  }
  .search-item-actions {
    justify-content: flex-end;
  }
  .playlist-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
