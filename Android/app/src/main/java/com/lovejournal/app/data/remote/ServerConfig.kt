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

import android.content.Context
import androidx.core.content.edit
import com.lovejournal.app.BuildConfig
import com.lovejournal.app.util.isEmulator
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Holds the runtime-configurable backend address.
 *
 * The server URL used to be hard-coded at build time via
 * [BuildConfig.API_BASE_URL]; it is now overridable from the login screen and
 * persisted to [SharedPreferences] so each couple can point the app at their
 * own self-hosted node without rebuilding. SharedPreferences (not DataStore) is
 * used deliberately so [HostSelectionInterceptor] can read it synchronously.
 */
@Singleton
class ServerConfig @Inject constructor(
    @ApplicationContext context: Context,
    private val cookieJar: AuthCookieJar,
) {
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** Build-time fallback for the emulator, e.g. http://10.0.2.2:8000/v1 */
    private val emulatorDefault: String = BuildConfig.API_BASE_URL.trimEnd('/')

    private val _apiBase = MutableStateFlow(loadInitialApiBase())
    val apiBaseFlow: StateFlow<String> = _apiBase

    /** Full API base without trailing slash, e.g. http://192.168.1.10:8000/v1 or https://demo.com/api/v1 */
    fun apiBase(): String = _apiBase.value

    /** Base used for health checks, e.g. http://192.168.1.10:8000 or https://demo.com/api */
    fun healthBase(): String = stripApiVersion(apiBase())

    /** Health origin for a candidate address without persisting the candidate. */
    fun healthBaseFor(raw: String): String = stripApiVersion(normalize(raw))

    /** Origin used to fetch uploaded media, e.g. http://192.168.1.10:8000 or https://demo.com */
    fun mediaBase(): String = stripMediaApiPrefix(apiBase())

    /** Stable ownership key for local data that must never cross accounts/servers. */
    fun dataScope(uid: String): String = "${apiBase()}|$uid"

    /**
     * Value shown in the login field (origin, no /v1 suffix).
     * Real devices start blank so users are not misled by the emulator-only
     * 10.0.2.2 default; the emulator keeps the build-time shortcut.
     */
    fun displayAddress(): String {
        val saved = prefs.getString(KEY_API_BASE, null)?.takeIf { it.isNotBlank() }
        return if (saved != null) {
            stripApiVersion(saved)
        } else if (isEmulator()) {
            stripApiVersion(emulatorDefault)
        } else {
            ""
        }
    }

    fun setAddress(raw: String) {
        val normalized = normalize(raw)
        if (normalized != _apiBase.value) {
            // Cookies are domain-based and ignore ports/path prefixes. Keeping
            // them across a server switch could send one service's session to
            // another service on the same host.
            cookieJar.clear()
        }
        prefs.edit { putString(KEY_API_BASE, normalized) }
        _apiBase.value = normalized
    }

    /** Resolves a server-relative media path (e.g. /uploads/x.jpg) to an absolute URL. */
    fun mediaUrl(path: String?): String? {
        if (path.isNullOrBlank()) return null
        if (path.startsWith("http://") || path.startsWith("https://")) return path
        val suffix = if (path.startsWith("/")) path else "/$path"
        return mediaBase() + suffix
    }

    /**
     * Validates user input before login. Returns an error message or null if OK.
     * Exposed so the login screen can give immediate feedback without a round trip.
     */
    fun validateAddressInput(raw: String): String? {
        val trimmed = raw.trim()
        if (trimmed.isEmpty()) return "请输入服务器地址"
        if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
            return "请填写完整的 https:// 服务器地址"
        }
        val parsed = trimmed.toHttpUrlOrNull() ?: return "服务器地址格式不正确"
        if (!parsed.isHttps && (!BuildConfig.ALLOW_CLEARTEXT_LOCAL || !isLocalDevelopmentHost(parsed.host))) {
            return "为保护账号和会话，正式版仅允许 HTTPS；本地 HTTP 仅限调试版私有地址"
        }
        return null
    }

    private fun loadInitialApiBase(): String {
        val saved = prefs.getString(KEY_API_BASE, null)?.takeIf { it.isNotBlank() }
        if (saved != null) return saved
        return if (isEmulator()) emulatorDefault else ""
    }

    private fun normalize(raw: String): String {
        var value = raw.trim().trimEnd('/')
        if (value.isEmpty()) {
            return if (isEmulator()) emulatorDefault else value
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

    private fun normalizeApiPath(parsed: okhttp3.HttpUrl, segments: List<String>): List<String> {
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

    private fun shouldUseProxyPath(parsed: okhttp3.HttpUrl): Boolean {
        val host = parsed.host
        val explicitPort = hasExplicitPort(parsed)
        if (explicitPort && parsed.port == DEFAULT_PORT) return false
        if (host == "10.0.2.2") return false
        if (host.equals("localhost", ignoreCase = true)) return false
        if (isIpLiteral(host)) return false
        if (!host.contains('.')) return false
        return true
    }

    /**
     * Direct backend deployments usually listen on :8000. Reverse-proxy
     * deployments expose /api on the domain's default port instead.
     */
    private fun shouldUseBackendPort(host: String, segments: List<String>): Boolean {
        if (segments.firstOrNull()?.equals("api", ignoreCase = true) == true) return false
        if (host == "10.0.2.2") return true
        if (host.equals("localhost", ignoreCase = true)) return true
        if (isIpLiteral(host)) return true
        return !host.contains('.')
    }

    private fun hasExplicitPort(url: okhttp3.HttpUrl): Boolean {
        val defaultPort = when (url.scheme.lowercase()) {
            "https" -> 443
            else -> 80
        }
        return url.port != defaultPort
    }

    private fun stripApiVersion(value: String): String = when {
        value.endsWith("/api/v1", ignoreCase = true) -> value.dropLast("/v1".length).trimEnd('/')
        value.endsWith("/v1", ignoreCase = true) -> value.dropLast("/v1".length).trimEnd('/')
        else -> value.trimEnd('/')
    }

    private fun stripMediaApiPrefix(value: String): String = when {
        value.endsWith("/api/v1", ignoreCase = true) -> value.dropLast("/api/v1".length).trimEnd('/')
        value.endsWith("/v1", ignoreCase = true) -> value.dropLast("/v1".length).trimEnd('/')
        else -> value.trimEnd('/')
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

    private companion object {
        const val PREFS = "love_server_config"
        const val KEY_API_BASE = "api_base"
        const val DEFAULT_PORT = 8000
        val IPV4_REGEX = Regex("""\d{1,3}(?:\.\d{1,3}){3}""")
    }
}
