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
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.glance.GlanceId
import androidx.glance.GlanceModifier
import androidx.glance.action.actionStartActivity
import androidx.glance.action.clickable
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.provideContent
import androidx.glance.appwidget.updateAll
import androidx.glance.background
import androidx.glance.layout.Alignment
import androidx.glance.layout.Column
import androidx.glance.layout.fillMaxSize
import androidx.glance.layout.padding
import androidx.glance.text.FontWeight
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import androidx.glance.unit.ColorProvider
import androidx.compose.ui.graphics.Color
import com.lovejournal.app.MainActivity

class LoveDaysWidget : GlanceAppWidget() {

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val days = WidgetPrefs.loveDays(context)
        provideContent {
            WidgetContent(days)
        }
    }

    @Composable
    private fun WidgetContent(days: Long) {
        Column(
            modifier = GlanceModifier
                .fillMaxSize()
                .background(Color(0xFFE5739B))
                .padding(12.dp)
                .clickable(actionStartActivity<MainActivity>()),
            verticalAlignment = Alignment.CenterVertically,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = "在一起",
                style = TextStyle(color = ColorProvider(Color.White), fontSize = 14.sp),
            )
            Text(
                text = days.toString(),
                style = TextStyle(
                    color = ColorProvider(Color.White),
                    fontSize = 40.sp,
                    fontWeight = FontWeight.Bold,
                ),
            )
            Text(
                text = "天",
                style = TextStyle(color = ColorProvider(Color.White), fontSize = 14.sp),
            )
        }
    }

    companion object {
        suspend fun requestUpdate(context: Context) {
            LoveDaysWidget().updateAll(context)
        }
    }
}
