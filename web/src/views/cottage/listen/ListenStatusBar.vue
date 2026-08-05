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
  <div class="status-bar glass-card">
    <div class="status-partners">
      <span
        v-for="p in partners"
        :key="p.user_uid"
        class="status-partner"
        :class="{ 'status-partner--off': !p.netease_logged_in }"
      >
        {{ p.nickname }}
        <span class="status-badge">{{ p.netease_logged_in ? t("listenStatusBar.loggedIn") : t("listenStatusBar.loggedOut") }}</span>
      </span>
    </div>
    <div v-if="lastEventOriginNickname" class="status-origin">
      {{ t("listenStatusBar.lastEventFrom") }}<strong>{{ lastEventOriginNickname }}</strong>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps({
  partners: { type: Array, default: () => [] },
  lastEventOriginUid: { type: String, default: "" }
});

const lastEventOriginNickname = computed(() => {
  if (!props.lastEventOriginUid) return "";
  const hit = (props.partners || []).find((p) => p.user_uid === props.lastEventOriginUid);
  return hit ? hit.nickname : "";
});
</script>

<style scoped>
.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.6rem;
  padding: 0.6rem 0.95rem;
  font-size: 0.84rem;
}

.status-partners {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
}

.status-partner {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: #2f3754;
  font-weight: 600;
}

.status-partner--off {
  color: #94a3b8;
}

.status-badge {
  font-size: 0.72rem;
  font-weight: 500;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.16);
  color: #047857;
}

.status-partner--off .status-badge {
  background: rgba(148, 163, 184, 0.18);
  color: #64748b;
}

.status-origin {
  font-size: 0.78rem;
  color: #64748b;
}

.status-origin strong {
  color: #2f3754;
}

@media (max-width: 768px) {
  .status-bar {
    font-size: 0.78rem;
  }
}
</style>
