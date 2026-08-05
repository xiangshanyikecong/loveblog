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
  <ul v-if="comments?.length" class="comment-thread">
    <li v-for="comment in comments" :key="comment.cid" class="comment-node">
      <div class="comment-card">
        <div class="comment-head">
          <span class="comment-author">{{ comment.author_nickname }}</span>
          <span class="comment-time">{{ formatTime(comment.created_at) }}</span>
        </div>

        <p class="comment-content">{{ comment.content }}</p>

        <div v-if="comment.mention_uids?.length" class="comment-mentions">
          <span v-for="uid in comment.mention_uids" :key="uid" class="comment-mention">@{{ shortUid(uid) }}</span>
        </div>

        <button
          v-if="canReply"
          type="button"
          class="comment-action"
          :disabled="submitting"
          @click="openReply(comment)"
        >
          {{ t("commentThread.reply") }}
        </button>
      </div>

      <div v-if="canReply && activeReplyCid === comment.cid" class="comment-reply-box">
        <input
          v-model="replyContent"
          class="comment-reply-input"
          :disabled="submitting"
          :placeholder="t('commentThread.replyPlaceholder')"
          @keyup.enter="handleSubmit(comment)"
        />
        <div class="comment-reply-actions">
          <button type="button" class="comment-action comment-action--primary" :disabled="submitting" @click="handleSubmit(comment)">
            {{ submitting ? t("commentThread.sending") : t("commentThread.send") }}
          </button>
          <button type="button" class="comment-action" :disabled="submitting" @click="closeReply">{{ t("commentThread.cancel") }}</button>
        </div>
      </div>

      <CommentThread
        v-if="comment.replies?.length"
        :comments="comment.replies"
        :can-reply="canReply"
        :submit-reply="submitReply"
        :submitting="submitting"
      />
    </li>
  </ul>
</template>

<script setup>
defineOptions({
  name: "CommentThread"
});

import { ref } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps({
  comments: {
    type: Array,
    default: () => []
  },
  canReply: {
    type: Boolean,
    default: false
  },
  submitReply: {
    type: Function,
    required: true
  },
  submitting: {
    type: Boolean,
    default: false
  }
});

const activeReplyCid = ref("");
const replyContent = ref("");
const mentionUids = ref([]);

function openReply(comment) {
  activeReplyCid.value = comment.cid;
  mentionUids.value = comment.author_uid ? [comment.author_uid] : [];
  replyContent.value = `@${comment.author_nickname} `;
}

function closeReply() {
  activeReplyCid.value = "";
  replyContent.value = "";
  mentionUids.value = [];
}

async function handleSubmit(comment) {
  const content = replyContent.value.trim();
  if (!content) {
    return;
  }

  await props.submitReply({
    parentCid: comment.cid,
    content,
    mentionUids: [...mentionUids.value]
  });
  closeReply();
}

function formatTime(raw) {
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? raw : date.toLocaleString();
}

function shortUid(uid) {
  return String(uid).slice(0, 8);
}
</script>

<style scoped>
.comment-thread {
  list-style: none;
  padding: 0;
  margin: 0.75rem 0 0;
  display: grid;
  gap: 0.6rem;
}

.comment-node {
  display: grid;
  gap: 0.55rem;
  padding-left: 0.9rem;
  border-left: 2px solid rgba(148, 163, 184, 0.18);
}

.comment-card {
  display: grid;
  gap: 0.35rem;
  padding: 0.7rem 0.8rem;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(203, 213, 225, 0.45);
}

.comment-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.comment-author {
  font-weight: 600;
  color: #334155;
}

.comment-time {
  font-size: 0.74rem;
  color: #94a3b8;
}

.comment-content {
  margin: 0;
  color: #334155;
  white-space: pre-wrap;
  line-height: 1.5;
}

.comment-mentions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.comment-mention {
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 0.72rem;
}

.comment-action {
  width: fit-content;
  border: 0;
  background: transparent;
  color: #6366f1;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.comment-action--primary {
  color: #2563eb;
}

.comment-action:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.comment-reply-box {
  display: grid;
  gap: 0.5rem;
  margin-left: 0.9rem;
}

.comment-reply-input {
  width: 100%;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.92);
  padding: 0.55rem 0.7rem;
  font-size: 0.84rem;
  outline: none;
}

.comment-reply-input:focus {
  border-color: rgba(99, 102, 241, 0.55);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.12);
}

.comment-reply-actions {
  display: flex;
  gap: 0.8rem;
  align-items: center;
}
</style>
