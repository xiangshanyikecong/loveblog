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

package com.lovejournal.app.data.repository

import com.lovejournal.app.R
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.AiMonthlyReportRequest
import com.lovejournal.app.data.remote.dto.AiMonthlyReportResponse
import com.lovejournal.app.data.remote.dto.AiPolishRequest
import com.lovejournal.app.data.remote.dto.AiPolishResponse
import com.lovejournal.app.data.remote.dto.AiQuestionsRequest
import com.lovejournal.app.data.remote.dto.AiQuestionsResponse
import com.lovejournal.app.data.remote.dto.AiSemanticSearchRequest
import com.lovejournal.app.data.remote.dto.AiSemanticSearchResponse
import com.lovejournal.app.data.remote.dto.AiStatusResponse
import com.lovejournal.app.ui.components.UiTextException
import com.lovejournal.app.ui.components.uiText
import retrofit2.HttpException
import javax.inject.Inject
import javax.inject.Singleton

/** AI 能力特性键，与后端 /v1/ai/status features 一致。 */
object AiFeatures {
    const val ARTICLE_POLISH = "article_polish"
    const val MONTHLY_REPORT = "monthly_report"
    const val QUESTION_GENERATE = "question_generate"
    const val SEMANTIC_SEARCH = "semantic_search"
}

/**
 * 小屋·AI 能力（润色/续写/校对、语义搜索、月报文案、每日一问出题）。
 * UI 显隐由 [status] 的 enabled + features 驱动；功能接口失败（含 503 未配置）
 * 统一映射为「AI 未配置或暂不可用」，其余异常原样抛出由 toUiText 兜底。
 */
@Singleton
class AiRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun status(): Result<AiStatusResponse> =
        runCatching { api.aiStatus() }

    suspend fun polish(content: String, mode: String): Result<AiPolishResponse> = runCatching {
        try {
            api.aiPolish(AiPolishRequest(content = content, mode = mode))
        } catch (e: HttpException) {
            throw aiUnavailable(e)
        }
    }

    suspend fun search(query: String, topK: Int = 5): Result<AiSemanticSearchResponse> = runCatching {
        try {
            api.aiSearch(AiSemanticSearchRequest(query = query, top_k = topK))
        } catch (e: HttpException) {
            throw aiUnavailable(e)
        }
    }

    suspend fun monthlyReport(year: Int, month: Int): Result<AiMonthlyReportResponse> = runCatching {
        try {
            api.aiMonthlyReport(AiMonthlyReportRequest(year = year, month = month))
        } catch (e: HttpException) {
            throw aiUnavailable(e)
        }
    }

    suspend fun generateQuestions(count: Int = 3): Result<AiQuestionsResponse> = runCatching {
        try {
            api.aiGenerateQuestions(AiQuestionsRequest(count = count))
        } catch (e: HttpException) {
            throw aiUnavailable(e)
        }
    }

    private fun aiUnavailable(cause: HttpException) =
        UiTextException(uiText(R.string.ai_error_unavailable), cause)
}
