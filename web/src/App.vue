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
  <router-view />
  <FrontendHeartbeat />
  <AppDialog />
</template>

<script setup>
import FrontendHeartbeat from "./components/FrontendHeartbeat.vue";
import AppDialog from "./components/AppDialog.vue";
</script>

<style>
/* 全局修复 Vditor 工具提示被遮盖的问题 */
/* 使用最高优先级确保工具提示显示 */

/* 工具提示的伪元素 - 最高层级 */
.vditor-tooltipped::before,
.vditor-tooltipped::after {
  z-index: 999999 !important;
  position: absolute !important;
}

/* 所有方向的工具提示 */
.vditor-tooltipped__s::before,
.vditor-tooltipped__s::after,
.vditor-tooltipped__n::before,
.vditor-tooltipped__n::after,
.vditor-tooltipped__w::before,
.vditor-tooltipped__w::after,
.vditor-tooltipped__e::before,
.vditor-tooltipped__e::after,
.vditor-tooltipped__nw::before,
.vditor-tooltipped__nw::after,
.vditor-tooltipped__ne::before,
.vditor-tooltipped__ne::after,
.vditor-tooltipped__sw::before,
.vditor-tooltipped__sw::after,
.vditor-tooltipped__se::before,
.vditor-tooltipped__se::after {
  z-index: 999999 !important;
  position: absolute !important;
}

/* 工具栏按钮的提示 */
.vditor-toolbar__item .vditor-tooltipped::before,
.vditor-toolbar__item .vditor-tooltipped::after {
  z-index: 999999 !important;
  position: absolute !important;
}

/* 确保工具栏按钮有正确的定位上下文 */
.vditor-toolbar__item {
  position: relative !important;
}

/* 其他浮窗元素 */
.vditor-panel,
.vditor-hint,
.vditor-menu,
.vditor-panel--emoji,
.vditor-panel--headings,
.vditor-panel--help,
.vditor-upload,
.vditor-link {
  z-index: 999999 !important;
}

/* 确保所有 Vditor 相关的弹出层都在最上层 */
body > .vditor-panel,
body > .vditor-hint,
body > .vditor-menu {
  z-index: 999999 !important;
}
</style>
