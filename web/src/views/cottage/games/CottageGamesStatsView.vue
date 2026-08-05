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
  <div class="content-section games-stats">
    <article class="glass-card section-block stats-head">
      <div class="head-row">
        <router-link to="/cottage/games" class="back-link">← 一起玩</router-link>
        <h2>战绩总览</h2>
      </div>
      <p class="stats-desc">{{ t("cottageGames.stats.desc") }}</p>
    </article>

    <section v-if="loading" class="glass-card section-block loading">
      {{ t("cottageGames.stats.loading") }}
    </section>

    <template v-else>
      <section v-if="hasAnyMatch" class="glass-card section-block summary">
        <div class="summary-grid">
          <div class="summary-card me">
            <p class="summary-label">{{ myName }}</p>
            <p class="summary-value">{{ myTotalWins }}<span class="unit"> {{ t("cottageGames.stats.winUnit") }}</span></p>
            <p class="summary-sub">{{ t("cottageGames.stats.winRate") }} {{ myWinRate }}%</p>
          </div>
          <div class="summary-card draw">
            <p class="summary-label">{{ t("cottageGames.stats.drawLabel") }}</p>
            <p class="summary-value">{{ totalDraws }}<span class="unit"> {{ t("cottageGames.stats.gameUnit") }}</span></p>
            <p class="summary-sub">{{ t("cottageGames.stats.totalGames", { n: totalGames }) }}</p>
          </div>
          <div class="summary-card partner">
            <p class="summary-label">{{ partnerName }}</p>
            <p class="summary-value">{{ partnerTotalWins }}<span class="unit"> {{ t("cottageGames.stats.winUnit") }}</span></p>
            <p class="summary-sub">{{ t("cottageGames.stats.winRate") }} {{ partnerWinRate }}%</p>
          </div>
        </div>
      </section>

      <section v-if="hasAnyMatch" class="glass-card section-block table-block">
        <h3 class="block-title">{{ t("cottageGames.stats.breakdown") }}</h3>
        <div class="table-scroll">
          <table class="stats-table">
            <thead>
              <tr>
                <th class="col-game">游戏</th>
                <th class="col-num">{{ myName }}</th>
                <th class="col-num">{{ partnerName }}</th>
                <th class="col-num">平</th>
                <th class="col-num">总数</th>
                <th class="col-rate">我方胜率</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.key">
                <td class="col-game">
                  <router-link :to="row.to" class="game-link">{{ row.title }}</router-link>
                </td>
                <td class="col-num">{{ row.myWins }}</td>
                <td class="col-num">{{ row.partnerWins }}</td>
                <td class="col-num">{{ row.draws }}</td>
                <td class="col-num">{{ row.total }}</td>
                <td class="col-rate">
                  <div class="rate-bar">
                    <div class="rate-fill" :style="{ width: row.myRatePct + '%' }"></div>
                    <span class="rate-text">{{ row.myRatePct }}%</span>
                  </div>
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <td class="col-game">合计</td>
                <td class="col-num">{{ myTotalWins }}</td>
                <td class="col-num">{{ partnerTotalWins }}</td>
                <td class="col-num">{{ totalDraws }}</td>
                <td class="col-num">{{ totalGames }}</td>
                <td class="col-rate">{{ myWinRate }}%</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <section v-if="recent.length" class="glass-card section-block recent">
        <h3 class="block-title">最近对局</h3>
        <ul class="recent-list">
          <li v-for="m in recent" :key="m.gmid" class="recent-item">
            <span class="recent-game">{{ gameName(m.game_key) }}</span>
            <span class="recent-result" :class="resultClass(m)">{{ resultText(m) }}</span>
            <span class="recent-time">{{ shortTime(m.created_at) }}</span>
          </li>
        </ul>
      </section>

      <section v-if="!hasAnyMatch" class="glass-card section-block empty">
        {{ t("cottageGames.stats.empty") }}
        <router-link to="/cottage/games" class="empty-link">{{ t("cottageGames.stats.backToGames") }}</router-link>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchDrawMatches, fetchGameMatches, fetchMe } from "../../../lib/api";
import { t, getLocale } from "../../../locales";

