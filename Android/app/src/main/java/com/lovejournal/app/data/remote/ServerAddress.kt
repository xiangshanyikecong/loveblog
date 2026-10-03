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

import com.lovejournal.app.R
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

/**
 * Pure address normalization rules extracted from [ServerConfig] so they can
 * be unit tested on the JVM without Android framework dependencies.
 *
 * Direct backend deployments usually listen on :8000; reverse-proxy
 * deployments expose /api on the domain's default port instead.
 */
internal object ServerAddress {
    const val DEFAULT_PORT = 8000
    private val IPV4_REGEX = Regex("""\d{1,3}(?:\.\d{1,3}){3}""")

    /** [ServerConfig.normalize] — trims, infers scheme and API path/port. */
    fun normalize(raw: String, emulatorDefault: String?, onEmulator: Boolean): String {
        var value = raw.trim().trimEnd('/')
        if (value.isEmpty()) {
            return if (onEmulator) emulatorDefault.orEmpty() else value
        }
        if (!value.startsWith("http://") && !value.startsWith("https://")) {
            value = "https://$value"
        }
        val parsed = value.toHttpUrlOrNull() ?: return value
        val originalSegments = parsed.pathSegments.filter { it.isNotEmpty() }
        val normalizedSegments = normalizeApiPath(parsed, originalSegments)
        val explicitPort = hasExplicitPort(parsed)
        val normalizedPort = when {
            explicitPort -> parsed.port
            shouldUseBackendPort(parsed.host, normalizedSegments) -> DEFAULT_PORT
            else -> parsed.port
        }
        val builder = parsed.newBuilder()
            .port(normalizedPort)
            .encodedPath("/")
            .query(null)
            .fragment(null)
        normalizedSegments.forEach(builder::addPathSegment)
        return builder.build().toString().trimEnd('/')
    }

    /**
     * [ServerConfig.validateAddressInput] — returns the error message resource
     * ID (R.string.server_config_*) or null if OK. Returning a resource id
     * (not a resolved string) keeps the JVM-pure rules testable and lets
     * callers localize.
     */
    fun validateAddressInput(raw: String, allowCleartext: Boolean): Int? {
        val trimmed = raw.trim()
        if (trimmed.isEmpty()) return R.string.server_config_empty
        if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
            return R.string.server_config_incomplete_https
        }
        val parsed = trimmed.toHttpUrlOrNull() ?: return R.string.server_config_invalid
        if (!parsed.isHttps && (!allowCleartext || !isLocalDevelopmentHost(parsed.host))) {
            return R.string.server_config_https_only
        }
        return null
    }

    fun stripApiVersion(value: String): String = when {
        value.endsWith("/api/v1", ignoreCase = true) -> value.dropLast("/v1".length).trimEnd('/')
        value.endsWith("/v1", ignoreCase = true) -> value.dropLast("/v1".length).trimEnd('/')
        else -> value.trimEnd('/')
    }

    fun stripMediaApiPrefix(value: String): String = when {
        value.endsWith("/api/v1", ignoreCase = true) -> value.dropLast("/api/v1".length).trimEnd('/')
        value.endsWith("/v1", ignoreCase = true) -> value.dropLast("/v1".length).trimEnd('/')
        else -> value.trimEnd('/')
    }

    private fun normalizeApiPath(parsed: HttpUrl, segments: List<String>): List<String> {
        if (segments.isEmpty()) {
            return if (shouldUseProxyPath(parsed)) listOf("api", "v1") else listOf("v1")
        }
        if (segments.size == 1 && segments[0].equals("api", ignoreCase = true)) {
            return listOf("api", "v1")
        }
        if (segments.last().equals("v1", ignoreCase = true)) {
            return segments
        }
        return segments + "v1"
    }

    private fun shouldUseProxyPath(parsed: HttpUrl): Boolean {
        val host = parsed.host
        val explicitPort = hasExplicitPort(parsed)
        if (explicitPort && parsed.port == DEFAULT_PORT) return false
        if (host == "10.0.2.2") return false
        if (host.equals("localhost", ignoreCase = true)) return false
        if (isIpLiteral(host)) return false
        if (!host.contains('.')) return false
        return true
    }

    private fun shouldUseBackendPort(host: String, segments: List<String>): Boolean {
        if (segments.firstOrNull()?.equals("api", ignoreCase = true) == true) return false
        if (host == "10.0.2.2") return true
        if (host.equals("localhost", ignoreCase = true)) return true
        if (isIpLiteral(host)) return true
        return !host.contains('.')
    }

    private fun hasExplicitPort(url: HttpUrl): Boolean {
        val defaultPort = when (url.scheme.lowercase()) {
            "https" -> 443
            else -> 80
        }
        return url.port != defaultPort
    }

    private fun isIpLiteral(host: String): Boolean {
        if (host.startsWith("[") && host.endsWith("]")) return true
        return IPV4_REGEX.matches(host)
    }

    private fun isLocalDevelopmentHost(host: String): Boolean {
        if (host.equals("localhost", ignoreCase = true) || host == "10.0.2.2" || host == "::1") return true
        val octets = host.split('.').mapNotNull { it.toIntOrNull() }
        if (octets.size != 4 || octets.any { it !in 0..255 }) return false
        return octets[0] == 10 ||
            (octets[0] == 172 && octets[1] in 16..31) ||
            (octets[0] == 192 && octets[1] == 168) ||
            octets[0] == 127
    }
}
