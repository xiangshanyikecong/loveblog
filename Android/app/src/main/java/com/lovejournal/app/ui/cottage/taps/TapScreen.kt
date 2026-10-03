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

package com.lovejournal.app.ui.cottage.taps

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.dto.TapResponse
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.asString
import com.lovejournal.app.ui.theme.LoveRose
import com.lovejournal.app.util.formatDateTime
import kotlinx.coroutines.delay

/**
 * 小屋·轻触回应。两个动作（敲一敲 / 心跳）：发送成功触发 触觉反馈 +
 * 爱心跳动动画；下方为最近轻触记录（含双方往来的全部记录）。
 */
@Composable
fun TapScreen(viewModel: TapViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val haptic = LocalHapticFeedback.current

    // 爱心动画：发送成功后从中心弹出放大再淡出；心跳为双脉冲。
    val heartScale = remember { Animatable(0f) }
    LaunchedEffect(state.sentCount) {
        if (state.sentCount > 0) {
            if (state.lastKind == "heartbeat") {
                repeat(2) {
                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                    heartScale.snapTo(0.4f)
                    heartScale.animateTo(1.3f, spring(dampingRatio = Spring.DampingRatioMediumBouncy, stiffness = Spring.StiffnessMedium))
                    heartScale.animateTo(0.2f, tween(160))
                }
            } else {
                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                heartScale.snapTo(0.4f)
                heartScale.animateTo(1.6f, spring(dampingRatio = Spring.DampingRatioMediumBouncy, stiffness = Spring.StiffnessMedium))
            }
            heartScale.animateTo(0f, tween(360))
            delay(120)
        }
    }

    LovePage {
        Box(modifier = Modifier.fillMaxSize()) {
            Column(modifier = Modifier.fillMaxSize()) {
                state.message?.let {
                    Text(
                        text = it.asString(),
                        color = if (state.messageIsError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 4.dp),
                    )
                }

                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(stringResource(R.string.tap_section_title), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(
                            stringResource(R.string.tap_section_subtitle),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            Button(
                                onClick = { viewModel.send("tap") },
                                enabled = !state.sending,
                                modifier = Modifier.weight(1f),
                            ) {
                                Text(if (state.sending) stringResource(R.string.tap_sending) else "👉 " + stringResource(R.string.tap_action_tap))
                            }
                            OutlinedButton(
                                onClick = { viewModel.send("heartbeat") },
                                enabled = !state.sending,
                                modifier = Modifier.weight(1f),
                            ) {
                                Text("💓 " + stringResource(R.string.tap_action_heartbeat))
                            }
                        }
                    }
                }

                Spacer(Modifier.height(12.dp))
                Text(stringResource(R.string.tap_recent_title), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))

                Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
                    when {
                        state.loading && state.items.isEmpty() ->
                            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                        state.error != null && state.items.isEmpty() ->
                            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                Text(
                                    stringResource(R.string.msg_load_failed_with_error, state.error?.asString() ?: ""),
                                    color = MaterialTheme.colorScheme.error,
                                )
                            }
                        state.items.isEmpty() ->
                            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                Text(stringResource(R.string.tap_recent_empty), color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            items(state.items, key = { it.tid }) { tap -> TapRecordCard(tap) }
                            item {
                                Text(
                                    stringResource(R.string.tap_total_kept, state.totalKept),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.outline,
                                    modifier = Modifier.padding(vertical = 6.dp),
                                )
                            }
                        }
                    }
                }
            }

            // 爱心弹出动画覆盖层。
            if (heartScale.value > 0f) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        if (state.lastKind == "heartbeat") "💓" else "💗",
                        style = MaterialTheme.typography.displayLarge,
                        modifier = Modifier
                            .graphicsLayer {
                                scaleX = heartScale.value
                                scaleY = heartScale.value
                            }
                            .alpha(heartScale.value.coerceAtMost(1f)),
                        color = LoveRose,
                    )
                }
            }
        }
    }
}

@Composable
private fun TapRecordCard(tap: TapResponse) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(if (tap.kind == "heartbeat") "💓" else "👉", style = MaterialTheme.typography.titleLarge)
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    stringResource(
                        if (tap.kind == "heartbeat") R.string.tap_log_heartbeat else R.string.tap_log_tap,
                        tap.from_nickname,
                        tap.to_nickname,
                    ),
                    style = MaterialTheme.typography.bodyMedium,
                )
                Text(
                    formatDateTime(tap.created_at),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }
    }
}