const GAMES = [
  { key: "gomoku", to: "/cottage/games/gomoku", kind: "game" },
  { key: "tictactoe", to: "/cottage/games/tictactoe", kind: "game" },
  { key: "reversi", to: "/cottage/games/reversi", kind: "game" },
  { key: "memory", to: "/cottage/games/memory", kind: "game" },
  { key: "linklink", to: "/cottage/games/linklink", kind: "game" },
  { key: "draw", to: "/cottage/games/draw", kind: "draw" }
];

const myUid = ref("");
const myName = ref(t("cottageGames.common.me"));
const partnerName = ref(t("cottageGames.common.partner"));
const loading = ref(true);
const rows = ref([]);
const recent = ref([]);

const hasAnyMatch = computed(() => rows.value.some((r) => r.total > 0));

const myTotalWins = computed(() => rows.value.reduce((s, r) => s + r.myWins, 0));
const partnerTotalWins = computed(() => rows.value.reduce((s, r) => s + r.partnerWins, 0));
const totalDraws = computed(() => rows.value.reduce((s, r) => s + r.draws, 0));
const totalGames = computed(() => rows.value.reduce((s, r) => s + r.total, 0));
const myWinRate = computed(() => ratePct(myTotalWins.value, totalGames.value));
const partnerWinRate = computed(() => ratePct(partnerTotalWins.value, totalGames.value));

function ratePct(wins, total) {
  if (!total) return 0;
  return Math.round((wins / total) * 100);
}

function gameName(key) {
  return t(`cottageGames.gameNames.${key}`) || t("cottageGames.common.fallbackGameName");
}

function resultText(m) {
  if (m.is_draw) return t("cottageGames.common.drawResult");
  const winnerIsMe = m.winner_uid && m.winner_uid === myUid.value;
  const reason = m.end_reason === "surrender" ? t("cottageGames.common.surrenderSuffix") : "";
  return winnerIsMe ? t("cottageGames.common.youWon") + reason : t("cottageGames.common.partnerWon", { name: partnerName.value }) + reason;
}

function resultClass(m) {
  if (m.is_draw) return "draw";
  return m.winner_uid === myUid.value ? "win" : "lose";
}

function shortTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(getLocale(), { month: "numeric", day: "numeric" }) +
      " " + d.toLocaleTimeString(getLocale(), { hour: "2-digit", minute: "2-digit" });
  } catch (_) {
    return "";
  }
}

async function loadOne(g) {
  try {
    const data = g.kind === "draw"
      ? await fetchDrawMatches(50)
      : await fetchGameMatches(g.key, 50);
    const stats = data.stats || [];
    const myStat = stats.find((s) => s.uid === myUid.value) || { wins: 0 };
    const partnerStat = stats.find((s) => s.uid !== myUid.value) || { wins: 0 };
    const draws = data.draws || 0;
    const items = data.items || [];

    // Learn partner nickname from stats first, then from a match's player names.
    const partnerFromStats = stats.find((s) => s.uid !== myUid.value);
    if (partnerFromStats && partnerFromStats.nickname) {
      partnerName.value = partnerFromStats.nickname;
    }
    if (items.length) {
      const first = items[0];
      const partnerFromMatch = [first.black_nickname, first.white_nickname]
        .find((n) => n && n !== myName.value);
      if (partnerFromMatch) partnerName.value = partnerFromMatch;
    }

    const myWins = myStat.wins || 0;
    const partnerWins = partnerStat.wins || 0;
    const total = myWins + partnerWins + draws;
    return {
      key: g.key,
      to: g.to,
      myWins,
      partnerWins,
      draws,
      total,
      myRatePct: ratePct(myWins, total),
      items
    };
  } catch (_) {
    return {
      key: g.key, to: g.to,
      myWins: 0, partnerWins: 0, draws: 0, total: 0, myRatePct: 0, items: []
    };
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    const me = await fetchMe();
    myUid.value = me.uid;
    myName.value = me.nickname || t("cottageGames.common.me");
  } catch (_) {
    /* ignore - stats will be anonymous */
  }
  const results = await Promise.all(GAMES.map(loadOne));
  rows.value = results;
  recent.value = results
    .flatMap((r) => r.items)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 20);
  loading.value = false;
});
</script>

