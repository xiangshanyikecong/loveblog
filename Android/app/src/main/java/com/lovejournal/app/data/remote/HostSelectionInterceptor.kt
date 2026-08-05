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

import com.lovejournal.app.BuildConfig
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Rewrites every outgoing request's scheme/host/port/path-prefix to the address
 * configured in [ServerConfig], so the build-time [BuildConfig.API_BASE_URL]
 * acts only as a default. Retrofit still uses the build-time base for its
 * relative path resolution; this interceptor swaps the origin (and any path
 * prefix such as `/api`) at request time, preserving the endpoint path and
 * query parameters.
 */
@Singleton
class HostSelectionInterceptor @Inject constructor(
    private val serverConfig: ServerConfig,
) : Interceptor {

    // How many leading path segments belong to the build-time base (e.g. "v1").
    private val baseSegmentCount: Int =
        BuildConfig.API_BASE_URL.toHttpUrlOrNull()
            ?.pathSegments
            ?.count { it.isNotEmpty() }
            ?: 1

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        if (request.tag(BypassHostSelection::class.java) != null) {
            return chain.proceed(request)
        }
        val configured = serverConfig.apiBase().toHttpUrlOrNull()
            ?: return chain.proceed(request)

        val endpointSegments = request.url.pathSegments
            .filter { it.isNotEmpty() }
            .drop(baseSegmentCount)

        val builder = HttpUrl.Builder()
            .scheme(configured.scheme)
            .host(configured.host)
            .port(configured.port)

        configured.pathSegments.filter { it.isNotEmpty() }.forEach { builder.addPathSegment(it) }
        endpointSegments.forEach { builder.addPathSegment(it) }

        request.url.queryParameterNames.forEach { name ->
            request.url.queryParameterValues(name).forEach { value ->
                builder.addQueryParameter(name, value)
            }
        }

        return chain.proceed(request.newBuilder().url(builder.build()).build())
    }
}
