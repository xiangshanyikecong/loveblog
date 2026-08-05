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
  <div class="cottage-layout">
    <!-- 子页面 -->
    <router-view />

    <!-- 全局邀请横幅：对方在小屋任意页面发出的邀请都会到这里 -->
    <transition name="cottage-invite-pop">
      <div v-if="invite" class="cottage-invite" role="alert">
        <span class="cottage-invite-emoji">💌</span>
        <span class="cottage-invite-text">{{ invite.text }}</span>
        <div class="cottage-invite-actions">
          <button type="button" class="cottage-invite-go" @click="acceptInvite">{{ t('cottageLayout.goLook') }}</button>
          <button type="button" class="cottage-invite-dismiss" :aria-label="t('cottageLayout.ignore')" @click="invite = null">✕</button>
        </div>
      </div>
    </transition>

    <!-- 全局戳一戳 / 悄悄话飞入：仅在不处理这类事件的页面上兜底显示 -->
    <transition name="cottage-flash-pop">
      <div v-if="flash" class="cottage-flash">
        <div class="cottage-flash-emoji">{{ flash.emoji }}</div>
        <div class="cottage-flash-text">{{ flash.text }}</div>
      </div>
    </transition>
  </div>
</template>

<script setup>
/**
 * Cottage (小屋) shell that wraps every /cottage child route. Its job is to keep
 * ONE realtime socket open for the whole time the user is anywhere in the
 * cottage. That single persistent connection is what makes "在小屋" presence
 * correct across features: as long as the partner is on any cottage page their
 * socket stays connected, so the server reports them online — instead of only
 * when they happen to sit on the home/chat page.
 *
 * It also surfaces cottage-wide nudges (invites / pokes / new chat messages)
 * that arrive while the user is on a feature page which doesn't itself handle
 * them, so an invite finally "has an effect" no matter where Ta is.
 */
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { createCottageSocket } from "../../lib/cottageChatWs";
import { fetchMe } from "../../lib/api";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const myUid = ref("");
const invite = ref(null);
const flash = ref(null);

let socket = null;
let flashTimer = null;

const POKE_EMOJI = { miss: "💗", hug: "🤗", poke: "👉", kiss: "😘" };

// Pages that already render incoming poke/chat events themselves. On those we
// stay quiet to avoid a double notification; everywhere else in the cottage we
// surface them so the user still notices.
function handledLocally() {
  return route.path === "/cottage" || route.path === "/cottage/chat";
}

function showFlash(text, emoji) {
  flash.value = { text, emoji: emoji || "💕" };
  if (flashTimer) clearTimeout(flashTimer);
  flashTimer = setTimeout(() => {
    flash.value = null;
  }, 2400);
}

function acceptInvite() {
  const link = invite.value && invite.value.link;
  invite.value = null;
  if (link) router.push(link);
}

function handleEvent(e) {
  if (!e || typeof e !== "object") return;
  if (e.type === "INVITE") {
    const p = e.payload || {};
    if (p.from_uid && p.from_uid === myUid.value) return;
    invite.value = {
      text: t("cottageLayout.inviteText", { name: p.from_nickname || t("cottageLayout.them"), title: p.title || t("cottageLayout.defaultInviteTitle") }),
      link: p.link || "/cottage",
    };
  } else if (e.type === "POKE") {
    if (handledLocally()) return;
    const p = e.payload || {};
    showFlash(t("cottageLayout.pokeText", { name: p.from_nickname || t("cottageLayout.them"), label: p.label || t("cottageLayout.defaultPokeLabel") }), POKE_EMOJI[p.kind]);
  } else if (e.type === "CHAT_MESSAGE") {
    if (handledLocally()) return;
    const p = e.payload || {};
    if (p.sender_uid && p.sender_uid !== myUid.value) {
      showFlash(t("cottageLayout.chatFlash", { name: p.sender_nickname || t("cottageLayout.them") }), "💌");
    }
  }
}

onMounted(async () => {
  try {
    const me = await fetchMe();
    myUid.value = me.uid || "";
  } catch (_) {
    /* ignore — events still render with fallback names */
  }
  socket = createCottageSocket({ onEvent: handleEvent });
});

onBeforeUnmount(() => {
  if (socket) socket.close();
  if (flashTimer) clearTimeout(flashTimer);
});
</script>

<style scoped>
.cottage-layout {
  position: relative;
}

.cottage-invite {
  position: fixed;
  top: 18px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 80;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  max-width: min(92vw, 460px);
  padding: 0.7rem 0.9rem;
  border-radius: 14px;
  background: rgba(47, 55, 84, 0.92);
  color: #fff;
  box-shadow: 0 14px 32px rgba(15, 23, 42, 0.28);
}
.cottage-invite-emoji { font-size: 1.2rem; line-height: 1; flex: 0 0 auto; }
.cottage-invite-text { flex: 1; font-size: 0.9rem; line-height: 1.4; }
.cottage-invite-actions { display: flex; align-items: center; gap: 0.4rem; flex: 0 0 auto; }
.cottage-invite-go {
  border: none;
  border-radius: 999px;
  padding: 0.35rem 0.9rem;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
}
.cottage-invite-dismiss {
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
  cursor: pointer;
  padding: 0.2rem 0.3rem;
}

.cottage-invite-pop-enter-active,
.cottage-invite-pop-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.cottage-invite-pop-enter-from,
.cottage-invite-pop-leave-to { opacity: 0; transform: translateX(-50%) translateY(-12px); }

.cottage-flash {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 70;
}
.cottage-flash-emoji { font-size: 4.5rem; animation: cottage-flash-bounce 0.6s ease; }
.cottage-flash-text {
  margin-top: 0.5rem;
  background: rgba(47, 55, 84, 0.82);
  color: #fff;
  padding: 0.4rem 1rem;
  border-radius: 999px;
  font-size: 0.9rem;
}
@keyframes cottage-flash-bounce {
  0% { transform: scale(0.3); opacity: 0; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(1); }
}
.cottage-flash-pop-enter-active { transition: opacity 0.2s ease; }
.cottage-flash-pop-leave-active { transition: opacity 0.5s ease; }
.cottage-flash-pop-enter-from,
.cottage-flash-pop-leave-to { opacity: 0; }
</style>
