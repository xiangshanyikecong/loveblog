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
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import java.io.IOException
import java.net.SocketTimeoutException

class SyncRetryPolicyTest {

    private fun httpError(code: Int): HttpException =
        HttpException(
            Response.error<Any>(code, "{}".toResponseBody("application/json".toMediaType())),
        )

    @Test
    fun `io failures are retryable`() {
        assertTrue(SyncRetryPolicy.classify(SocketTimeoutException("timeout")) is SyncFailure.Retryable)
        assertTrue(SyncRetryPolicy.classify(IOException("network down")) is SyncFailure.Retryable)
    }

    @Test
    fun `server errors and throttling are retryable`() {
        assertTrue(SyncRetryPolicy.classify(httpError(500)) is SyncFailure.Retryable)
        assertTrue(SyncRetryPolicy.classify(httpError(503)) is SyncFailure.Retryable)
        assertTrue(SyncRetryPolicy.classify(httpError(429)) is SyncFailure.Retryable)
        assertTrue(SyncRetryPolicy.classify(httpError(408)) is SyncFailure.Retryable)
    }

    @Test
    fun `client errors are permanent`() {
        assertTrue(SyncRetryPolicy.classify(httpError(400)) is SyncFailure.Permanent)
        assertTrue(SyncRetryPolicy.classify(httpError(401)) is SyncFailure.Permanent)
        assertTrue(SyncRetryPolicy.classify(httpError(422)) is SyncFailure.Permanent)
    }

    @Test
    fun `payload drift is permanent`() {
        assertTrue(SyncRetryPolicy.classify(SerializationException("missing field")) is SyncFailure.Permanent)
    }

    @Test
    fun `wrapped io failure keeps retryable classification`() {
        val wrapped = IllegalStateException("replay failed", SocketTimeoutException("timeout"))
        assertTrue(SyncRetryPolicy.classify(wrapped) is SyncFailure.Retryable)
    }

    @Test
    fun `backoff starts around one minute with jitter`() {
        repeat(20) {
            val delay = SyncRetryPolicy.backoffMillis(attemptsSoFar = 1)
            assertTrue("expected 30s..72s, got ${delay}ms", delay in 30_000..72_000)
        }
    }

    @Test
    fun `backoff grows with attempts`() {
        val early = SyncRetryPolicy.backoffMillis(attemptsSoFar = 1)
        val later = SyncRetryPolicy.backoffMillis(attemptsSoFar = 5)
        assertTrue("expected growth, early=$early later=$later", later > early)
    }

    @Test
    fun `backoff is capped near six hours`() {
        repeat(20) {
            val delay = SyncRetryPolicy.backoffMillis(attemptsSoFar = 50)
            assertTrue("expected <= 7.2h, got ${delay}ms", delay <= 6 * 60 * 60 * 1000L * 1.2)
        }
    }

    @Test
    fun `max attempts constant is stable`() {
        // 8 次：1min → 2 → 4 → 8 → 16 → 32min → 64min → 封顶 6h，总窗口足以跨过
        // 短暂断网 / 服务重启，又不至于让坏数据无限占用队列。
        assertTrue(SyncRetryPolicy.MAX_ATTEMPTS in 3..12)
    }
}
