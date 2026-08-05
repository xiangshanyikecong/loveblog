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
  <div class="content-section games-lobby">
    <article class="glass-card section-block lobby-hero">
      <div class="section-header">
        <h2>{{ t("cottageGames.common.playTogether") }}</h2>
        <router-link to="/cottage/games/stats" class="stats-link">{{ t("cottageGames.lobby.statsLink") }}</router-link>
      </div>
      <p class="lobby-desc">{{ t("cottageGames.lobby.desc") }}</p>
    </article>

    <section class="game-grid">
      <router-link
        v-for="g in games"
        :key="g.key"
        :to="g.to"
        class="game-card glass-card"
      >
        <div class="game-card-top">
          <h3 class="game-title">{{ gameTitle(g.key) }}</h3>
          <span class="game-badge" :class="{ live: g.live }">
            {{ g.live ? t("cottageGames.lobby.live") : t("cottageGames.lobby.idle") }}
          </span>
        </div>
        <p class="game-sub">{{ gameDesc(g.key) }}</p>
        <div class="game-foot">
          <span v-if="g.kind !== 'casual'" class="record">
            {{ t("cottageGames.lobby.record") }} {{ g.myWins }} : {{ g.partnerWins }}<span v-if="g.draws"> · {{ t("cottageGames.common.drawLabel") }} {{ g.draws }}</span>
          </span>
          <span v-else class="record">{{ t("cottageGames.lobby.casualRecord") }}</span>
          <span class="enter">{{ t("cottageGames.lobby.enter") }}</span>
        </div>
      </router-link>

    </section>

    <section v-if="recent.length" class="glass-card section-block recent">
      <h3 class="recent-title">{{ t("cottageGames.lobby.recent") }}</h3>
      <ul class="recent-list">
        <li v-for="m in recent" :key="m.gmid" class="recent-item">
          <span class="recent-game">{{ gameName(m.game_key) }}</span>
          <span class="recent-result">{{ resultText(m) }}</span>
          <span class="recent-time">{{ shortTime(m.created_at) }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from "vue";
import { fetchDrawMatches, fetchDrawState, fetchGameMatches, fetchGameState, fetchMe } from "../../../lib/api";
import { parseError } from "../../../utils/helpers";
import { t, getLocale } from "../../../locales";

const showMessage = inject("showMessage", () => {});

const GAME_TITLE_KEYS = {
  gomoku: "cottageGames.gomoku.title",
  tictactoe: "cottageGames.tictactoe.title",
  reversi: "cottageGames.reversi.title",
  memory: "cottageGames.memory.title",
  linklink: "cottageGames.linklink.title",
  draw: "cottageGames.draw.title",
  canvas: "cottageGames.canvas.title"
};

const GAME_DESC_KEYS = {
  gomoku: "cottageGames.lobby.gomokuDesc",
  tictactoe: "cottageGames.lobby.tictactoeDesc",
  reversi: "cottageGames.lobby.reversiDesc",
  memory: "cottageGames.lobby.memoryDesc",
  linklink: "cottageGames.lobby.linklinkDesc",
  draw: "cottageGames.lobby.drawDesc",
  canvas: "cottageGames.lobby.canvasDesc"
};

const myUid = ref("");
const partnerName = ref(t("cottageGames.common.partner"));
const recent = ref([]);

const games = reactive([
  {
    key: "gomoku",
    to: "/cottage/games/gomoku",
    live: false,
    myWins: 0,
    partnerWins: 0,
    draws: 0
  },
  {
    key: "tictactoe",
    to: "/cottage/games/tictactoe",
    live: false,
    myWins: 0,
    partnerWins: 0,
    draws: 0
  },
  {
    key: "reversi",
    to: "/cottage/games/reversi",
    live: false,
    myWins: 0,
    partnerWins: 0,
    draws: 0
  },
  {
    key: "memory",
    to: "/cottage/games/memory",
    live: false,
    myWins: 0,
    partnerWins: 0,
    draws: 0
  },
  {
    key: "linklink",
    to: "/cottage/games/linklink",
    live: false,
    myWins: 0,
    partnerWins: 0,
    draws: 0
  },
  {
    key: "draw",
    kind: "draw",
    to: "/cottage/games/draw",
    live: false,
    myWins: 0,
    partnerWins: 0,
    draws: 0
  },
  {
    key: "canvas",
    kind: "casual",
    to: "/cottage/games/canvas",
    live: false,
    myWins: 0,
    partnerWins: 0,
    draws: 0
  }
]);

function gameTitle(key) {
  return t(GAME_TITLE_KEYS[key] || "cottageGames.common.fallbackGameName");
}

function gameDesc(key) {
  return t(GAME_DESC_KEYS[key] || "");
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

function shortTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(getLocale(), { month: "numeric", day: "numeric" }) +
      " " + d.toLocaleTimeString(getLocale(), { hour: "2-digit", minute: "2-digit" });
  } catch (_) {
    return "";
  }
}

