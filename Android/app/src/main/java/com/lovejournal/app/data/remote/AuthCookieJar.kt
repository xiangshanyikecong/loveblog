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
import android.content.SharedPreferences
import androidx.core.content.edit
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Persists session cookies (notably the backend's HttpOnly `access_token`) so
 * login survives process death. The backend authenticates either via this
 * cookie or an `Authorization: Bearer` header; the mobile login endpoint only
 * sets the cookie, so we capture and replay it.
 *
 * Security: the cookie store holds the session token, so it is kept in
 * [EncryptedSharedPreferences] (AES-256, key in the Android Keystore) instead
 * of plaintext, and the app disables backup/transfer of this file. A synchronous
 * store (not DataStore) is used deliberately: [CookieJar] is a synchronous API
 * and must read/write without suspending.
 */
@Singleton
class AuthCookieJar @Inject constructor(
    @ApplicationContext private val context: Context,
) : CookieJar {

    private val prefs: SharedPreferences = createEncryptedPrefs(context)

    @Volatile
    private var cached: MutableMap<String, Cookie> = load()

    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        if (cookies.isEmpty()) return
        synchronized(this) {
            for (cookie in cookies) {
                // Preserve every security attribute exactly as the server sent
                // it. A Secure cookie must never be downgraded for HTTP.
                cached[cookie.name] = cookie
            }
            persist()
        }
    }

    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val now = System.currentTimeMillis()
        synchronized(this) {
            val valid = cached.values.filter { it.expiresAt > now }
            if (valid.size != cached.size) {
                cached = valid.associateBy { it.name }.toMutableMap()
                persist()
            }
            return valid.filter { it.matches(url) }
        }
    }

    fun hasSession(): Boolean = synchronized(this) {
        val now = System.currentTimeMillis()
        cached.values.any { it.name == ACCESS_TOKEN && it.expiresAt > now }
    }

    fun clear() {
        synchronized(this) {
            cached.clear()
            prefs.edit { clear() }
        }
    }

    private fun persist() {
        prefs.edit {
            clear()
            cached.values.forEachIndexed { index, cookie ->
                putString("cookie_$index", serialize(cookie))
            }
            putInt(COUNT, cached.size)
        }
    }

    private fun load(): MutableMap<String, Cookie> {
        val count = prefs.getInt(COUNT, 0)
        val map = mutableMapOf<String, Cookie>()
        for (i in 0 until count) {
            val raw = prefs.getString("cookie_$i", null) ?: continue
            deserialize(raw)?.let { map[it.name] = it }
        }
        return map
    }

    private fun serialize(cookie: Cookie): String = listOf(
        cookie.name,
        cookie.value,
        cookie.domain,
        cookie.path,
        cookie.expiresAt.toString(),
        cookie.secure.toString(),
        cookie.httpOnly.toString(),
        cookie.hostOnly.toString(),
    ).joinToString("\u0001")

    private fun deserialize(raw: String): Cookie? {
        val parts = raw.split("\u0001")
        if (parts.size < 8) return null
        return try {
            val builder = Cookie.Builder()
                .name(parts[0])
                .value(parts[1])
                .path(parts[3])
                .expiresAt(parts[4].toLong())
            if (parts[7].toBoolean()) builder.hostOnlyDomain(parts[2]) else builder.domain(parts[2])
            if (parts[5].toBoolean()) builder.secure()
            if (parts[6].toBoolean()) builder.httpOnly()
            builder.build()
        } catch (e: Exception) {
            null
        }
    }

    private companion object {
        const val PREFS = "love_cookies_enc"
        const val COUNT = "cookie_count"
        const val ACCESS_TOKEN = "access_token"

        /**
         * Builds the encrypted store, tolerating a corrupted keyset (which can
         * happen after an OS restore onto new hardware): drop the bad file and
         * rebuild once so the app degrades to "logged out" instead of crashing
         * on every launch.
         */
        fun createEncryptedPrefs(context: Context): SharedPreferences {
            fun build(): SharedPreferences {
                val masterKey = MasterKey.Builder(context)
                    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                    .build()
                return EncryptedSharedPreferences.create(
                    context,
                    PREFS,
                    masterKey,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
                )
            }
            return try {
                build()
            } catch (e: Exception) {
                context.deleteSharedPreferences(PREFS)
                build()
            }
        }
    }
}
