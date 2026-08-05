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
  <div class="content-section cottage-wishlist">
    <div class="wishlist-header">
      <h2>{{ t('cottageWishlist.title') }}</h2>
      <span class="wishlist-progress-text">{{ t('cottageWishlist.progress', { completed: counts.completed, total: counts.total }) }}</span>
    </div>

    <div class="wishlist-progressbar" aria-hidden="true">
      <div class="wishlist-progressbar-fill" :style="{ width: progressPercent + '%' }"></div>
    </div>

    <!-- 新建心愿 -->
    <section class="glass-card section-block">
      <form class="wish-form" @submit.prevent="submitCreate">
        <input
          v-model="form.title"
          class="input"
          maxlength="160"
          :placeholder="t('cottageWishlist.titlePlaceholder')"
          required
        />
        <textarea
          v-model="form.description"
          class="input min-h-16"
          maxlength="2000"
          :placeholder="t('cottageWishlist.descPlaceholder')"
        ></textarea>
        <div class="wish-form-row">
          <select v-model="form.category" class="input">
            <option value="">{{ t('cottageWishlist.noCategory') }}</option>
            <option v-for="c in categoryOptions" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
          <input v-model="form.target_date" type="date" class="input" />
          <button type="submit" class="btn" :disabled="busy || !form.title.trim()">
            {{ busy ? t('cottageWishlist.adding') : t('cottageWishlist.submit') }}
          </button>
        </div>
      </form>
    </section>

    <!-- 筛选 -->
    <div class="wishlist-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.value"
        :class="['wishlist-tab', { active: filter === tab.value }]"
        @click="setFilter(tab.value)"
      >
        {{ tab.label }}
        <span class="wishlist-tab-count">{{ tab.count }}</span>
      </button>
    </div>

    <!-- 列表 -->
    <section class="wishlist-list">
      <p v-if="loading" class="wishlist-empty">{{ t('cottageWishlist.loading') }}</p>
      <p v-else-if="!wishes.length" class="wishlist-empty">
        {{ filter === "completed" ? t('cottageWishlist.emptyCompleted') : t('cottageWishlist.emptyDefault') }}
      </p>

      <article
        v-for="w in wishes"
        :key="w.wid"
        class="glass-card wish-card"
        :class="{ 'wish-card--done': w.status === 'completed' }"
      >
        <button
          class="wish-check"
          :class="{ checked: w.status === 'completed' }"
          :title="w.status === 'completed' ? t('cottageWishlist.markPending') : t('cottageWishlist.markCompleted')"
          @click="toggleComplete(w)"
        >
          <span v-if="w.status === 'completed'">✓</span>
        </button>

        <div class="wish-body">
          <template v-if="editingWid === w.wid">
            <input v-model="editForm.title" class="input" maxlength="160" />
            <textarea v-model="editForm.description" class="input min-h-16" maxlength="2000" :placeholder="t('cottageWishlist.descPlaceholder')"></textarea>
            <div class="wish-form-row">
              <select v-model="editForm.category" class="input">
                <option value="">{{ t('cottageWishlist.noCategory') }}</option>
                <option v-for="c in categoryOptions" :key="c.value" :value="c.value">{{ c.label }}</option>
              </select>
              <input v-model="editForm.target_date" type="date" class="input" />
            </div>
            <div class="wish-actions">
              <button class="btn-small" :disabled="busy" @click="saveEdit(w)">{{ t('cottageWishlist.save') }}</button>
              <button class="btn-small btn-ghost" @click="cancelEdit">{{ t('cottageWishlist.cancel') }}</button>
            </div>
          </template>

          <template v-else>
            <p class="wish-title">{{ w.title }}</p>
            <p v-if="w.description" class="wish-desc">{{ w.description }}</p>
            <div class="wish-meta">
              <span v-if="w.category" class="wish-pill">{{ categoryLabel(w.category) }}</span>
              <span v-if="w.target_date" class="wish-meta-item">🎯 {{ formatDate(w.target_date) }}</span>
              <span class="wish-meta-item">{{ t('cottageWishlist.authorLabel', { name: w.author_nickname }) }}</span>
              <span v-if="w.status === 'completed' && w.completed_by_nickname" class="wish-meta-item done-text">
                {{ t('cottageWishlist.completedBy', { name: w.completed_by_nickname, date: formatDate(w.completed_at) }) }}
              </span>
            </div>
            <div class="wish-actions">
              <button class="wish-link" @click="togglePin(w)">{{ w.priority > 0 ? t('cottageWishlist.unpin') : t('cottageWishlist.pin') }}</button>
              <button class="wish-link" @click="startEdit(w)">{{ t('cottageWishlist.edit') }}</button>
              <button class="wish-link wish-link--danger" @click="remove(w)">{{ t('cottageWishlist.delete') }}</button>
            </div>
          </template>
        </div>

        <span v-if="w.priority > 0 && editingWid !== w.wid" class="wish-pin" :title="t('cottageWishlist.pinned')">★</span>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, inject } from "vue";
