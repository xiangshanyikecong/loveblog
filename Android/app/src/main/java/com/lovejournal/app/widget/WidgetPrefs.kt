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

package com.lovejournal.app.widget

import android.content.Context
import androidx.core.content.edit

/**
 * Tiny synchronous store for the home-screen widget's data. The widget runs in
 * a separate process context where Hilt injection is awkward, so the love-days
 * count is mirrored here whenever the dashboard refreshes.
 */
object WidgetPrefs {
    private const val PREFS = "love_widget"
    private const val KEY_DAYS = "love_days"

    fun setLoveDays(context: Context, days: Long) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit { putLong(KEY_DAYS, days) }
    }

    fun loveDays(context: Context): Long =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(KEY_DAYS, 0L)
}
