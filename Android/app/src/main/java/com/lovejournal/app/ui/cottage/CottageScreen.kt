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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSoftCard
import com.lovejournal.app.ui.theme.LoveLavender
import com.lovejournal.app.ui.theme.LoveMint
import com.lovejournal.app.ui.theme.LovePeach
import com.lovejournal.app.ui.theme.LoveRose

object CottageRoute {
    const val HUB = "cottage"; const val CHAT = "cottage/chat"; const val MOOD = "cottage/mood"; const val WISHLIST = "cottage/wishlist"; const val QUESTIONS = "cottage/questions"; const val GAMES = "cottage/games"; const val WATCH = "cottage/watch"; const val LISTEN = "cottage/listen"; const val COUPONS = "cottage/coupons"; const val REMINDERS = "cottage/reminders"; const val LEDGER = "cottage/ledger"; const val PERIOD = "cottage/period"; const val REPORTS = "cottage/reports"; const val FOOTPRINTS = "cottage/footprints"; const val PLANS = "cottage/plans"; const val CHECKINS = "checkins"; const val VAULT = "cottage/vault"; const val CANVAS = "cottage/games/canvas"; const val CANVAS_GALLERY = "cottage/games/canvas/gallery"; const val CANVAS_ARTWORK = "cottage/games/canvas/gallery/artwork"
}

private data class CottageFeature(val emoji: String, val title: String, val subtitle: String, val route: String, val accent: Color)
private val features = listOf(
    CottageFeature("💬", "悄悄话", "实时陪伴", CottageRoute.CHAT, LoveRose), CottageFeature("🌤️", "心情", "分享此刻", CottageRoute.MOOD, LovePeach),
    CottageFeature("📍", "报备", "让 TA 安心", CottageRoute.CHECKINS, LoveMint), CottageFeature("💝", "心愿单", "一起实现", CottageRoute.WISHLIST, LoveLavender),
    CottageFeature("💌", "每日一问", "更懂彼此", CottageRoute.QUESTIONS, LoveRose), CottageFeature("📺", "一起看", "同步追剧", CottageRoute.WATCH, LoveLavender),
    CottageFeature("🎮", "一起玩", "双人游戏", CottageRoute.GAMES, LoveMint), CottageFeature("🎧", "一起听", "同步听歌", CottageRoute.LISTEN, LovePeach),
    CottageFeature("🎟️", "兑换券", "兑现甜蜜", CottageRoute.COUPONS, LoveRose), CottageFeature("🔔", "提醒", "重要小事", CottageRoute.REMINDERS, LovePeach),
    CottageFeature("🗓️", "约会计划", "期待见面", CottageRoute.PLANS, LoveLavender), CottageFeature("💰", "情侣账本", "共同生活", CottageRoute.LEDGER, LoveMint),
    CottageFeature("📊", "恋爱月报", "回顾甜蜜", CottageRoute.REPORTS, LoveRose), CottageFeature("🗺️", "足迹地图", "点亮城市", CottageRoute.FOOTPRINTS, LoveMint),
    CottageFeature("🌸", "生理期", "贴心关怀", CottageRoute.PERIOD, LovePeach), CottageFeature("🔐", "私密空间", "端到端加密", CottageRoute.VAULT, LoveLavender),
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
            item(span = { androidx.compose.foundation.lazy.grid.GridItemSpan(2) }) { Column(Modifier.padding(bottom = 4.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) { Text("只属于你们俩的小天地", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold); Text("聊天、陪伴、记录和共同生活，都放在这里。", color = MaterialTheme.colorScheme.onSurfaceVariant) } }
            items(features, key = { it.route }) { feature ->
                LoveSoftCard(Modifier.fillMaxWidth().clickable { onOpen(feature.route) }) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) { Text(feature.emoji, style = MaterialTheme.typography.headlineMedium); Icon(Icons.AutoMirrored.Filled.ArrowForward, null, tint = feature.accent) }
                        Text(feature.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(feature.subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        androidx.compose.foundation.layout.Box(Modifier.fillMaxWidth().clip(MaterialTheme.shapes.small).background(feature.accent.copy(alpha = 0.13f)).padding(vertical = 3.dp))
                    }
                }
            }
        }
    }
}
