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
    <ModuleTabs :items="interactionTabs" :label="t('messages.tabAriaLabel')" />
    <MessageBoard :title="t('messages.messageBoard')" />
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
import ModuleTabs from "../components/ModuleTabs.vue";
import MessageBoard from "../components/MessageBoard.vue";

const { t } = useI18n();
const interactionTabs = [
  { label: t("messages.tabMessages"), to: "/messages" },
  { label: t("messages.tabNotifications"), to: "/notifications" }
];
</script>
