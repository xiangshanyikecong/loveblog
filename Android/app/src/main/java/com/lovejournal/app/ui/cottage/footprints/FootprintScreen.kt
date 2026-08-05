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

package com.lovejournal.app.ui.cottage.footprints

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.data.remote.dto.FootprintCity
import com.lovejournal.app.data.remote.dto.FootprintRecent
import com.lovejournal.app.data.remote.dto.FootprintResponse
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.util.formatDateTime

@Composable
fun FootprintScreen(viewModel: FootprintViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val data = state.data

    LovePage {
    when {
        state.loading && data == null ->
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        state.error != null && data == null ->
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("加载失败：${state.error}", color = MaterialTheme.colorScheme.error)
            }
        data == null || (data.cities.isEmpty() && data.recent.isEmpty()) ->
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("还没有足迹，去「报备打卡」解锁你们去过的城市吧")
            }
        else -> FootprintContent(data)
    }
    }
}

@Composable
private fun FootprintContent(data: FootprintResponse) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("我们的足迹", style = MaterialTheme.typography.labelMedium)
                    Text(
                        "${data.total_cities} 座城市 · ${data.total_checkins} 次打卡",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }

        if (data.cities.isNotEmpty()) {
            item {
                Text("去过的地方", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            }
            items(data.cities, key = { it.city }) { city ->
                CityCard(city)
            }
        }

        if (data.recent.isNotEmpty()) {
            item {
                Text("最近足迹", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            }
            items(data.recent.size) { index ->
                RecentRow(data.recent[index])
            }
        }
    }
}

@Composable
private fun CityCard(city: FootprintCity) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(city.city, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(
                    "最近 ${formatDateTime(city.last_at)}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                "${city.count} 次",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

@Composable
private fun RecentRow(recent: FootprintRecent) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 4.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("📍", style = MaterialTheme.typography.bodyMedium)
        Column(modifier = Modifier.weight(1f)) {
            Text(recent.city, style = MaterialTheme.typography.bodyMedium)
            Text(
                "${recent.author_nickname} · ${formatDateTime(recent.created_at)}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
