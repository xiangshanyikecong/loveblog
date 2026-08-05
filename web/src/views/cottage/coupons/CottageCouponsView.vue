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
  <div class="content-section cottage-coupons">
    <div class="cp-header">
      <h2>{{ t('cottageCoupons.title') }}</h2>
      <span class="cp-sub">{{ t('cottageCoupons.subtitle') }}</span>
    </div>

    <!-- 新建券 -->
    <section class="glass-card section-block">
      <form class="cp-form" @submit.prevent="submitCreate">
        <div class="cp-icon-row">
          <button
            v-for="ic in icons"
            :key="ic"
            type="button"
            class="cp-icon-pick"
            :class="{ active: form.icon === ic }"
            @click="form.icon = ic"
          >{{ ic }}</button>
        </div>
        <input
          v-model="form.title"
          class="input"
          maxlength="160"
          :placeholder="t('cottageCoupons.titlePlaceholder')"
          required
        />
        <textarea
          v-model="form.description"
          class="input min-h-16"
          maxlength="2000"
          :placeholder="t('cottageCoupons.descPlaceholder')"
        ></textarea>
        <button type="submit" class="btn" :disabled="busy || !form.title.trim()">
          {{ busy ? t('cottageCoupons.sending') : t('cottageCoupons.submit') }}
        </button>
      </form>
    </section>

    <!-- 切换收发 -->
    <div class="cp-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.value"
        :class="['cp-tab', { active: box === tab.value }]"
        @click="setBox(tab.value)"
      >{{ tab.label }}</button>
    </div>

    <!-- 列表 -->
    <section class="cp-list">
      <p v-if="loading" class="cp-empty">{{ t('cottageCoupons.loading') }}</p>
      <p v-else-if="!coupons.length" class="cp-empty">
        {{ box === "sent" ? t('cottageCoupons.emptySent') : t('cottageCoupons.emptyReceived') }}
      </p>

      <article
        v-for="c in coupons"
        :key="c.cpid"
        class="cp-card glass-card"
        :class="{ 'cp-card--used': c.status === 'redeemed' }"
      >
        <div class="cp-card-icon">{{ c.icon || "🎁" }}</div>
        <div class="cp-card-body">
          <p class="cp-card-title">{{ c.title }}</p>
          <p v-if="c.description" class="cp-card-desc">{{ c.description }}</p>
          <div class="cp-card-meta">
            <span>{{ c.is_mine ? t('cottageCoupons.sentByMe') : t('cottageCoupons.sentBy', { name: c.author_nickname }) }}</span>
            <span v-if="c.status === 'redeemed'" class="cp-used-text">
              {{ t('cottageCoupons.redeemedAt', { date: formatDate(c.redeemed_at) }) }}
            </span>
          </div>
        </div>
        <div class="cp-card-actions">
          <span v-if="c.status === 'redeemed'" class="cp-badge-used">{{ t('cottageCoupons.redeemedBadge') }}</span>
          <button
            v-else-if="!c.is_mine"
            class="btn-small"
            :disabled="busy"
            @click="redeem(c)"
          >{{ t('cottageCoupons.redeem') }}</button>
          <button
            v-if="c.is_mine && c.status === 'active'"
            class="cp-link cp-link--danger"
            @click="remove(c)"
          >{{ t('cottageCoupons.withdraw') }}</button>
          <button
            v-else-if="c.status === 'redeemed'"
            class="cp-link cp-link--danger"
            @click="remove(c)"
          >{{ t('cottageCoupons.delete') }}</button>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  fetchCoupons,
  createCoupon,
  redeemCoupon,
  deleteCoupon,
} from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

const icons = ["🎁", "💝", "🤗", "😘", "🍳", "🧹", "🛋️", "🎬", "☕", "💆", "🛍️", "💗"];

const coupons = ref([]);
const loading = ref(true);
const busy = ref(false);
const box = ref("received");

const form = reactive({ title: "", description: "", icon: "🎁" });

const tabs = [
  { value: "received", label: t("cottageCoupons.tabReceived") },
  { value: "sent", label: t("cottageCoupons.tabSent") },
];

function formatDate(raw) {
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return String(raw).slice(0, 10);
  return d.toLocaleDateString(undefined);
}

