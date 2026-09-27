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

package com.lovejournal.app.ui.cottage.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.lovejournal.app.data.chat.ChatMediaDecryptor
import java.nio.ByteBuffer

/**
 * E2EE 加密图片气泡：未解锁显示锁占位；解锁后经 [ChatMediaDecryptor]
 * 下载并解密密文，再交给 Coil 按 ByteBuffer 加载（格式由内容魔数识别）。
 * 解密结果缓存在 decryptor 内存 LRU 中，重组/滚动不会重复下载解密。
 *
 * [modifier] 由调用方提供统一的尺寸约束与圆角裁剪，三种状态共用同一
 * 布局占位，避免列表滚动时气泡尺寸跳变。
 */
@Composable
fun EncryptedChatImage(
    mid: String,
    iv: String?,
    url: String?,
    unlocked: Boolean,
    decryptor: ChatMediaDecryptor,
    modifier: Modifier = Modifier,
    onOpen: (ByteArray) -> Unit,
) {
    when {
        !unlocked -> MediaPlaceholder(modifier) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(
                    Icons.Outlined.Lock,
                    contentDescription = "加密图片",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "解锁后可见",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        url == null || iv == null -> MediaPlaceholder(modifier) {
            Text(
                "[图片]",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        else -> {
            var bytes by remember(mid, iv) { mutableStateOf<ByteArray?>(null) }
            var failed by remember(mid, iv) { mutableStateOf(false) }
            var attempt by remember(mid, iv) { mutableStateOf(0) }
            LaunchedEffect(mid, iv, url, attempt) {
                failed = false
                runCatching { decryptor.decryptBytes(mid, iv, url) }
                    .onSuccess { bytes = it }
                    .onFailure { failed = true }
            }
            when {
                bytes != null -> AsyncImage(
                    model = ByteBuffer.wrap(bytes),
                    contentDescription = "加密图片",
                    contentScale = ContentScale.Fit,
                    modifier = modifier.clickable { bytes?.let(onOpen) },
                )
                failed -> MediaPlaceholder(modifier, clickable = true, onClick = { attempt++ }) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            Icons.Outlined.Refresh,
                            contentDescription = "重试",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            "解密失败，点击重试",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                else -> MediaPlaceholder(modifier) {
                    CircularProgressIndicator(
                        modifier = Modifier.padding(24.dp),
                        strokeWidth = 2.dp,
                    )
                }
            }
        }
    }
}

/** 加密图片的占位底板（加载中 / 锁定 / 失败），尺寸随调用方 modifier 约束。 */
@Composable
private fun MediaPlaceholder(
    modifier: Modifier,
    clickable: Boolean = false,
    onClick: () -> Unit = {},
    content: @Composable () -> Unit,
) {
    val base = modifier
        .background(MaterialTheme.colorScheme.surfaceVariant)
    Box(
        modifier = if (clickable) base.clickable(onClick = onClick) else base,
        contentAlignment = Alignment.Center,
    ) {
        content()
    }
}
