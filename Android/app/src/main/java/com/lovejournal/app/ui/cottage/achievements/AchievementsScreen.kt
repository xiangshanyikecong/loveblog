/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

package com.lovejournal.app.ui.cottage.achievements

import androidx.compose.foundation.BorderStroke
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.dto.AchievementsResponse
import com.lovejournal.app.data.remote.dto.BadgeProgress
import com.lovejournal.app.data.remote.dto.CoupleLevel
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSoftCard
import com.lovejournal.app.ui.components.asString
import com.lovejournal.app.ui.theme.LoveRose

// tier → 主题色：未达标徽章整体置灰，达成徽章按 bronze/silver/gold 着色。
private val TierBronze = Color(0xFFB0733C)
private val TierSilver = Color(0xFF8E9AA6)
private val TierGold = Color(0xFFD4A017)

private fun tierColor(tier: String): Color = when (tier) {
    "gold" -> TierGold
    "silver" -> TierSilver
    "bronze" -> TierBronze
    else -> Color(0xFF9E9E9E)
}

private fun tierLabelRes(tier: String): Int = when (tier) {
    "gold" -> R.string.achievement_tier_gold
    "silver" -> R.string.achievement_tier_silver
    "bronze" -> R.string.achievement_tier_bronze
    else -> R.string.achievement_tier_none
}

// 统计摘要展示顺序（键为后端 stats 字典的键，未知键忽略）。
private val STAT_LABELS = listOf(
    "love_days" to R.string.achievement_stat_love_days,
    "articles" to R.string.achievement_stat_articles,
    "albums" to R.string.achievement_stat_albums,
    "album_media" to R.string.achievement_stat_album_media,
    "moments" to R.string.achievement_stat_moments,
    "capsules" to R.string.achievement_stat_capsules,
    "checkins" to R.string.achievement_stat_checkins,
    "checkin_streak_days" to R.string.achievement_stat_checkin_streak,
    "moods" to R.string.achievement_stat_moods,
    "mood_streak_days" to R.string.achievement_stat_mood_streak,
    "chat_messages" to R.string.achievement_stat_chat_messages,
    "games_played" to R.string.achievement_stat_games_played,
    "wishes_total" to R.string.achievement_stat_wishes_total,
    "wishes_completed" to R.string.achievement_stat_wishes_completed,
    "songs_played" to R.string.achievement_stat_songs_played,
)

@Composable
fun AchievementsScreen(viewModel: AchievementsViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LovePage {
        Box(modifier = Modifier.fillMaxSize()) {
            val data = state.data
            when {
                state.loading && data == null ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                state.error != null && data == null ->
                    Column(
                        modifier = Modifier.fillMaxSize().padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Text(
                            stringResource(R.string.msg_load_failed_with_error, state.error?.asString() ?: ""),
                            color = MaterialTheme.colorScheme.error,
                            textAlign = TextAlign.Center,
                        )
                        Spacer(Modifier.height(12.dp))
                        Button(onClick = viewModel::refresh) { Text(stringResource(R.string.btn_refresh)) }
                    }
                data == null ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(stringResource(R.string.achievement_no_data), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                else -> AchievementsContent(data)
            }
        }
    }
}

@Composable
private fun AchievementsContent(data: AchievementsResponse) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item { LevelCard(data.level) }
        item { StatsCard(data.stats) }
        item {
            Text(stringResource(R.string.achievement_badges_title), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        }
        data.badges.chunked(3).forEach { rowBadges ->
            item(key = rowBadges.joinToString("_") { it.code }) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    rowBadges.forEach { badge -> BadgeCard(badge, Modifier.weight(1f)) }
                    repeat(3 - rowBadges.size) { Spacer(Modifier.weight(1f)) }
                }
            }
        }
    }
}

/** 等级卡：等级/称号/积分、通往下一等级的进度条与目标。 */
@Composable
private fun LevelCard(level: CoupleLevel) {
    LoveSoftCard(Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Surface(
                    shape = CircleShape,
                    color = LoveRose.copy(alpha = 0.16f),
                ) {
                    Box(modifier = Modifier.padding(14.dp), contentAlignment = Alignment.Center) {
                        Text(
                            stringResource(R.string.achievement_level_badge, level.level),
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                            color = LoveRose,
                        )
                    }
                }
                Column(modifier = Modifier.weight(1f)) {
                    Text(level.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text(
                        stringResource(R.string.achievement_points, level.points),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            LinearProgressIndicator(
                progress = { (level.progress_percent.coerceIn(0, 100)) / 100f },
                modifier = Modifier.fillMaxWidth().height(8.dp).clip(MaterialTheme.shapes.extraLarge),
            )
            if (level.next_level_points != null && !level.next_level_title.isNullOrBlank()) {
                Text(
                    stringResource(R.string.achievement_next_level, level.next_level_title, level.next_level_points, level.progress_percent),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                Text(
                    stringResource(R.string.achievement_max_level),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

/** 统计摘要：双方共同数据的全量聚合。 */
@Composable
private fun StatsCard(stats: Map<String, Int>) {
    Card {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                stringResource(R.string.achievement_stats_title),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 12.dp),
            )
            STAT_LABELS.chunked(3).forEach { rowItems ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    rowItems.forEach { (key, labelRes) ->
                        StatCell(stringResource(labelRes), stats[key] ?: 0, Modifier.weight(1f))
                    }
                    repeat(3 - rowItems.size) { Spacer(Modifier.weight(1f)) }
                }
            }
        }
    }
}

@Composable
private fun StatCell(label: String, count: Int, modifier: Modifier = Modifier) {
    Column(modifier = modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            "$count",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary,
        )
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
    }
}

/** 徽章卡：图标、tier 描边着色、未达成置灰 + current/next_target 进度。 */
@Composable
private fun BadgeCard(badge: BadgeProgress, modifier: Modifier = Modifier) {
    val tint = if (badge.achieved) tierColor(badge.tier) else MaterialTheme.colorScheme.outline
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = if (badge.achieved) tint.copy(alpha = 0.10f) else MaterialTheme.colorScheme.surface.copy(alpha = 0.85f),
        ),
        border = if (badge.achieved) BorderStroke(1.dp, tint.copy(alpha = 0.6f)) else null,
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp, horizontal = 8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                badge.icon,
                style = MaterialTheme.typography.headlineMedium,
                color = if (badge.achieved) Color.Unspecified else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f),
            )
            Text(
                badge.name,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                color = if (badge.achieved) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                textAlign = TextAlign.Center,
            )
            Text(
                stringResource(tierLabelRes(badge.tier)),
                style = MaterialTheme.typography.labelSmall,
                color = if (badge.achieved) tint else MaterialTheme.colorScheme.outline,
            )
            if (!badge.achieved && badge.next_target != null && badge.next_target > 0) {
                Text(
                    stringResource(R.string.achievement_badge_progress, badge.current, badge.next_target),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                LinearProgressIndicator(
                    progress = { (badge.current.toFloat() / badge.next_target).coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth().height(4.dp).clip(MaterialTheme.shapes.extraLarge),
                )
            }
        }
    }
}
