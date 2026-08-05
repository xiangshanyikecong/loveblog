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
  <div class="content-section cottage-questions">
    <header class="questions-header">
      <div>
        <h2>{{ t('cottageQuestions.title') }}</h2>
        <p>{{ t('cottageQuestions.subtitle') }}</p>
      </div>
      <router-link to="/cottage" class="questions-back">{{ t('cottageQuestions.backToCottage') }}</router-link>
    </header>

    <section v-if="loading" class="glass-card questions-empty">{{ t('cottageQuestions.loading') }}</section>

    <template v-else>
      <section v-if="!todayQuestion" class="glass-card section-block question-composer">
        <h3>{{ t('cottageQuestions.composerTitle') }}</h3>
        <form class="question-form" @submit.prevent="submitQuestion">
          <textarea
            v-model="questionForm.prompt"
            class="input"
            maxlength="500"
            :placeholder="t('cottageQuestions.promptPlaceholder')"
            required
          ></textarea>
          <div class="question-form-actions">
            <input v-model="questionForm.question_date" type="date" class="input date-input" />
            <button class="btn" type="submit" :disabled="busy || !questionForm.prompt.trim()">
              {{ busy ? t('cottageQuestions.saving') : t('cottageQuestions.setAsToday') }}
            </button>
          </div>
        </form>
      </section>

      <section v-else class="glass-card section-block today-question">
        <div class="today-question-top">
          <div>
            <span class="question-date">{{ formatDate(todayQuestion.question_date) }}</span>
            <h3>{{ todayQuestion.prompt }}</h3>
          </div>
          <span class="reveal-pill" :class="{ revealed: todayQuestion.revealed }">
            {{ todayQuestion.revealed ? t('cottageQuestions.revealed') : t('cottageQuestions.answeredCount', { answered: todayQuestion.answered_count, total: todayQuestion.partner_count }) }}
          </span>
        </div>

        <div class="answers-grid">
          <article
            v-for="answer in todayQuestion.answers"
            :key="answer.author_uid"
            class="answer-card"
            :class="{ self: answer.is_self, hidden: !answer.content_visible }"
          >
            <div class="answer-card-head">
              <strong>{{ answer.is_self ? t('cottageQuestions.myAnswer') : answer.author_nickname }}</strong>
              <span>{{ answer.answered ? t('cottageQuestions.answered') : t('cottageQuestions.waiting') }}</span>
            </div>
            <p v-if="answer.content_visible" class="answer-content">{{ answer.content }}</p>
            <p v-else-if="answer.answered" class="answer-placeholder">{{ t('cottageQuestions.partnerWaiting') }}</p>
            <p v-else class="answer-placeholder">{{ t('cottageQuestions.notAnswered') }}</p>
          </article>
        </div>

        <form class="answer-form" @submit.prevent="submitAnswer">
          <textarea
            v-model="answerForm.content"
            class="input"
            maxlength="4000"
            :placeholder="t('cottageQuestions.answerPlaceholder')"
            required
          ></textarea>
          <button class="btn" type="submit" :disabled="busy || !answerForm.content.trim()">
            {{ myAnswer?.answered ? t("cottageQuestions.updateAnswer") : t("cottageQuestions.submitAnswer") }}
          </button>
        </form>
      </section>

      <section class="question-history">
        <div class="history-title">
          <h3>{{ t('cottageQuestions.historyTitle') }}</h3>
          <span>{{ t('cottageQuestions.historyCount', { n: history.length }) }}</span>
        </div>
        <article v-for="item in history" :key="item.qid" class="glass-card history-card">
          <div class="history-card-head">
            <span>{{ formatDate(item.question_date) }}</span>
            <span class="reveal-pill small" :class="{ revealed: item.revealed }">
              {{ item.revealed ? t("cottageQuestions.revealed") : t("cottageQuestions.notRevealed") }}
            </span>
          </div>
          <h4>{{ item.prompt }}</h4>
          <div v-if="item.revealed" class="history-answers">
            <p v-for="answer in item.answers" :key="answer.author_uid">
              <strong>{{ answer.author_nickname }}：</strong>{{ answer.content || t("cottageQuestions.noAnswer") }}
            </p>
          </div>
          <p v-else class="answer-placeholder">{{ t("cottageQuestions.sealedHint") }}</p>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  answerDailyQuestion,
  createDailyQuestion,
  fetchDailyQuestions,
  fetchTodayQuestion,
} from "../../../lib/api";
import { parseError } from "../../../utils/helpers";
import { formatLocalDate, localDateKey } from "../../../utils/date";

const showMessage = inject("showMessage", () => {});
const { t } = useI18n();

const loading = ref(true);
const busy = ref(false);
const todayQuestion = ref(null);
const history = ref([]);
const questionForm = reactive({
  prompt: "",
  question_date: localDateKey(),
});
const answerForm = reactive({ content: "" });

