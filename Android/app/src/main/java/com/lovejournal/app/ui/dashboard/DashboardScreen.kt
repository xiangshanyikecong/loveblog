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

package com.lovejournal.app.ui.dashboard

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.ui.res.stringResource
import com.lovejournal.app.R
import com.lovejournal.app.data.local.entity.EventEntity
import com.lovejournal.app.data.remote.dto.LoveClock
import com.lovejournal.app.ui.components.LoveEmptyState
import com.lovejournal.app.ui.components.LoveHeroBrush
import com.lovejournal.app.ui.components.LoveSectionTitle
import com.lovejournal.app.ui.components.LoveSoftCard
import com.lovejournal.app.ui.theme.LovePink
import com.lovejournal.app.ui.theme.LoveRose
import kotlinx.coroutines.delay

@Composable
fun DashboardScreen(viewModel: DashboardViewModel = hiltViewModel()) {
    val events by viewModel.events.collectAsStateWithLifecycle()
    val clock by viewModel.clock.collectAsStateWithLifecycle()
    val offline by viewModel.offline.collectAsStateWithLifecycle()
    val onThisDay by viewModel.onThisDay.collectAsStateWithLifecycle()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(
                        MaterialTheme.colorScheme.background,
                        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.08f),
                    ),
                ),
            ),
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item { WelcomeHeader() }
            item { LoveClockCard(clock) }
            onThisDay?.let { od ->
                if (od.years.isNotEmpty()) {
                    item { OnThisDayCard(od) }
                }
            }
            if (offline) item { OfflineBanner() }
            item { LoveSectionTitle(stringResource(R.string.dashboard_upcoming_events), stringResource(R.string.dashboard_upcoming_events_sub)) }
            if (events.isEmpty()) {
                item { LoveEmptyState("📅", stringResource(R.string.dashboard_no_events), stringResource(R.string.dashboard_no_events_sub)) }
            } else {
                items(events, key = { it.eid }) { EventRow(it) }
            }
        }
    }
}

@Composable
private fun WelcomeHeader() {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            stringResource(R.string.dashboard_today_love),
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
        )
        Text(
            stringResource(R.string.dashboard_every_day_story),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun LoveClockCard(initial: LoveClock) {
    var seconds by remember(initial) {
        mutableStateOf(initial.totalSeconds())
    }
    LaunchedEffect(initial) {
        seconds = initial.totalSeconds()
        while (true) {
            delay(1000)
            seconds += 1
        }
    }
    val days = seconds / 86_400
    val h = (seconds % 86_400) / 3_600
    val m = (seconds % 3_600) / 60
    val s = seconds % 60

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.large)
            .background(LoveHeroBrush)
            .padding(24.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(Icons.Default.Favorite, null, tint = Color.White)
                Text(
                    stringResource(R.string.dashboard_love_clock_together),
                    color = Color.White.copy(alpha = 0.9f),
                    style = MaterialTheme.typography.labelLarge,
                )
            }
            Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    days.toString(),
                    color = Color.White,
                    style = MaterialTheme.typography.displaySmall,
                )
                Text(
                    stringResource(R.string.dashboard_day),
                    color = Color.White,
                    style = MaterialTheme.typography.titleLarge,
                    modifier = Modifier.padding(bottom = 4.dp),
                )
            }
            Surface(
                color = Color.White.copy(alpha = 0.18f),
                shape = MaterialTheme.shapes.medium,
            ) {
                Row(
                    Modifier.padding(horizontal = 14.dp, vertical = 9.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Icon(Icons.Default.Schedule, null, tint = Color.White)
                    Text(
                        "%02d:%02d:%02d".format(h, m, s),
                        color = Color.White,
                        style = MaterialTheme.typography.titleMedium,
                    )
                }
            }
        }
    }
}

@Composable
private fun OfflineBanner() {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        shape = MaterialTheme.shapes.medium,
    ) {
        Row(
            Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                Icons.Default.CloudOff,
                null,
                tint = MaterialTheme.colorScheme.error,
            )
            Text(
                stringResource(R.string.dashboard_offline_mode),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

private fun LoveClock.totalSeconds(): Long = days * 86_400 + hours * 3_600 + minutes * 60 + seconds

@Composable
private fun EventRow(event: EventEntity) {
    LoveSoftCard(Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    event.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    event.date,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            event.nextOccurrenceDays?.let { days ->
                Surface(
                    color = MaterialTheme.colorScheme.primaryContainer,
                    shape = MaterialTheme.shapes.small,
                ) {
                    Text(
                        if (days == 0) stringResource(R.string.dashboard_today) else stringResource(R.string.dashboard_days_left, days),
                        Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }
        }
    }
}

/**
 * 那年今日卡片：展示历史上同一天创建的文章 / 相册 / 听过的歌，
 * 数据来自 /v1/memories/on-this-day（与网页端「那年今日」一致）。
 */
@Composable
private fun OnThisDayCard(data: com.lovejournal.app.data.remote.dto.OnThisDayResponse) {
    LoveSoftCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("🕰️", style = MaterialTheme.typography.titleMedium)
                Text(stringResource(R.string.dashboard_on_this_day), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }
            data.years.forEach { year ->
                Text(
                    stringResource(R.string.dashboard_on_this_day_year, year.year),
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
                year.articles.take(2).forEach { article ->
                    Text(stringResource(R.string.dashboard_otd_article, article.title), style = MaterialTheme.typography.bodySmall)
                }
                year.albums.take(2).forEach { album ->
                    Text(stringResource(R.string.dashboard_otd_album, album.title), style = MaterialTheme.typography.bodySmall)
                }
                year.songs.take(2).forEach { song ->
                    Text(stringResource(R.string.dashboard_otd_song, song.name), style = MaterialTheme.typography.bodySmall)
                }
            }
            Text(
                stringResource(R.string.dashboard_otd_totals, data.totals.articles, data.totals.albums, data.totals.songs),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
