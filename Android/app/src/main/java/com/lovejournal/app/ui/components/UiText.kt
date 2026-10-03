/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

package com.lovejournal.app.ui.components

import androidx.annotation.StringRes
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.lovejournal.app.R

/**
 * 可在 ViewModel 层构造、UI 层再解析为本地化字符串的轻量文案载体。
 *
 * ViewModel 无法访问 Compose 的 stringResource，因此提示文案以 [Res]（资源 ID +
 * 格式参数）的形式存入 UI state，由 Composable 调用 [asString] 解析；服务端动态
 * 返回的文本用 [Raw] 透传。这样中 / 英 / 日资源才能真正生效，而不是被
 * ViewModel 里硬编码的中文覆盖。
 */
sealed interface UiText {

    /** 引用 strings.xml 资源，[args] 为 stringResource 的格式参数。 */
    data class Res(@StringRes val id: Int, val args: List<Any> = emptyList()) : UiText

    /** 已解析完成的动态文本（如服务端返回的 detail）。 */
    data class Raw(val value: String) : UiText
}

/** 构造资源文案的便捷函数。 */
fun uiText(@StringRes id: Int, vararg args: Any): UiText = UiText.Res(id, args.toList())

/** 在 Composable 中解析为当前语言的字符串。 */
@Composable
fun UiText.asString(): String = when (this) {
    is UiText.Res -> if (args.isEmpty()) stringResource(id) else stringResource(id, *args.toTypedArray())
    is UiText.Raw -> value
}

/**
 * 在非 Composable 上下文（如 SnackbarHostState.showSnackbar、Worker 通知）中
 * 用当前应用资源解析。注意：ViewModel 持有该结果跨越语言切换时可能过期，
 * 优先在 UI 层用 [asString]。
 */
fun UiText.asString(context: android.content.Context): String = when (this) {
    is UiText.Res -> if (args.isEmpty()) {
        context.getString(id)
    } else {
        context.getString(id, *args.toTypedArray())
    }
    is UiText.Raw -> value
}

/**
 * 携带本地化文案的异常：数据层（如 AuthRepository）需要把失败原因翻译成用户
 * 可读文案时抛出，ViewModel 通过 [Throwable.toUiText] 统一还原。
 */
class UiTextException(
    val text: UiText,
    cause: Throwable? = null,
) : Exception(text.debugDescription(), cause)

/** 把任意 Throwable 转成可展示文案：优先 UiTextException，其次透传 message。 */
fun Throwable.toUiText(): UiText = when (this) {
    is UiTextException -> text
    else -> message?.takeIf { it.isNotBlank() }?.let { UiText.Raw(it) }
        ?: uiText(R.string.msg_operation_failed)
}

private fun UiText.debugDescription(): String = when (this) {
    is UiText.Res -> "UiText.Res(id=$id, args=$args)"
    is UiText.Raw -> value
}
