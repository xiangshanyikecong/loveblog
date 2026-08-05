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

// Love Journal 一起听 (listen-together) upstream launcher.
//
// We run the MAINTAINED fork NeteaseCloudMusicApiEnhanced (npm package
// @neteasecloudmusicapienhanced/api) instead of the original Binaryify
// NeteaseCloudMusicApi, which was ARCHIVED 2024-04-16 and no longer copes
// with NetEase's current login / risk-control.
//
// We delegate to the package's OWN app.js launcher on purpose — NOT a bare
// serveNcmApi() call. app.js refreshes the guest `anonymous_token` on startup
// (via generateConfig()). Without that refresh NetEase increasingly answers
// authenticated calls with "需要验证" / code 301, which our backend reads as
// "login expired" and silently drops the partner's imported cookie — exactly
// the "导入 cookie 后登录态还是会丢" symptom. app.js listens on PORT (default
// 3000); the backend reaches it at http://netease:3000 over the compose net.
require('@neteasecloudmusicapienhanced/api/app.js')
