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
  <section class="glass-card rounded-2xl border border-white/70 p-5">
    <h2 class="text-lg font-semibold text-sakura-800">{{ t("commentBox.title") }}</h2>
    <p class="mt-2 text-sm text-sakura-700">
      {{ t("commentBox.desc") }}
    </p>
    <div class="mt-4 rounded-xl border border-dashed border-sakura-300 bg-white/60 p-3 text-sm text-sakura-700">
      {{ t("commentBox.example") }}
    </div>
  </section>
</template>

<script setup>
import { useI18n } from "vue-i18n";

const { t } = useI18n();
</script>