import { useI18n } from "vue-i18n";
import {
  fetchWishes,
  createWish,
  updateWish,
  completeWish,
  reopenWish,
  deleteWish,
} from "../../../lib/api";
import { parseError } from "../../../utils/helpers";
import { formatLocalDate as formatDate } from "../../../utils/date";

const { t } = useI18n();
const showMessage = inject("showMessage", () => {});

const categoryOptions = computed(() => [
  { value: "旅行", label: t("cottageWishlist.catTravel") },
  { value: "美食", label: t("cottageWishlist.catFood") },
  { value: "礼物", label: t("cottageWishlist.catGift") },
  { value: "体验", label: t("cottageWishlist.catExperience") },
  { value: "纪念日", label: t("cottageWishlist.catAnniversary") },
  { value: "其他", label: t("cottageWishlist.catOther") },
]);

function categoryLabel(value) {
  const found = categoryOptions.value.find((c) => c.value === value);
  return found ? found.label : value;
}

const wishes = ref([]);
const counts = reactive({ total: 0, pending: 0, completed: 0 });
const loading = ref(true);
const busy = ref(false);
const filter = ref("all");

const form = reactive({ title: "", description: "", category: "", target_date: "" });

const editingWid = ref(null);
const editForm = reactive({ title: "", description: "", category: "", target_date: "" });

const tabs = computed(() => [
  { value: "all", label: t("cottageWishlist.tabAll"), count: counts.total },
  { value: "pending", label: t("cottageWishlist.tabPending"), count: counts.pending },
  { value: "completed", label: t("cottageWishlist.tabCompleted"), count: counts.completed },
]);

const progressPercent = computed(() =>
  counts.total > 0 ? Math.round((counts.completed / counts.total) * 100) : 0
);

