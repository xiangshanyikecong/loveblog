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

package com.lovejournal.app.data.prefs

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore(name = "love_session")

data class SessionState(
    val loggedIn: Boolean = false,
    val uid: String? = null,
    val nickname: String? = null,
    val role: String? = null,
    val avatar: String? = null,
)

@Singleton
class SessionManager @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val ds = context.dataStore

    val sessionFlow: Flow<SessionState> = ds.data.map { p ->
        SessionState(
            loggedIn = p[LOGGED_IN] ?: false,
            uid = p[UID],
            nickname = p[NICKNAME],
            role = p[ROLE],
            avatar = p[AVATAR],
        )
    }

    val loveDaysFlow: Flow<Long> = ds.data.map { it[LOVE_DAYS] ?: 0L }

    suspend fun setLoggedIn(uid: String, nickname: String, role: String, avatar: String?) {
        ds.edit { p ->
            p[LOGGED_IN] = true
            p[UID] = uid
            p[NICKNAME] = nickname
            p[ROLE] = role
            if (avatar != null) p[AVATAR] = avatar else p.remove(AVATAR)
        }
    }

    suspend fun setLoveDays(days: Long) {
        ds.edit { it[LOVE_DAYS] = days }
        com.lovejournal.app.widget.WidgetPrefs.setLoveDays(context, days)
    }

    suspend fun clear() {
        ds.edit { it.clear() }
        // Reset the home-screen widget so it doesn't keep showing the previous
        // couple's love-days count after logout.
        com.lovejournal.app.widget.WidgetPrefs.setLoveDays(context, 0)
        runCatching { com.lovejournal.app.widget.LoveDaysWidget.requestUpdate(context) }
    }

    private companion object {
        val LOGGED_IN = booleanPreferencesKey("logged_in")
        val UID = stringPreferencesKey("uid")
        val NICKNAME = stringPreferencesKey("nickname")
        val ROLE = stringPreferencesKey("role")
        val AVATAR = stringPreferencesKey("avatar")
        val LOVE_DAYS = longPreferencesKey("love_days")
    }
}
