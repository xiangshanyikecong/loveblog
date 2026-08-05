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

import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Watches every response for HTTP 401 (expired / revoked session — e.g. the
 * backend bumped `session_version` on logout elsewhere) and raises a global
 * [SessionEventBus] signal. The login endpoint itself is exempt so a wrong
 * password on the login screen doesn't masquerade as a session expiry.
 */
@Singleton
class AuthStatusInterceptor @Inject constructor(
    private val sessionEventBus: SessionEventBus,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val response = chain.proceed(request)
        if (response.code == 401 && !isAuthEndpoint(request.url.encodedPath)) {
            sessionEventBus.notifyExpired()
        }
        return response
    }

    private fun isAuthEndpoint(path: String): Boolean =
        path.endsWith("/auth/login") || path.endsWith("/auth/logout")
}
