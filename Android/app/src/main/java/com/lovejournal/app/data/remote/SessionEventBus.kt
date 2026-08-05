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

package com.lovejournal.app.data.remote

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * App-wide signal that the backend rejected our session (HTTP 401). Emitted from
 * the OkHttp layer (synchronous) and collected by a process-level coroutine that
 * clears the cookie + session so the UI falls back to the login screen instead
 * of getting stuck behind a wall of failing requests.
 */
@Singleton
class SessionEventBus @Inject constructor() {

    // replay=0, small buffer so a 401 emitted off the OkHttp thread is never
    // dropped even if the collector hasn't resumed yet.
    private val _sessionExpired = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val sessionExpired: SharedFlow<Unit> = _sessionExpired

    fun notifyExpired() {
        _sessionExpired.tryEmit(Unit)
    }
}
