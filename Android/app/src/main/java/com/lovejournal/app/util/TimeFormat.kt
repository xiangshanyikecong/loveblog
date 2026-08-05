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

package com.lovejournal.app.util

import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * 后端 ISO-8601 时间字符串 -> 本地可读文本的统一格式化工具，供各小屋模块复用，
 * 避免在每个 Screen 重复造时间解析逻辑。
 *
 * 后端时间字段（DateTime(timezone=True)）通常带时区偏移，但为健壮起见，对
 * 「Z 结尾」「±offset」「无时区(按 UTC 处理)」三种写法都做兜底；全部解析失败时
 * 原样返回，绝不抛异常影响 UI 渲染。
 */
private fun parseInstant(iso: String): Instant? = runCatching { Instant.parse(iso) }
    .recoverCatching { OffsetDateTime.parse(iso).toInstant() }
    .recoverCatching { LocalDateTime.parse(iso).toInstant(ZoneOffset.UTC) }
    .getOrNull()

private val DATE_TIME_FMT = DateTimeFormatter.ofPattern("MM-dd HH:mm")
private val DATE_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd")

/** ISO datetime -> "MM-dd HH:mm"（本地时区）。空或非法返回空串。 */
fun formatDateTime(iso: String?): String {
    if (iso.isNullOrBlank()) return ""
    val instant = parseInstant(iso) ?: return iso
    return DATE_TIME_FMT.withZone(ZoneId.systemDefault()).format(instant)
}

/** ISO datetime/date -> "yyyy-MM-dd"（本地时区）。空或非法返回空串。 */
fun formatDate(iso: String?): String {
    if (iso.isNullOrBlank()) return ""
    val instant = parseInstant(iso) ?: return iso
    return DATE_FMT.withZone(ZoneId.systemDefault()).format(instant)
}