async function load() {
  loading.value = true;
  try {
    const params = filter.value === "all" ? {} : { status: filter.value };
    const data = await fetchWishes(params);
    wishes.value = data.items || [];
    counts.total = data.total ?? 0;
    counts.pending = data.pending ?? 0;
    counts.completed = data.completed ?? 0;
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

function setFilter(value) {
  if (filter.value === value) return;
  filter.value = value;
  load();
}

async function submitCreate() {
  if (!form.title.trim() || busy.value) return;
  busy.value = true;
  try {
    await createWish({
      title: form.title.trim(),
      description: form.description.trim() || null,
      category: form.category || null,
      target_date: form.target_date || null,
    });
    form.title = "";
    form.description = "";
    form.category = "";
    form.target_date = "";
    await load();
    showMessage(t("cottageWishlist.createdToast"));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function toggleComplete(w) {
  try {
    if (w.status === "completed") {
      await reopenWish(w.wid);
    } else {
      await completeWish(w.wid);
    }
    await load();
  } catch (error) {
    showMessage(parseError(error));
  }
}

function startEdit(w) {
  editingWid.value = w.wid;
  editForm.title = w.title;
  editForm.description = w.description || "";
  editForm.category = w.category || "";
  editForm.target_date = w.target_date ? String(w.target_date).slice(0, 10) : "";
}

function cancelEdit() {
  editingWid.value = null;
}

async function saveEdit(w) {
  if (!editForm.title.trim() || busy.value) return;
  busy.value = true;
  try {
    await updateWish(w.wid, {
      title: editForm.title.trim(),
      description: editForm.description.trim() || null,
      category: editForm.category || null,
      target_date: editForm.target_date || null,
    });
    editingWid.value = null;
    await load();
    showMessage(t("cottageWishlist.savedToast"));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function togglePin(w) {
  try {
    await updateWish(w.wid, { priority: w.priority > 0 ? 0 : 1 });
    await load();
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function remove(w) {
  if (!window.confirm(t("cottageWishlist.confirmDelete", { title: w.title }))) return;
  try {
    await deleteWish(w.wid);
    await load();
    showMessage(t("cottageWishlist.deletedToast"));
  } catch (error) {
    showMessage(parseError(error));
  }
}

onMounted(load);
</script>

<style scoped>
.cottage-wishlist {
  display: grid;
  gap: 1rem;
}

.wishlist-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 0.2rem 0.2rem 0;
}
.wishlist-header h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #2f3754;
}
.wishlist-progress-text {
  font-size: 0.86rem;
  color: var(--text-soft);
}

.wishlist-progressbar {
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.25);
  overflow: hidden;
}
.wishlist-progressbar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #f9a8d4, #a78bfa);
  transition: width 0.3s ease;
}

.wish-form {
  display: grid;
  gap: 0.6rem;
}
.wish-form-row {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.wish-form-row .input {
  flex: 1 1 auto;
  min-width: 120px;
}
.min-h-16 {
  min-height: 4rem;
  resize: vertical;
}

.wishlist-tabs {
  display: flex;
  gap: 0.5rem;
}
.wishlist-tab {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.9rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  font-size: 0.84rem;
  cursor: pointer;
}
.wishlist-tab.active {
  border-color: rgba(143, 155, 255, 0.6);
  background: rgba(167, 139, 250, 0.16);
  color: #2f3754;
  font-weight: 600;
}
.wishlist-tab-count {
  font-size: 0.74rem;
  color: var(--text-soft);
}

.wishlist-list {
  display: grid;
  gap: 0.8rem;
}
.wishlist-empty {
  text-align: center;
  color: var(--text-soft);
  font-size: 0.9rem;
  padding: 1.5rem 0;
}

.wish-card {
  display: flex;
  align-items: flex-start;
  gap: 0.8rem;
  padding: 1rem 1.1rem;
  border-radius: 16px;
  position: relative;
}
.wish-card--done {
  opacity: 0.72;
}

.wish-check {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  margin-top: 2px;
  border-radius: 50%;
  border: 2px solid rgba(148, 163, 184, 0.7);
  background: transparent;
  color: #fff;
  font-size: 0.85rem;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.wish-check.checked {
  background: #a78bfa;
  border-color: #a78bfa;
}

.wish-body {
  flex: 1 1 auto;
  display: grid;
  gap: 0.4rem;
  min-width: 0;
}
.wish-title {
  margin: 0;
  font-size: 0.98rem;
  font-weight: 600;
  color: #2f3754;
  word-break: break-word;
}
.wish-card--done .wish-title {
  text-decoration: line-through;
  color: var(--text-soft);
}
.wish-desc {
  margin: 0;
  font-size: 0.86rem;
  color: var(--text-soft);
  white-space: pre-wrap;
  word-break: break-word;
}
.wish-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.78rem;
  color: var(--text-soft);
}
.wish-meta-item {
  white-space: nowrap;
}
.done-text {
  color: #16a34a;
}
.wish-pill {
  padding: 0.1rem 0.55rem;
  border-radius: 999px;
  background: rgba(167, 139, 250, 0.16);
  color: #7c3aed;
  font-size: 0.74rem;
}

.wish-actions {
  display: flex;
  gap: 0.8rem;
  margin-top: 0.2rem;
}
.wish-link {
  background: none;
  border: none;
  padding: 0;
  font-size: 0.8rem;
  color: #6d77a8;
  cursor: pointer;
}
.wish-link:hover {
  color: #2f3754;
}
.wish-link--danger {
  color: #e2698f;
}
.wish-link--danger:hover {
  color: #d6336c;
}

.btn-small {
  padding: 0.35rem 0.85rem;
  border-radius: 8px;
  border: none;
  background: #a78bfa;
  color: #fff;
  font-size: 0.82rem;
  cursor: pointer;
}
.btn-ghost {
  background: rgba(148, 163, 184, 0.18);
  color: #3d4665;
}

.wish-pin {
  position: absolute;
  top: 0.6rem;
  right: 0.8rem;
  color: #fbbf24;
  font-size: 0.9rem;
}

@media (max-width: 768px) {
  .wish-form-row { flex-direction: column; }
  .wishlist-tabs { flex-wrap: wrap; }
}
</style>
