/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

// web/src/views/cottage/modules.js

/**
 * @typedef {Object} CottageModule
 * @property {string} key       - 唯一键,用作 v-for :key,kebab-case
 * @property {string} titleKey  - i18n key for the card title
 * @property {string} descKey   - i18n key for the short description
 * @property {string} to        - vue-router 路径,必须命中已注册 cottage 子路由
 * @property {string} icon      - 卡片前缀 emoji 图标
 * @property {string} group     - 所属分组 key,对应 cottageGroups
 */

/**
 * @typedef {Object} CottageGroup
 * @property {string} key       - 分组唯一键
 * @property {string} titleKey  - i18n key for the group title
 * @property {string} emoji     - 分组标题前缀 emoji
 */

/**
 * 首页模块分组(决定渲染顺序与小标题)。
 * @type {CottageGroup[]}
 */
export const cottageGroups = [
  { key: "together-now", titleKey: "cottage.groups.together-now.title", emoji: "💞" },
  { key: "do-together", titleKey: "cottage.groups.do-together.title", emoji: "✨" },
  { key: "our-records", titleKey: "cottage.groups.our-records.title", emoji: "📒" },
  { key: "keep-private", titleKey: "cottage.groups.keep-private.title", emoji: "🤫" }
];

/** @type {CottageModule[]} */
export const cottageModules = [
  {
    key: "chat",
    titleKey: "cottage.modules.chat.title",
    descKey: "cottage.modules.chat.desc",
    to: "/cottage/chat",
    icon: "💬",
    group: "together-now"
  },
  {
    key: "mood",
    titleKey: "cottage.modules.mood.title",
    descKey: "cottage.modules.mood.desc",
    to: "/cottage/mood",
    icon: "😊",
    group: "together-now"
  },
  {
    key: "questions",
    titleKey: "cottage.modules.questions.title",
    descKey: "cottage.modules.questions.desc",
    to: "/cottage/questions",
    icon: "💭",
    group: "together-now"
  },
  {
    key: "check-in",
    titleKey: "cottage.modules.check-in.title",
    descKey: "cottage.modules.check-in.desc",
    to: "/cottage/check-in",
    icon: "📍",
    group: "together-now"
  },
  {
    key: "plans",
    titleKey: "cottage.modules.plans.title",
    descKey: "cottage.modules.plans.desc",
    to: "/cottage/plans",
    icon: "📝",
    group: "do-together"
  },
  {
    key: "wishlist",
    titleKey: "cottage.modules.wishlist.title",
    descKey: "cottage.modules.wishlist.desc",
    to: "/cottage/wishlist",
    icon: "⭐",
    group: "do-together"
  },
  {
    key: "listen",
    titleKey: "cottage.modules.listen.title",
    descKey: "cottage.modules.listen.desc",
    to: "/cottage/listen",
    icon: "🎧",
    group: "do-together"
  },
  {
    key: "watch",
    titleKey: "cottage.modules.watch.title",
    descKey: "cottage.modules.watch.desc",
    to: "/cottage/watch",
    icon: "🎬",
    group: "do-together"
  },
  {
    key: "games",
    titleKey: "cottage.modules.games.title",
    descKey: "cottage.modules.games.desc",
    to: "/cottage/games",
    icon: "🎮",
    group: "do-together"
  },
  {
    key: "reports",
    titleKey: "cottage.modules.reports.title",
    descKey: "cottage.modules.reports.desc",
    to: "/cottage/reports",
    icon: "📊",
    group: "our-records"
  },
  {
    key: "calendar",
    titleKey: "cottage.modules.calendar.title",
    descKey: "cottage.modules.calendar.desc",
    to: "/cottage/calendar",
    icon: "📅",
    group: "our-records"
  },
  {
    key: "ledger",
    titleKey: "cottage.modules.ledger.title",
    descKey: "cottage.modules.ledger.desc",
    to: "/cottage/ledger",
    icon: "💰",
    group: "our-records"
  },
  {
    key: "footprints",
    titleKey: "cottage.modules.footprints.title",
    descKey: "cottage.modules.footprints.desc",
    to: "/cottage/footprints",
    icon: "🗺️",
    group: "our-records"
  },
  {
    key: "period",
    titleKey: "cottage.modules.period.title",
    descKey: "cottage.modules.period.desc",
    to: "/cottage/period",
    icon: "🌸",
    group: "our-records"
  },
  {
    key: "vault",
    titleKey: "cottage.modules.vault.title",
    descKey: "cottage.modules.vault.desc",
    to: "/cottage/vault",
    icon: "🔒",
    group: "keep-private"
  },
  {
    key: "coupons",
    titleKey: "cottage.modules.coupons.title",
    descKey: "cottage.modules.coupons.desc",
    to: "/cottage/coupons",
    icon: "🎟️",
    group: "keep-private"
  },
  {
    key: "reminders",
    titleKey: "cottage.modules.reminders.title",
    descKey: "cottage.modules.reminders.desc",
    to: "/cottage/reminders",
    icon: "🔔",
    group: "keep-private"
  }
];
