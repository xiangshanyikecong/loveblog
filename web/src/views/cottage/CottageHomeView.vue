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
    <article class="glass-card section-block cottage-hero">
      <div class="section-header">
        <h2>{{ t('cottage.hub') }}</h2>
        <router-link
          to="/cottage/reminders"
          class="cottage-reminder-btn"
          :title="t('cottage.remindersTitle')"
          :aria-label="t('cottage.remindersTitle')"
        >
          <span class="cottage-reminder-icon" aria-hidden="true">🔔</span>
        </router-link>
      </div>
      <p class="cottage-hero-desc">
        {{ t('cottage.heroDesc') }}
      </p>
    </article>

    <!-- 在线状态 + 戳一戳 -->
    <section class="glass-card section-block cottage-link">
      <div class="link-peer">
        <div class="link-avatar" :class="{ online: partnerOnline }">
          {{ initialOf(partnerName) }}
          <span class="link-dot" :class="{ online: partnerOnline }"></span>
        </div>
        <div class="link-meta">
          <p class="link-name">{{ partnerName || t('cottage.noPartner') }}</p>
          <p class="link-status" :class="{ online: partnerOnline }">
            {{ partnerOnline ? t('cottage.onlineStatus') : t('cottage.offlineStatus') }}
          </p>
        </div>
        <router-link to="/cottage/chat" class="link-chat-btn">
          {{ t('cottage.chatLink') }}
          <span v-if="unread > 0" class="link-unread">{{ unread > 99 ? "99+" : unread }}</span>
        </router-link>
      </div>

      <div class="link-pokes">
        <button
          v-for="p in pokes"
          :key="p.kind"
          class="link-poke"
          :disabled="pokeBusy"
          @click="poke(p.kind)"
        >
          <span class="link-poke-emoji">{{ p.emoji }}</span>
          <span class="link-poke-label">{{ p.label }}</span>
        </button>
      </div>
    </section>

    <!-- 回忆回顾：回到那一天 / 年度报告 -->
    <section class="cottage-module-group">
      <div class="cottage-modules">
        <router-link to="/cottage/memories" class="cottage-module-card glass-card cottage-recall-card">
          <h4 class="cottage-module-title">
            <span class="cottage-module-icon" aria-hidden="true">🕰️</span>
            <span class="cottage-module-name">{{ t('cottageMemories.title') }}</span>
          </h4>
          <p class="cottage-module-desc">{{ t('cottageMemories.subtitle') }}</p>
        </router-link>
        <router-link to="/cottage/reports/annual" class="cottage-module-card glass-card cottage-recall-card">
          <h4 class="cottage-module-title">
            <span class="cottage-module-icon" aria-hidden="true">📊</span>
            <span class="cottage-module-name">{{ t('cottageAnnualReport.title') }}</span>
          </h4>
          <p class="cottage-module-desc">{{ t('cottageAnnualReport.subtitle') }}</p>
        </router-link>
      </div>
    </section>

    <section
      v-for="g in groupedModules"
      :key="g.key"
      class="cottage-module-group"
    >
      <h3 class="cottage-group-title">
        <span class="cottage-group-emoji" aria-hidden="true">{{ g.emoji }}</span>
        {{ t(g.titleKey) }}
      </h3>
      <div class="cottage-modules">
        <router-link
          v-for="m in g.items"
          :key="m.key"
          :to="m.to"
          class="cottage-module-card glass-card"
        >
          <h4 class="cottage-module-title">
            <span class="cottage-module-icon" aria-hidden="true">{{ m.icon }}</span>
            <span class="cottage-module-name">{{ t(m.titleKey) }}</span>
            <span v-if="m.key === 'chat' && unread > 0" class="module-badge">{{ unread > 99 ? "99+" : unread }}</span>
          </h4>
          <p class="cottage-module-desc">{{ t(m.descKey) }}</p>
        </router-link>
      </div>
    </section>

    <!-- 安全中心入口 -->
    <section class="cottage-modules security-entry">
      <router-link to="/cottage/security" class="cottage-module-card glass-card">
        <h4 class="cottage-module-title">
          <span class="cottage-module-icon" aria-hidden="true">🔒</span>
          <span class="cottage-module-name">{{ t('securityCenter.title') }}</span>
        </h4>
        <p class="cottage-module-desc">{{ t('securityCenter.subtitle') }}</p>
      </router-link>
    </section>

    <!-- 戳一戳飞入动画 -->
    <transition name="poke-pop">
      <div v-if="pokeFlash" class="poke-flash">
        <div class="poke-flash-emoji">{{ pokeFlash.emoji }}</div>
        <div class="poke-flash-text">{{ pokeFlash.text }}</div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { cottageModules, cottageGroups } from "./modules";