const myAnswer = computed(() =>
  (todayQuestion.value?.answers || []).find((answer) => answer.is_self)
);

function formatDate(raw) {
  return formatLocalDate(raw, { month: "long", day: "numeric" });
}

function syncAnswerForm() {
  answerForm.content = myAnswer.value?.content || "";
}

async function load() {
  loading.value = true;
  try {
    const [today, list] = await Promise.all([
      fetchTodayQuestion(),
      fetchDailyQuestions({ limit: 30 }),
    ]);
    todayQuestion.value = today.item || null;
    history.value = (list.items || []).filter((item) => item.qid !== todayQuestion.value?.qid);
    syncAnswerForm();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loading.value = false;
  }
}

async function submitQuestion() {
  if (!questionForm.prompt.trim() || busy.value) return;
  busy.value = true;
  try {
    todayQuestion.value = await createDailyQuestion({
      prompt: questionForm.prompt.trim(),
      question_date: questionForm.question_date || null,
    });
    questionForm.prompt = "";
    await load();
    showMessage(t('cottageQuestions.createdToast'));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

async function submitAnswer() {
  if (!todayQuestion.value || !answerForm.content.trim() || busy.value) return;
  busy.value = true;
  try {
    todayQuestion.value = await answerDailyQuestion(todayQuestion.value.qid, {
      content: answerForm.content.trim(),
    });
    await load();
    showMessage(todayQuestion.value?.revealed ? t('cottageQuestions.revealedToast') : t('cottageQuestions.savedToast'));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    busy.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.cottage-questions {
  display: grid;
  gap: 1rem;
}
.questions-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.questions-header h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #2f3754;
}
.questions-header p {
  margin: 0.35rem 0 0;
  color: var(--text-soft);
  font-size: 0.9rem;
}
.questions-back {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.78);
  color: #3d4665;
  font-size: 0.82rem;
  text-decoration: none;
  white-space: nowrap;
}
.questions-empty {
  padding: 1.2rem;
  color: var(--text-soft);
  text-align: center;
}
.question-composer h3,
.today-question h3,
.history-title h3 {
  margin: 0;
  color: #2f3754;
}
.question-form,
.answer-form {
  display: grid;
  gap: 0.75rem;
}
.question-form textarea,
.answer-form textarea {
  min-height: 7rem;
  resize: vertical;
}
.question-form-actions {
  display: flex;
  gap: 0.7rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.date-input {
  max-width: 180px;
}
.today-question {
  display: grid;
  gap: 1rem;
}
.today-question-top {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}
.question-date {
  display: inline-block;
  margin-bottom: 0.35rem;
  color: #7c3aed;
  font-size: 0.78rem;
  font-weight: 700;
}
.reveal-pill {
  flex: 0 0 auto;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
  color: #64748b;
  font-size: 0.78rem;
}
.reveal-pill.revealed {
  background: rgba(52, 211, 153, 0.18);
  color: #059669;
}
.reveal-pill.small {
  font-size: 0.72rem;
}
.answers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.8rem;
}
.answer-card {
  min-height: 150px;
  padding: 0.9rem;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.26);
  background: rgba(255, 255, 255, 0.55);
}
.answer-card.self {
  border-color: rgba(167, 139, 250, 0.45);
  background: rgba(167, 139, 250, 0.08);
}
.answer-card.hidden {
  background-image: repeating-linear-gradient(
    135deg,
    rgba(148, 163, 184, 0.08) 0,
    rgba(148, 163, 184, 0.08) 8px,
    rgba(255, 255, 255, 0.1) 8px,
    rgba(255, 255, 255, 0.1) 16px
  );
}
.answer-card-head,
.history-card-head,
.history-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}
.answer-card-head strong {
  color: #2f3754;
}
.answer-card-head span,
.history-card-head span,
.history-title span {
  color: var(--text-soft);
  font-size: 0.78rem;
}
.answer-content,
.answer-placeholder {
  margin: 0.75rem 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.65;
  font-size: 0.9rem;
}
.answer-content {
  color: #3d4665;
}
.answer-placeholder {
  color: var(--text-soft);
}
.question-history {
  display: grid;
  gap: 0.75rem;
}
.history-card {
  padding: 1rem;
}
.history-card h4 {
  margin: 0.55rem 0 0;
  color: #2f3754;
}
.history-answers {
  display: grid;
  gap: 0.35rem;
  margin-top: 0.75rem;
}
.history-answers p {
  margin: 0;
  color: #3d4665;
  font-size: 0.86rem;
  line-height: 1.55;
  word-break: break-word;
}
@media (max-width: 768px) {
  .questions-header,
  .today-question-top {
    flex-direction: column;
  }
  .questions-back,
  .date-input {
    width: 100%;
    max-width: none;
    justify-content: center;
  }
}
</style>
