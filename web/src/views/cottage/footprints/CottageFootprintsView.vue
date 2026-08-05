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
  <div class="content-section cottage-footprints">
    <div class="fp-header">
      <h2>{{ t('cottageFootprints.title') }}</h2>
      <span class="fp-sub">{{ t('cottageFootprints.subtitle') }}</span>
    </div>

    <!-- 统计 -->
    <section class="glass-card section-block fp-stats">
      <div class="fp-stat">
        <span class="fp-stat-num">{{ data.total_cities }}</span>
        <span class="fp-stat-lbl">{{ t('cottageFootprints.citiesLabel') }}</span>
      </div>
      <div class="fp-stat">
        <span class="fp-stat-num">{{ data.total_checkins }}</span>
        <span class="fp-stat-lbl">{{ t('cottageFootprints.checkinsLabel') }}</span>
      </div>
    </section>

    <p v-if="loading" class="fp-empty">加载中…</p>
    <p v-else-if="!data.cities.length" class="fp-empty">
      还没有带定位的报备～去
      <router-link to="/cottage/check-in" class="fp-inline-link">报备</router-link>
      时打开定位，足迹就会出现在这里。
    </p>

    <!-- 城市列表 -->
    <section v-if="data.cities.length" class="fp-cities">
      <article v-for="(c, i) in data.cities" :key="c.city" class="fp-city glass-card">
        <span class="fp-rank" :class="{ top: i === 0 }">{{ i + 1 }}</span>
        <div class="fp-city-body">
          <p class="fp-city-name">📍 {{ c.city }}</p>
          <div class="fp-city-bar">
            <div class="fp-city-fill" :style="{ width: barWidth(c.count) + '%' }"></div>
          </div>
          <p class="fp-city-meta">
            {{ c.count }} 次 · 最近 {{ formatDate(c.last_at) }}
          </p>
        </div>
      </article>
    </section>

    <!-- 最近足迹 -->
    <section v-if="data.recent.length" class="glass-card section-block fp-recent">
      <h3 class="fp-recent-title">{{ t('cottageFootprints.recentTitle') }}</h3>
      <ul class="fp-timeline">
        <li v-for="(r, i) in data.recent" :key="i" class="fp-tl-item">
          <span class="fp-tl-dot"></span>
          <span class="fp-tl-city">{{ r.city }}</span>
          <span class="fp-tl-meta">{{ r.author_nickname }} · {{ formatDate(r.created_at) }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from "vue";
import { fetchFootprints } from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

const showMessage = inject("showMessage", () => {});

const data = reactive({ cities: [], total_cities: 0, total_checkins: 0, recent: [] });
const loading = ref(true);

function barWidth(count) {
  const max = data.cities.reduce((m, c) => Math.max(m, c.count), 0);
  return max > 0 ? Math.max(6, Math.round((count / max) * 100)) : 0;
}
function formatDate(raw) {
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return String(raw).slice(0, 10);
  return d.toLocaleDateString(undefined);
}

async function load() {
  loading.value = true;
  try {
    const res = await fetchFootprints();
    data.cities = res.cities || [];
    data.total_cities = res.total_cities || 0;
    data.total_checkins = res.total_checkins || 0;
    data.recent = res.recent || [];
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.cottage-footprints { display: grid; gap: 1rem; }
.fp-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.6rem;
  padding: 0.2rem 0.2rem 0;
}
.fp-header h2 { margin: 0; font-size: 1.4rem; color: #2f3754; }
.fp-sub { font-size: 0.82rem; color: var(--text-soft); }

.fp-stats { display: flex; gap: 1.5rem; }
.fp-stat { display: grid; gap: 0.15rem; }
.fp-stat-num { font-size: 1.6rem; font-weight: 700; color: #2f3754; }
.fp-stat-lbl { font-size: 0.78rem; color: var(--text-soft); }

.fp-empty { text-align: center; color: var(--text-soft); font-size: 0.9rem; padding: 1.5rem 0; }
.fp-inline-link { color: #7c3aed; text-decoration: none; }

.fp-cities { display: grid; gap: 0.7rem; }
.fp-city { display: flex; align-items: center; gap: 0.8rem; padding: 0.85rem 1.05rem; border-radius: 14px; }
.fp-rank {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 700;
  color: #6d77a8;
  background: rgba(148, 163, 184, 0.2);
}
.fp-rank.top { color: #fff; background: linear-gradient(135deg, #ff8ab5, #8f9bff); }
.fp-city-body { flex: 1 1 auto; min-width: 0; display: grid; gap: 0.3rem; }
.fp-city-name { margin: 0; font-size: 0.96rem; font-weight: 600; color: #2f3754; word-break: break-word; }
.fp-city-bar { height: 7px; border-radius: 999px; background: rgba(148, 163, 184, 0.22); overflow: hidden; }
.fp-city-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #f9a8d4, #a78bfa); }
.fp-city-meta { margin: 0; font-size: 0.76rem; color: var(--text-soft); }

.fp-recent { display: grid; gap: 0.6rem; }
.fp-recent-title { margin: 0; font-size: 1rem; color: #2f3754; }
.fp-timeline { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.55rem; }
.fp-tl-item { display: flex; align-items: center; gap: 0.6rem; font-size: 0.84rem; }
.fp-tl-dot { flex: 0 0 auto; width: 9px; height: 9px; border-radius: 50%; background: #a78bfa; }
.fp-tl-city { color: #2f3754; font-weight: 600; }
.fp-tl-meta { color: var(--text-soft); font-size: 0.76rem; }
</style>