import { fetchChatState, sendPoke } from "../../lib/api";
import { createCottageSocket } from "../../lib/cottageChatWs";
import { parseError } from "../../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

const groupedModules = computed(() =>
  cottageGroups
    .map((g) => ({
      ...g,
      items: cottageModules.filter((m) => m.group === g.key && m.key !== "reminders")
    }))
    .filter((g) => g.items.length > 0)
);

const pokes = computed(() => [
  { kind: "miss", emoji: "💗", label: t("cottage.pokeMiss") },
  { kind: "hug", emoji: "🤗", label: t("cottage.pokeHug") },
  { kind: "poke", emoji: "👉", label: t("cottage.pokePoke") },
]);
const POKE_EMOJI = { miss: "💗", hug: "🤗", poke: "👉", kiss: "😘" };

const partnerUid = ref("");
const partnerName = ref("");
const partnerOnline = ref(false);
const unread = ref(0);
const pokeBusy = ref(false);
const pokeFlash = ref(null);

let socket = null;
let pokeFlashTimer = null;

function initialOf(name) {
  const s = String(name || "").trim();
  return s ? s.slice(0, 1).toUpperCase() : "Ta";
}

function flashPoke(text, emoji) {
  pokeFlash.value = { text, emoji: emoji || "💕" };
  if (pokeFlashTimer) clearTimeout(pokeFlashTimer);
  pokeFlashTimer = setTimeout(() => {
    pokeFlash.value = null;
  }, 2200);
}

async function poke(kind) {
  if (pokeBusy.value) return;
  pokeBusy.value = true;
  try {
    await sendPoke(kind);
    const found = pokes.value.find((p) => p.kind === kind);
    showMessage(t("cottage.pokeSent", { name: partnerName.value || "Ta", action: found ? found.label : t("cottage.pokeGreet") }));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    setTimeout(() => {
      pokeBusy.value = false;
    }, 600);
  }
}

function handleEvent(e) {
  if (!e || typeof e !== "object") return;
  if (e.type === "PRESENCE") {
    if (e.payload && e.payload.uid === partnerUid.value) {
      partnerOnline.value = !!e.payload.online;
    }
  } else if (e.type === "PRESENCE_SNAPSHOT") {
    const online = (e.payload && e.payload.online) || [];
    if (partnerUid.value) partnerOnline.value = online.includes(partnerUid.value);
  } else if (e.type === "POKE") {
    const p = e.payload || {};
    flashPoke(t("cottage.pokeReceived", { name: p.from_nickname || "Ta" }), POKE_EMOJI[p.kind]);
  } else if (e.type === "CHAT_MESSAGE") {
    if (e.payload && e.payload.sender_uid && e.payload.sender_uid === partnerUid.value) {
      unread.value += 1;
    }
  }
}

// Dev-only sanity check (V3): every cottageModules.to must point to a
// registered route whose meta.requiresPartner === true.
if (import.meta.env.DEV) {
  const router = useRouter();
  const registered = router.getRoutes();
  for (const m of cottageModules) {
    const hit = registered.find((r) => r.path === m.to);
    if (!hit || hit.meta?.requiresPartner !== true) {
      throw new Error(`[cottage-shell] Module "${m.key}" has an invalid partner route: "${m.to}".`);
    }
  }
}

onMounted(async () => {
  try {
    const state = await fetchChatState();
    partnerUid.value = state.partner_uid || "";
    partnerName.value = state.partner_nickname || "";
    partnerOnline.value = !!state.partner_online;
    unread.value = state.unread || 0;
  } catch (_) {
    /* ignore */
  }
  socket = createCottageSocket({ onEvent: handleEvent });
});

onBeforeUnmount(() => {
  if (socket) socket.close();
  if (pokeFlashTimer) clearTimeout(pokeFlashTimer);
});
</script>

<style scoped>
.cottage-hero { padding: 1.4rem 1.5rem; }
.cottage-hero-desc { margin: 0; color: var(--text-soft); font-size: 0.92rem; line-height: 1.6; }

