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

package com.lovejournal.app.ui.cottage

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.lovejournal.app.R
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSoftCard
import com.lovejournal.app.ui.theme.LoveLavender
import com.lovejournal.app.ui.theme.LoveMint
import com.lovejournal.app.ui.theme.LovePeach
import com.lovejournal.app.ui.theme.LoveRose

object CottageRoute {
    const val HUB = "cottage"; const val CHAT = "cottage/chat"; const val MOOD = "cottage/mood"; const val WISHLIST = "cottage/wishlist"; const val QUESTIONS = "cottage/questions"; const val GAMES = "cottage/games"; const val WATCH = "cottage/watch"; const val LISTEN = "cottage/listen"; const val COUPONS = "cottage/coupons"; const val REMINDERS = "cottage/reminders"; const val LEDGER = "cottage/ledger"; const val PERIOD = "cottage/period"; const val REPORTS = "cottage/reports"; const val FOOTPRINTS = "cottage/footprints"; const val PLANS = "cottage/plans"; const val CHECKINS = "checkins"; const val VAULT = "cottage/vault"; const val CANVAS = "cottage/games/canvas"; const val CANVAS_GALLERY = "cottage/games/canvas/gallery"; const val CANVAS_ARTWORK = "cottage/games/canvas/gallery/artwork"
}

private data class CottageFeature(val emoji: String, val titleRes: Int, val subtitleRes: Int, val route: String, val accent: Color)
private val features = listOf(
    CottageFeature("💬", R.string.cottage_feature_chat, R.string.cottage_feature_chat_sub, CottageRoute.CHAT, LoveRose), CottageFeature("🌤️", R.string.cottage_feature_mood, R.string.cottage_feature_mood_sub, CottageRoute.MOOD, LovePeach),
    CottageFeature("📍", R.string.cottage_feature_checkin, R.string.cottage_feature_checkin_sub, CottageRoute.CHECKINS, LoveMint), CottageFeature("💝", R.string.cottage_feature_wishlist, R.string.cottage_feature_wishlist_sub, CottageRoute.WISHLIST, LoveLavender),
    CottageFeature("💌", R.string.cottage_feature_questions, R.string.cottage_feature_questions_sub, CottageRoute.QUESTIONS, LoveRose), CottageFeature("📺", R.string.cottage_feature_watch, R.string.cottage_feature_watch_sub, CottageRoute.WATCH, LoveLavender),
    CottageFeature("🎮", R.string.cottage_feature_games, R.string.cottage_feature_games_sub, CottageRoute.GAMES, LoveMint), CottageFeature("🎧", R.string.cottage_feature_listen, R.string.cottage_feature_listen_sub, CottageRoute.LISTEN, LovePeach),
    CottageFeature("🎟️", R.string.cottage_feature_coupons, R.string.cottage_feature_coupons_sub, CottageRoute.COUPONS, LoveRose), CottageFeature("🔔", R.string.cottage_feature_reminders, R.string.cottage_feature_reminders_sub, CottageRoute.REMINDERS, LovePeach),
    CottageFeature("🗓️", R.string.cottage_feature_plans, R.string.cottage_feature_plans_sub, CottageRoute.PLANS, LoveLavender), CottageFeature("💰", R.string.cottage_feature_ledger, R.string.cottage_feature_ledger_sub, CottageRoute.LEDGER, LoveMint),
    CottageFeature("📊", R.string.cottage_feature_reports, R.string.cottage_feature_reports_sub, CottageRoute.REPORTS, LoveRose), CottageFeature("🗺️", R.string.cottage_feature_footprints, R.string.cottage_feature_footprints_sub, CottageRoute.FOOTPRINTS, LoveMint),
    CottageFeature("🌸", R.string.cottage_feature_period, R.string.cottage_feature_period_sub, CottageRoute.PERIOD, LovePeach), CottageFeature("🔐", R.string.cottage_feature_vault, R.string.cottage_feature_vault_sub, CottageRoute.VAULT, LoveLavender),
)

@Composable
fun CottageScreen(onOpen: (String) -> Unit) {
    LovePage {
        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item(span = { androidx.compose.foundation.lazy.grid.GridItemSpan(2) }) { Column(Modifier.padding(bottom = 4.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) { Text(stringResource(R.string.cottage_hub_title), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold); Text(stringResource(R.string.cottage_hub_subtitle), color = MaterialTheme.colorScheme.onSurfaceVariant) } }
            items(features, key = { it.route }) { feature ->
                LoveSoftCard(Modifier.fillMaxWidth().clickable { onOpen(feature.route) }) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) { Text(feature.emoji, style = MaterialTheme.typography.headlineMedium); Icon(Icons.AutoMirrored.Filled.ArrowForward, null, tint = feature.accent) }
                        Text(stringResource(feature.titleRes), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(stringResource(feature.subtitleRes), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        androidx.compose.foundation.layout.Box(Modifier.fillMaxWidth().clip(MaterialTheme.shapes.small).background(feature.accent.copy(alpha = 0.13f)).padding(vertical = 3.dp))
                    }
                }
            }
        }
    }
}
