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
  <section class="glass-card section-block message-board">
    <div class="section-header">
      <h2>{{ title || t("messageBoard.title") }}</h2>
      <div class="message-actions">
        <button class="ghost-btn" :disabled="loading || sending" @click="loadMessages">
          {{ loading ? t("messageBoard.refreshing") : t("messageBoard.refresh") }}
        </button>
        <router-link v-if="openPagePath" :to="openPagePath" class="ghost-btn message-link">
          {{ t("messageBoard.viewAll") }}
        </router-link>
      </div>
    </div>

    <p v-if="showComposer && !token" class="muted">
      {{ t("messageBoard.guestHint") }}
    </p>

    <form v-if="showComposer" class="form-stack" @submit.prevent="submitMessage">
      <label class="message-field">
        <span>{{ t("messageBoard.contentLabel") }}</span>
        <textarea
          v-model="form.content"
          class="input message-textarea"
          maxlength="2000"
          :placeholder="t('messageBoard.contentPlaceholder')"
          required
        />
      </label>
      <label class="message-field">
        <span>{{ t("messageBoard.tagsLabel") }}</span>
        <input v-model="form.tagsText" class="input" maxlength="240" :placeholder="t('messageBoard.tagsPlaceholder')" />
      </label>
      <div class="message-form-footer">
        <label class="check">
          <input v-model="form.is_public" type="checkbox" />
          {{ t("messageBoard.publicMessage") }}
        </label>
        <button class="btn-primary" :disabled="!token || sending || !form.content.trim()">
          {{ sending ? t("messageBoard.sending") : t("messageBoard.send") }}
        </button>
      </div>
    </form>

    <ul v-if="visibleMessages.length" class="simple-list message-list">
      <li v-for="item in visibleMessages" :key="item.msg_id" class="message-item">
        <div class="message-main">
          <p class="message-content">{{ item.content }}</p>
          <p class="message-meta">
            {{ item.author_nickname || item.visitor_name || t("messageBoard.anonymous") }}
            <span>，{{ formatTime(item.created_at) }}</span>
            <span v-if="!item.is_public">，{{ t("messageBoard.private") }}</span>
          </p>
          <div v-if="item.tags && item.tags.length" class="message-tags">
            <span v-for="tag in item.tags" :key="tag" class="pill pill--tag">#{{ tag }}</span>
          </div>
        </div>
      </li>
    </ul>
    <p v-else-if="loading" class="muted">{{ t("messageBoard.loadingMessages") }}</p>
    <EmptyState
      v-else
      :icon="MessageCircle"
      :title="t('messageBoard.emptyTitle')"
      :description="showComposer ? t('messageBoard.emptyDescComposer') : t('messageBoard.emptyDescGuest')"
    />
  </section>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { MessageCircle } from "@lucide/vue";
import EmptyState from "./EmptyState.vue";
import { createMessage, fetchMessages } from "../lib/api";
import { useAuth } from "../stores/auth";
import { parseError, parseTags } from "../utils/helpers";

const { t } = useI18n();

const props = defineProps({
  title: {
    type: String,
    default: ""
  },
  maxItems: {
    type: Number,
    default: 0
  },
  openPagePath: {
    type: String,
    default: ""
  },
  showComposer: {
    type: Boolean,
    default: true
  }
});

const showMessage = inject("showMessage");
const { token } = useAuth();

const loading = ref(false);
const sending = ref(false);
const messages = ref([]);
const form = reactive({
  content: "",
  tagsText: "",
  is_public: true
});

const visibleMessages = computed(() => {
  if (!props.maxItems || props.maxItems <= 0) {
    return messages.value;
  }
  return messages.value.slice(0, props.maxItems);
});

function formatTime(raw) {
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? raw : date.toLocaleString();
}

async function loadMessages() {
  loading.value = true;
  try {
    const params = token.value ? { include_private: true } : {};
    const data = await fetchMessages(params);
    messages.value = data.items || [];
  } catch (error) {
    showMessage?.(parseError(error), "error");
  } finally {
    loading.value = false;
  }
}

async function submitMessage() {
  if (!token.value) {
    showMessage?.(t("messageBoard.loginRequired"));
    return;
  }

  const content = form.content.trim();
  if (!content) {
    return;
  }

  sending.value = true;
  try {
    await createMessage({
      content,
      tags: parseTags(form.tagsText),
      is_public: form.is_public
    });
    form.content = "";
    form.tagsText = "";
    showMessage?.(t("messageBoard.sentSuccess"));
    await loadMessages();
  } catch (error) {
    showMessage?.(parseError(error), "error");
  } finally {
    sending.value = false;
  }
}

watch(
  () => token.value,
  () => {
    loadMessages();
  }
);

onMounted(() => {
  loadMessages();
});
</script>

<style scoped>
.message-board {
  display: grid;
  gap: 0.85rem;
}

.message-actions {
  display: flex;
  gap: 0.45rem;
  align-items: center;
}

.message-link {
  text-decoration: none;
}

.message-textarea {
  min-height: 92px;
  resize: vertical;
}

.message-field {
  display: grid;
  gap: 0.35rem;
  color: var(--text-main);
  font-size: 0.82rem;
  font-weight: 700;
}

.message-form-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}

.message-list {
  margin-top: 0.2rem;
}

.message-item {
  justify-content: flex-start;
}

.message-main {
  width: 100%;
}

.message-content {
  margin: 0;
  line-height: 1.55;
  white-space: pre-wrap;
}

.message-meta {
  margin: 0.35rem 0 0;
  color: #64748b;
  font-size: 0.77rem;
}

.message-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.45rem;
}
</style>