/* 小屋提醒 · 圆形入口(与标题同栏,靠右) */
.cottage-reminder-btn {
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  background: linear-gradient(135deg, #ffd9a8, #ff9eb6);
  box-shadow: 0 6px 14px rgba(255, 138, 181, 0.32);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.cottage-reminder-btn:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 10px 20px rgba(255, 138, 181, 0.4);
}
.cottage-reminder-btn:active { transform: scale(0.96); }
.cottage-reminder-icon { font-size: 1.1rem; line-height: 1; }

/* Link / presence card */
.cottage-link {
  display: grid;
  gap: 0.9rem;
}
.link-peer {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.link-avatar {
  position: relative;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #c7cdf5, #b9c0e8);
  flex: 0 0 auto;
}
.link-avatar.online {
  background: linear-gradient(135deg, #ff8ab5, #8f9bff);
}
.link-dot {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 2px solid #fff;
  background: #cbd5e1;
}
.link-dot.online { background: #34d399; }
.link-meta { flex: 1; min-width: 0; }
.link-name {
  margin: 0;
  font-size: 1.02rem;
  font-weight: 700;
  color: #2f3754;
}
.link-status {
  margin: 0;
  font-size: 0.78rem;
  color: var(--text-soft);
}
.link-status.online { color: #16a34a; }
.link-chat-btn {
  position: relative;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.45rem 1rem;
  border-radius: 999px;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
  font-size: 0.84rem;
  font-weight: 600;
  text-decoration: none;
  box-shadow: 0 8px 16px rgba(143, 155, 255, 0.3);
}
.link-unread {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #fff;
  color: #e2698f;
  font-size: 0.68rem;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.link-pokes {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}
.link-poke {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.5rem 0.4rem;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  background: rgba(255, 255, 255, 0.72);
  cursor: pointer;
  transition: transform 0.12s ease;
}
.link-poke:hover { transform: translateY(-2px); }
.link-poke:disabled { opacity: 0.55; cursor: not-allowed; }
.link-poke-emoji { font-size: 1.15rem; line-height: 1; }
.link-poke-label { font-size: 0.8rem; color: #3d4665; }

/* Module groups */
.cottage-module-group {
  display: grid;
  gap: 0.7rem;
}
.security-entry .cottage-module-card {
  max-width: 340px;
}
.cottage-group-title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.92rem;
  font-weight: 700;
  color: #2f3754;
  padding-left: 0.1rem;
}
.cottage-group-emoji { font-size: 1.05rem; line-height: 1; }

/* Modules */
.cottage-modules {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}
.cottage-module-card {
  display: block;
  padding: 1.2rem 1.3rem;
  border-radius: 18px;
  text-decoration: none;
  color: var(--text-main);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.cottage-module-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.12);
}
.cottage-module-title {
  margin: 0 0 0.4rem;
  font-size: 1rem;
  color: #2f3754;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.cottage-module-icon { font-size: 1.2rem; line-height: 1; flex: 0 0 auto; }
.cottage-module-name { flex: 1 1 auto; min-width: 0; }
.module-badge {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #e2698f;
  color: #fff;
  font-size: 0.66rem;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.cottage-module-desc { margin: 0; font-size: 0.84rem; color: var(--text-soft); line-height: 1.55; }

/* 回忆回顾入口（回到那一天 / 年度报告）· 渐变粉色调 */
.cottage-recall-card {
  background: linear-gradient(135deg, rgba(255, 224, 238, 0.88), rgba(247, 226, 255, 0.78));
  border: 1px solid rgba(255, 182, 205, 0.55);
  box-shadow: 0 10px 24px rgba(255, 138, 181, 0.16);
}
.cottage-recall-card .cottage-module-desc { color: #8a6b7c; }

/* Poke flash */
.poke-flash {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 60;
}
.poke-flash-emoji {
  font-size: 5rem;
  animation: poke-bounce 0.6s ease;
}
.poke-flash-text {
  margin-top: 0.5rem;
  background: rgba(47, 55, 84, 0.82);
  color: #fff;
  padding: 0.4rem 1rem;
  border-radius: 999px;
  font-size: 0.9rem;
}
@keyframes poke-bounce {
  0% { transform: scale(0.3); opacity: 0; }
  50% { transform: scale(1.25); opacity: 1; }
  100% { transform: scale(1); }
}
.poke-pop-enter-active { transition: opacity 0.2s ease; }
.poke-pop-leave-active { transition: opacity 0.5s ease; }
.poke-pop-enter-from, .poke-pop-leave-to { opacity: 0; }

@media (max-width: 768px) {
  .cottage-modules { grid-template-columns: 1fr; }
}
</style>
