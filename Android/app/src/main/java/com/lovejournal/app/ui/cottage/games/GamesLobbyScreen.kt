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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.lovejournal.app.R
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSoftCard

private data class GameEntry(
    val key: String,
    val emoji: String,
    val nameRes: Int,
    val descRes: Int,
    val available: Boolean,
)

private val games = listOf(
    GameEntry("gomoku", "⚫", R.string.game_gomoku, R.string.game_gomoku_desc, true),
    GameEntry("tictactoe", "❌", R.string.game_tictactoe, R.string.game_tictactoe_desc, true),
    GameEntry("reversi", "⚪", R.string.game_reversi, R.string.game_reversi_desc, true),
    GameEntry("memory", "🃏", R.string.game_memory, R.string.game_memory_desc, true),
    GameEntry("linklink", "🀄", R.string.game_linklink, R.string.game_linklink_desc, true),
    GameEntry("draw", "🎨", R.string.game_draw, R.string.game_draw_desc, true),
    GameEntry("canvas", "🖌️", R.string.game_canvas, R.string.game_canvas_desc, true),
)

@Composable
fun GamesLobbyScreen(onOpen: (String) -> Unit) {
    LovePage {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text(stringResource(R.string.games_lobby_title), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            Text(stringResource(R.string.games_lobby_subtitle), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                            stringResource(g.nameRes),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = if (g.available) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.outline,
                        )
                        Text(stringResource(g.descRes), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
    }
}