async function loadGame(g) {
  // The collaborative whiteboard has no game state / win record.
  if (g.kind === "casual") return [];

  const isDraw = g.kind === "draw";
  try {
    const state = isDraw ? await fetchDrawState() : await fetchGameState(g.key);
    g.live = isDraw ? state.phase === "drawing" : state.phase === "playing";
    const partner = (state.players || []).find((p) => p.uid !== myUid.value);
    if (partner) partnerName.value = partner.nickname || partnerName.value;
  } catch (error) {
    // A 503 just means Redis is down — the lobby still works.
    if (error && error.response && error.response.status !== 503) {
      showMessage(parseError(error));
    }
  }
  try {
    const data = isDraw ? await fetchDrawMatches(8) : await fetchGameMatches(g.key, 8);
    g.draws = data.draws || 0;
    const stats = data.stats || [];
    g.myWins = (stats.find((s) => s.uid === myUid.value) || {}).wins || 0;
    const partnerStat = stats.find((s) => s.uid !== myUid.value);
    g.partnerWins = partnerStat ? partnerStat.wins : 0;
    return data.items || [];
  } catch (_) {
    return [];
  }
}

onMounted(async () => {
  try {
    const me = await fetchMe();
    myUid.value = me.uid;
  } catch (_) {
    /* ignore */
  }
  const lists = await Promise.all(games.map((g) => loadGame(g)));
  recent.value = lists
    .flat()
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 8);
});
</script>

<style scoped>
.games-lobby { display: grid; gap: 1rem; }
.lobby-hero { padding: 1.2rem 1.4rem; }
.lobby-hero .section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.stats-link {
  font-size: 0.82rem;
  color: #e2698f;
  text-decoration: none;
  font-weight: 600;
}
.stats-link:hover { text-decoration: underline; }
.lobby-desc { margin: 0; color: var(--text-soft); font-size: 0.9rem; line-height: 1.6; }

.game-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}
.game-card {
  display: block;
  padding: 1.1rem 1.2rem;
  border-radius: 18px;
  text-decoration: none;
  color: var(--text-main);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.game-card:not(.soon):hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.12);
}
.game-card.soon { opacity: 0.7; }
.game-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.game-title { margin: 0 0 0.1rem; font-size: 1.05rem; color: #2f3754; }
.game-badge {
  font-size: 0.68rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.25);
  color: #64748b;
  white-space: nowrap;
}
.game-badge.live {
  background: rgba(52, 211, 153, 0.2);
  color: #16a34a;
}
.game-sub { margin: 0.35rem 0 0; font-size: 0.82rem; color: var(--text-soft); line-height: 1.5; }
.game-foot {
  margin-top: 0.9rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.record { font-size: 0.8rem; color: #6470c4; font-weight: 600; }
.enter { font-size: 0.82rem; color: #e2698f; font-weight: 600; }

.recent { padding: 1rem 1.2rem; }
.recent-title { margin: 0 0 0.6rem; font-size: 0.95rem; color: #2f3754; }
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
.recent-result { color: #3d4665; flex: 1; }
.recent-time { color: var(--text-soft); font-size: 0.76rem; white-space: nowrap; }
</style>
