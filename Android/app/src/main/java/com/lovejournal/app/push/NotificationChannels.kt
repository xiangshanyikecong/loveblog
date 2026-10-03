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

package com.lovejournal.app.push

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import com.lovejournal.app.R

object NotificationChannels {
    const val MESSAGES = "love_messages"
    const val MOODS = "love_moods"
    const val EVENTS = "love_events"
    const val TAPS = "love_taps"

    fun register(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        manager.createNotificationChannel(
            NotificationChannel(MESSAGES, context.getString(R.string.notification_channel_messages), NotificationManager.IMPORTANCE_HIGH),
        )
        manager.createNotificationChannel(
            NotificationChannel(MOODS, context.getString(R.string.notification_channel_moods), NotificationManager.IMPORTANCE_DEFAULT),
        )
        manager.createNotificationChannel(
            NotificationChannel(EVENTS, context.getString(R.string.notification_channel_events), NotificationManager.IMPORTANCE_DEFAULT),
        )
        // 轻触回应（cottage.tap）：高优先级 + 震动，让「敲一敲/心跳」有实感。
        val taps = NotificationChannel(TAPS, context.getString(R.string.notification_channel_taps), NotificationManager.IMPORTANCE_HIGH).apply {
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 60, 80, 60)
        }
        manager.createNotificationChannel(taps)
    }

    fun channelForType(type: String?): String = when {
        type == null -> MESSAGES
        type.startsWith("cottage.tap") -> TAPS
        type.startsWith("mood") -> MOODS
        type.startsWith("event") -> EVENTS
        else -> MESSAGES
    }
}
