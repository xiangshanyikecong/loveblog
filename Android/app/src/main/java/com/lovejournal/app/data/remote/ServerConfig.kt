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
import androidx.annotation.StringRes
import androidx.core.content.edit
import com.lovejournal.app.BuildConfig
import com.lovejournal.app.util.isEmulator
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
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
     * Validates user input before login. Returns the error message resource
     * ID (R.string.server_config_*) or null if OK. Exposed so the login
     * screen can give immediate feedback without a round trip.
     */
    fun validateAddressInput(raw: String): Int? =
        ServerAddress.validateAddressInput(raw, BuildConfig.ALLOW_CLEARTEXT_LOCAL)

    private fun loadInitialApiBase(): String {
        val saved = prefs.getString(KEY_API_BASE, null)?.takeIf { it.isNotBlank() }
        if (saved != null) return saved
        return if (isEmulator()) emulatorDefault else ""
    }

    private fun normalize(raw: String): String =
        ServerAddress.normalize(raw, emulatorDefault, isEmulator())

    private fun stripApiVersion(value: String): String = ServerAddress.stripApiVersion(value)

    private fun stripMediaApiPrefix(value: String): String = ServerAddress.stripMediaApiPrefix(value)

    private companion object {
        const val PREFS = "love_server_config"
        const val KEY_API_BASE = "api_base"
    }
}
