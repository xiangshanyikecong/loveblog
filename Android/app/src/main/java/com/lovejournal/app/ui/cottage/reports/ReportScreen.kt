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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.dto.CottageMonthlyReportResponse
import com.lovejournal.app.data.remote.dto.CottageReportHighlight
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.asString
import com.lovejournal.app.util.formatDateTime

private val STAT_LABELS = listOf(
    "checkins" to R.string.report_stat_checkins,
    "moods" to R.string.report_stat_moods,
    "questions" to R.string.report_stat_questions,
    "answers" to R.string.report_stat_answers,
    "chat_messages" to R.string.report_stat_chat_messages,
    "wishes_created" to R.string.report_stat_wishes_created,
    "wishes_completed" to R.string.report_stat_wishes_completed,
    "plans_created" to R.string.report_stat_plans_created,
    "plans_completed" to R.string.report_stat_plans_completed,
    "reminders_created" to R.string.report_stat_reminders_created,
)

@Composable
private fun highlightKindLabel(kind: String): String = when (kind) {
    "wish" -> stringResource(R.string.report_kind_wish)
    "plan" -> stringResource(R.string.report_kind_plan)
    "question" -> stringResource(R.string.report_kind_question)
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
                Icon(Icons.Filled.KeyboardArrowLeft, contentDescription = stringResource(R.string.report_prev_month))
            }
            Text(
                stringResource(R.string.report_month_format, state.year, state.month),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            IconButton(onClick = { viewModel.nextMonth() }) {
                Icon(Icons.Filled.KeyboardArrowRight, contentDescription = stringResource(R.string.report_next_month))
            }
        }

        AnnualReportSection(state)
        if (state.aiEnabled) AiReportSection(state, onGenerate = viewModel::generateAiText, onDismiss = viewModel::dismissAiText)
        Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
            val report = state.report
            when {
                state.loading && report == null ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                state.error != null && report == null ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(stringResource(R.string.msg_load_failed_with_error, state.error?.asString() ?: ""), color = MaterialTheme.colorScheme.error)
                    }
                report == null ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text(stringResource(R.string.report_no_data)) }
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
                            rowItems.forEach { (key, labelRes) ->
                                StatCell(stringResource(labelRes), report.stats[key] ?: 0, Modifier.weight(1f))
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
                Text(stringResource(R.string.report_common_moods), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
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
                                Text(stringResource(R.string.report_times, mood.count), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }

        if (report.highlights.isNotEmpty()) {
            item {
                Text(stringResource(R.string.report_highlights), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
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
 * AI 月报文案区块：按当前选中月份生成一段文案，卡片展示并可一键复制。
 * 仅当 /ai/status enabled 且具备 monthly_report 特性时由外层显示。
 */
@Composable
private fun AiReportSection(state: ReportUiState, onGenerate: () -> Unit, onDismiss: () -> Unit) {
    val clipboard = LocalClipboardManager.current
    var copied by remember { mutableStateOf(false) }

    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.45f))) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    stringResource(R.string.ai_report_title),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.weight(1f),
                )
                if (state.aiLoading) {
                    CircularProgressIndicator(modifier = Modifier.height(16.dp), strokeWidth = 2.dp)
                } else {
                    OutlinedButton(onClick = onGenerate) { Text(stringResource(R.string.ai_report_button)) }
                }
            }
            state.aiError?.let {
                Text(it.asString(), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }
            state.aiText?.let { text ->
                Text(
                    text,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 200.dp)
                        .verticalScroll(rememberScrollState()),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = {
                        clipboard.setText(AnnotatedString(text))
                        copied = true
                    }) { Text(stringResource(if (copied) R.string.ai_copied else R.string.ai_copy)) }
                    TextButton(onClick = onDismiss) { Text(stringResource(R.string.btn_close)) }
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
                    stringResource(R.string.report_annual_title, annual?.year ?: state.year),
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
                    state.annualError?.asString() ?: stringResource(R.string.report_no_annual_data),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                else -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        StatCell(stringResource(R.string.report_stat_days_together), annual.days_together, Modifier.weight(1f))
                        StatCell(stringResource(R.string.report_stat_articles), annual.stats.articles, Modifier.weight(1f))
                        StatCell(stringResource(R.string.report_stat_photos), annual.stats.photos, Modifier.weight(1f))
                        StatCell(stringResource(R.string.report_stat_checkin), annual.stats.checkins, Modifier.weight(1f))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        StatCell(stringResource(R.string.report_stat_chat_messages), annual.stats.messages, Modifier.weight(1f))
                        StatCell(stringResource(R.string.report_stat_songs_played), annual.stats.songs_played, Modifier.weight(1f))
                        StatCell(stringResource(R.string.report_stat_wishes_completed), annual.stats.wishes_completed, Modifier.weight(1f))
                        StatCell(stringResource(R.string.report_stat_capsules), annual.stats.capsules_created, Modifier.weight(1f))
                    }
                    if (annual.top_songs.isNotEmpty()) {
                        Text(stringResource(R.string.report_annual_top_songs, minOf(3, annual.top_songs.size)), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                        annual.top_songs.take(3).forEachIndexed { i, song ->
                            Text(
                                stringResource(R.string.report_annual_song_line, i + 1, song.name, song.artists.joinToString("/"), song.played_count),
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                    annual.highlights.take(3).forEach { Text("✨ \$it", style = MaterialTheme.typography.bodySmall) }
                    Text(
                        stringResource(R.string.report_annual_summary, annual.stats.songs_minutes, annual.stats.capsules_created),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}
