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

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import i18n from './locales'
import { initPwa } from "./lib/pwa";
import { useAuth } from './stores/auth'
import './styles.css'

const { initAuth } = useAuth()
initAuth()

const app = createApp(App)
app.use(router)
app.use(i18n)
app.mount('#app')

initPwa(router)
