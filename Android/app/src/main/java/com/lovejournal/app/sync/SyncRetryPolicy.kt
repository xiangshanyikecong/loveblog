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

package com.lovejournal.app.sync

import kotlinx.serialization.SerializationException
import retrofit2.HttpException
import java.io.IOException
import kotlin.random.Random

/** 单次重放失败后的处置决定。 */
sealed interface SyncFailure {
    /** 暂时性失败（网络 / 5xx / 限流），按退避节奏稍后重试。 */
    data class Retryable(val reason: String) : SyncFailure

    /** 请求本身不可能再成功（4xx / 载荷与服务端模型漂移），转入死信，不再重放。 */
    data class Permanent(val reason: String) : SyncFailure
}

/**
 * 离线队列的失败分类与指数退避策略。
 *
 * 目标：避免「毒丸」条目被周期任务无限重放——
 * - 永久失败（4xx 等）立即死信，只保留诊断信息；
 * - 暂时失败按 1 分钟起步、2 倍指数增长、上限 6 小时、±20% 抖动的节奏重试；
 * - 连续重试超过 [MAX_ATTEMPTS] 次的暂时失败也转入死信，防止长期占用队列。
 */
object SyncRetryPolicy {

    /** 暂时失败的最大尝试次数（含首次），超过后转入死信。 */
    const val MAX_ATTEMPTS: Int = 8

    private const val BASE_DELAY_MS: Long = 60_000L
    private const val MAX_DELAY_MS: Long = 6 * 60 * 60 * 1000L
    private const val MAX_JITTER_RATIO: Double = 0.2

    fun classify(error: Exception): SyncFailure {
        val root = error.rootCause()
        val reason = describe(root)
        return when (root) {
            is HttpException -> when (root.code()) {
                // 请求超时 / 限流 / 服务端错误都值得稍后重试。
                408, 429 -> SyncFailure.Retryable(reason)
                in 500..599 -> SyncFailure.Retryable(reason)
                in 400..499 -> SyncFailure.Permanent(reason)
                else -> SyncFailure.Retryable(reason)
            }
            // 断网、DNS、超时等 IO 问题重试大概率能自愈。
            is IOException -> SyncFailure.Retryable(reason)
            // 载荷无法被服务端模型解析：重试只会得到同样的 422。
            is SerializationException -> SyncFailure.Permanent(reason)
            // 未知异常按客户端 bug 处理，重试无意义。
            else -> SyncFailure.Permanent(reason)
        }
    }

    /**
     * 第 [attemptsSoFar] 次失败后的下次可重试时间偏移（毫秒）。
     * attemptsSoFar=1 → 约 1 分钟；之后每次翻倍，封顶约 6 小时；附 ±20% 抖动。
     */
    fun backoffMillis(attemptsSoFar: Int): Long {
        val shift = (attemptsSoFar - 1).coerceIn(0, 16)
        val exponential = (BASE_DELAY_MS shl shift).coerceAtMost(MAX_DELAY_MS)
        val jitter = (exponential * MAX_JITTER_RATIO * Random.nextDouble(-1.0, 1.0)).toLong()
        return (exponential + jitter).coerceAtLeast(BASE_DELAY_MS / 2)
    }

    private fun describe(error: Throwable): String {
        val code = (error as? HttpException)?.code()
        val prefix = if (code != null) "HTTP $code" else error.javaClass.simpleName
        val detail = error.message?.takeIf { it.isNotBlank() }?.take(300)
        return if (detail != null) "$prefix: $detail" else prefix
    }

    private fun Throwable.rootCause(): Throwable {
        var current: Throwable = this
        while (current.cause != null && current.cause !== current) {
            current = current.cause!!
        }
        return current
    }
}