<style scoped>
.games-stats { display: grid; gap: 1rem; }
.stats-head { padding: 1.2rem 1.4rem; }
.head-row {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  flex-wrap: wrap;
}
.back-link {
  color: var(--text-soft);
  text-decoration: none;
  font-size: 0.85rem;
}
.back-link:hover { color: #e2698f; }
.stats-head h2 { margin: 0; font-size: 1.2rem; color: #2f3754; }
.stats-desc { margin: 0.4rem 0 0; color: var(--text-soft); font-size: 0.85rem; }

.loading { padding: 2rem; text-align: center; color: var(--text-soft); }

.summary { padding: 1.2rem 1.4rem; }
.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0.8rem;
}
.summary-card {
  border-radius: 14px;
  padding: 0.9rem 1rem;
  text-align: center;
  background: rgba(255, 255, 255, 0.55);
}
.summary-card.me { background: rgba(100, 112, 196, 0.12); }
.summary-card.partner { background: rgba(226, 105, 143, 0.12); }
.summary-card.draw { background: rgba(148, 163, 184, 0.14); }
.summary-label { margin: 0; font-size: 0.8rem; color: var(--text-soft); }
.summary-value {
  margin: 0.3rem 0 0.1rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: #2f3754;
}
.summary-card.me .summary-value { color: #6470c4; }
.summary-card.partner .summary-value { color: #e2698f; }
.summary-value .unit { font-size: 0.85rem; font-weight: 500; color: var(--text-soft); }
.summary-sub { margin: 0; font-size: 0.74rem; color: var(--text-soft); }

.table-block { padding: 1rem 1.2rem; }
.block-title { margin: 0 0 0.7rem; font-size: 0.95rem; color: #2f3754; }
.table-scroll { overflow-x: auto; }
.stats-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
}
.stats-table th,
.stats-table td {
  padding: 0.55rem 0.6rem;
  text-align: center;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}
.stats-table th {
  color: var(--text-soft);
  font-weight: 600;
  font-size: 0.76rem;
  background: rgba(148, 163, 184, 0.08);
}
.stats-table tfoot td {
  font-weight: 700;
  color: #2f3754;
  border-top: 2px solid rgba(148, 163, 184, 0.3);
  border-bottom: none;
}
.col-game { text-align: left; }
.col-num, .col-rate { text-align: center; }
.game-link { color: #6470c4; text-decoration: none; font-weight: 600; }
.game-link:hover { color: #e2698f; }

.rate-bar {
  position: relative;
  width: 100%;
  min-width: 80px;
  height: 18px;
  background: rgba(148, 163, 184, 0.18);
  border-radius: 9px;
  overflow: hidden;
}
.rate-fill {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  background: linear-gradient(90deg, #8f9bff, #6470c4);
  border-radius: 9px;
  transition: width 0.3s ease;
}
.rate-text {
  position: relative;
  z-index: 1;
  font-size: 0.72rem;
  font-weight: 600;
  color: #2f3754;
  line-height: 18px;
}

.recent { padding: 1rem 1.2rem; }
.recent-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.4rem; }
.recent-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.84rem;
  padding: 0.4rem 0.1rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.25);
}
.recent-item:last-child { border-bottom: none; }
.recent-game {
  font-size: 0.7rem;
  color: #6470c4;
  background: rgba(100, 112, 196, 0.12);
  border-radius: 6px;
  padding: 0.1rem 0.4rem;
  white-space: nowrap;
}
.recent-result { flex: 1; color: #3d4665; }
.recent-result.win { color: #16a34a; }
.recent-result.lose { color: #d6455f; }
.recent-result.draw { color: #94a3b8; }
.recent-time { color: var(--text-soft); font-size: 0.76rem; white-space: nowrap; }

.empty {
  padding: 2rem 1.4rem;
  text-align: center;
  color: var(--text-soft);
  display: grid;
  gap: 0.6rem;
  justify-items: center;
}
.empty-link { color: #e2698f; text-decoration: none; font-weight: 600; }

@media (max-width: 560px) {
  .summary-grid { grid-template-columns: 1fr; }
}
</style>
