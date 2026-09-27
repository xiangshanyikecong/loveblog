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

package com.lovejournal.app.ui.cottage.reports

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import com.lovejournal.app.data.remote.dto.CottageMonthlyReportResponse
import com.lovejournal.app.data.remote.dto.CottageReportHighlight
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.util.formatDateTime

private val STAT_LABELS = listOf(
    "checkins" to "报备打卡",
    "moods" to "心情打卡",
    "questions" to "每日一问",
    "answers" to "问题作答",
    "chat_messages" to "悄悄话",
    "wishes_created" to "新增心愿",
    "wishes_completed" to "达成心愿",
    "plans_created" to "新增计划",
    "plans_completed" to "完成计划",
    "reminders_created" to "新增提醒",
)

private fun highlightKindLabel(kind: String): String = when (kind) {
    "wish" -> "心愿"
    "plan" -> "计划"
    "question" -> "每日一问"
    else -> kind
}

@Composable
fun ReportScreen(viewModel: ReportViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LovePage {
    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = { viewModel.prevMonth() }) {
                Icon(Icons.Filled.KeyboardArrowLeft, contentDescription = "上个月")
            }
            Text(
                "${state.year} 年 ${state.month} 月",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            IconButton(onClick = { viewModel.nextMonth() }) {
                Icon(Icons.Filled.KeyboardArrowRight, contentDescription = "下个月")
            }
        }

        AnnualReportSection(state)
        Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
            val report = state.report
            when {
                state.loading && report == null ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                state.error != null && report == null ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("加载失败：${state.error}", color = MaterialTheme.colorScheme.error)
                    }
                report == null ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("这个月还没有数据") }
                else -> ReportContent(report)
            }
        }
    }
    }
}

@Composable
private fun ReportContent(report: CottageMonthlyReportResponse) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Card {
                Column(modifier = Modifier.padding(16.dp)) {
                    STAT_LABELS.chunked(2).forEach { rowItems ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            rowItems.forEach { (key, label) ->
                                StatCell(label, report.stats[key] ?: 0, Modifier.weight(1f))
                            }
                            if (rowItems.size == 1) Spacer(Modifier.weight(1f))
                        }
                        Spacer(Modifier.height(10.dp))
                    }
                }
            }
        }

        if (report.top_moods.isNotEmpty()) {
            item {
                Text("常见心情", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            }
            item {
                Card {
                    Column(modifier = Modifier.padding(12.dp)) {
                        report.top_moods.forEach { mood ->
                            Row(
                                modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                Text("${mood.emoji ?: ""} ${mood.mood}", style = MaterialTheme.typography.bodyMedium)
                                Text("${mood.count} 次", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }

        if (report.highlights.isNotEmpty()) {
            item {
                Text("高光时刻", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            }
            items(report.highlights) { highlight ->
                HighlightCard(highlight)
            }
        }
    }
}

@Composable
private fun StatCell(label: String, count: Int, modifier: Modifier = Modifier) {
    Column(modifier = modifier) {
        Text(
            "$count",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary,
        )
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun HighlightCard(highlight: CottageReportHighlight) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(highlightKindLabel(highlight.kind), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            Column(modifier = Modifier.weight(1f)) {
                Text(highlight.title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
                highlight.occurred_at?.let {
                    Text(formatDateTime(it), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
                }
            }
        }
    }
}

/**
 * 恋爱年报区块（对齐网页端年度报告）：在一起天数、年度统计、年度歌单 Top、
 * 高光时刻摘要。点击年份箭头切换年 ReportViewModel.loadAnnual。
 */
@Composable
private fun AnnualReportSection(state: ReportUiState) {
    val annual = state.annual
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.35f))) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "${annual?.year ?: state.year} 年度报告",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.weight(1f),
                )
                if (state.annualLoading) {
                    CircularProgressIndicator(modifier = Modifier.height(16.dp).padding(0.dp), strokeWidth = 2.dp)
                }
            }
            when {
                annual == null -> Text(
                    state.annualError ?: "暂无年报数据",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                else -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        StatCell("在一起天数", annual.days_together, Modifier.weight(1f))
                        StatCell("文章", annual.stats.articles, Modifier.weight(1f))
                        StatCell("照片", annual.stats.photos, Modifier.weight(1f))
                        StatCell("报备", annual.stats.checkins, Modifier.weight(1f))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        StatCell("悄悄话", annual.stats.messages, Modifier.weight(1f))
                        StatCell("听歌次数", annual.stats.songs_played, Modifier.weight(1f))
                        StatCell("达成心愿", annual.stats.wishes_completed, Modifier.weight(1f))
                        StatCell("时光胶囊", annual.stats.capsules_created, Modifier.weight(1f))
                    }
                    if (annual.top_songs.isNotEmpty()) {
                        Text("年度歌曲 Top${minOf(3, annual.top_songs.size)}", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                        annual.top_songs.take(3).forEachIndexed { i, song ->
                            Text(
                                "${i + 1}. ${song.name} - ${song.artists.joinToString("/")}（${song.played_count} 次）",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                    annual.highlights.take(3).forEach { Text("✨ $it", style = MaterialTheme.typography.bodySmall) }
                    Text(
                        "${annual.stats.songs_minutes} 分钟的共同旋律 · ${annual.stats.capsules_created} 颗时光胶囊",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}