async function load() {
  loading.value = true;
  try {
    const data = await fetchCoupons({ box: box.value });
    coupons.value = data.items || [];
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

function setBox(value) {
  if (box.value === value) return;
  box.value = value;
  load();
}

async function submitCreate() {
  if (!form.title.trim() || busy.value) return;
  busy.value = true;
  try {
    await createCoupon({
      title: form.title.trim(),
      description: form.description.trim() || null,
      icon: form.icon || null,
    });
    form.title = "";
    form.description = "";
    form.icon = "🎁";
    box.value = "sent";
    await load();
    showMessage(t('cottageCoupons.createdToast'));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function redeem(c) {
  if (busy.value) return;
  if (!window.confirm(t('cottageCoupons.confirmRedeem', { title: c.title }))) return;
  busy.value = true;
  try {
    await redeemCoupon(c.cpid);
    await load();
    showMessage(t('cottageCoupons.redeemedToast'));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function remove(c) {
  if (!window.confirm(t('cottageCoupons.confirmRemove', { title: c.title }))) return;
  try {
    await deleteCoupon(c.cpid);
    await load();
    showMessage(t('cottageCoupons.removedToast'));
  } catch (error) {
    showMessage(parseError(error));
  }
}

onMounted(load);
</script>

<style scoped>
.cottage-coupons {
  display: grid;
  gap: 1rem;
}
.cp-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.6rem;
  padding: 0.2rem 0.2rem 0;
}
.cp-header h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #2f3754;
}
.cp-sub {
  font-size: 0.82rem;
  color: var(--text-soft);
}

.cp-form {
  display: grid;
  gap: 0.6rem;
}
.cp-icon-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.cp-icon-pick {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  background: rgba(255, 255, 255, 0.7);
  font-size: 1.1rem;
  cursor: pointer;
  transition: transform 0.12s ease;
}
.cp-icon-pick:hover { transform: translateY(-2px); }
.cp-icon-pick.active {
  border-color: rgba(143, 155, 255, 0.7);
  background: rgba(167, 139, 250, 0.18);
}
.min-h-16 { min-height: 4rem; resize: vertical; }

.cp-tabs { display: flex; gap: 0.5rem; }
.cp-tab {
  padding: 0.4rem 1rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  font-size: 0.84rem;
  cursor: pointer;
}
.cp-tab.active {
  border-color: rgba(143, 155, 255, 0.6);
  background: rgba(167, 139, 250, 0.16);
  color: #2f3754;
  font-weight: 600;
}

.cp-list { display: grid; gap: 0.8rem; }
.cp-empty {
  text-align: center;
  color: var(--text-soft);
  font-size: 0.9rem;
  padding: 1.5rem 0;
}

.cp-card {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  padding: 1rem 1.1rem;
  border-radius: 16px;
  position: relative;
  border-left: 4px dashed rgba(167, 139, 250, 0.5);
}
.cp-card--used { opacity: 0.66; border-left-color: rgba(148, 163, 184, 0.5); }
.cp-card-icon {
  flex: 0 0 auto;
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  background: linear-gradient(135deg, #ffe0ec, #e9e2ff);
}
.cp-card-body { flex: 1 1 auto; min-width: 0; display: grid; gap: 0.25rem; }
.cp-card-title { margin: 0; font-size: 0.98rem; font-weight: 600; color: #2f3754; word-break: break-word; }
.cp-card--used .cp-card-title { text-decoration: line-through; color: var(--text-soft); }
.cp-card-desc { margin: 0; font-size: 0.84rem; color: var(--text-soft); white-space: pre-wrap; word-break: break-word; }
.cp-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  font-size: 0.76rem;
  color: var(--text-soft);
}
.cp-used-text { color: #16a34a; }
.cp-card-actions {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.4rem;
}
.cp-badge-used {
  font-size: 0.74rem;
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 999px;
  padding: 0.1rem 0.55rem;
}
.btn-small {
  padding: 0.4rem 1rem;
  border-radius: 999px;
  border: none;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
}
.btn-small:disabled { opacity: 0.6; cursor: not-allowed; }
.cp-link {
  background: none;
  border: none;
  padding: 0;
  font-size: 0.78rem;
  color: #6d77a8;
  cursor: pointer;
}
.cp-link--danger { color: #e2698f; }
.cp-link--danger:hover { color: #d6336c; }
</style>
