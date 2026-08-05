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

package com.lovejournal.app.ui.cottage.games

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSoftCard

private data class GameEntry(
    val key: String,
    val emoji: String,
    val name: String,
    val desc: String,
    val available: Boolean,
)

private val games = listOf(
    GameEntry("gomoku", "⚫", "五子棋", "15×15，先连五子者胜", true),
    GameEntry("tictactoe", "❌", "井字棋", "3×3，连成一线即胜", true),
    GameEntry("reversi", "⚪", "黑白棋", "8×8，翻子多者胜", true),
    GameEntry("memory", "🃏", "记忆翻牌", "合作翻出相同图案", true),
    GameEntry("linklink", "🀄", "连连看", "配对相同图案，清空棋盘", true),
    GameEntry("draw", "🎨", "你画我猜", "实时作画与猜词", true),
    GameEntry("canvas", "🖌️", "协作画板", "同一块画布一起涂鸦", true),
)

@Composable
fun GamesLobbyScreen(onOpen: (String) -> Unit) {
    LovePage {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("一起玩", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            Text("选个游戏，和 TA 来一局", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        items(games.size) { i ->
            val g = games[i]
            LoveSoftCard(
                modifier = Modifier
                    .fillMaxWidth()
                    .then(if (g.available) Modifier.clickable { onOpen(g.key) } else Modifier),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    Text(g.emoji, style = MaterialTheme.typography.headlineMedium)
                    Column {
                        Text(
                            g.name,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = if (g.available) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.outline,
                        )
                        Text(g.desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
    }
}
