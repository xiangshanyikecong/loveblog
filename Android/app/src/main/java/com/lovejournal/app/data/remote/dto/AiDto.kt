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

package com.lovejournal.app.data.remote.dto

import kotlinx.serialization.Serializable

// ---------------------------------------------------------------------------
// AI 能力 — /v1/ai/*
// 字段名严格镜像后端 app.schemas.ai (snake_case)。
// 服务端未配置 AI 模型时 /ai/status 返回 enabled=false，各功能接口返回 503；
// 客户端 UI 显隐统一由 status 驱动，调用失败统一提示「AI 未配置或暂不可用」。
// features 键：article_polish | monthly_report | question_generate | semantic_search。
// ---------------------------------------------------------------------------

@Serializable
data class AiStatusResponse(
    val enabled: Boolean = false,
    val chat_model: String? = null,
    val embedding_model: String? = null,
    val features: List<String> = emptyList(),
)

@Serializable
data class AiPolishRequest(
    val content: String,
    // polish（润色）| continue（续写）| proofread（校对）。
    val mode: String = "polish",
)

@Serializable
data class AiPolishResponse(
    val text: String = "",
)

@Serializable
data class AiSemanticSearchRequest(
    val query: String,
    val top_k: Int = 5,
)

@Serializable
data class AiSemanticSearchResult(
    val aid: String,
    val title: String = "",
    val snippet: String = "",
    val score: Double = 0.0,
    val updated_at: String? = null,
)

@Serializable
data class AiSemanticSearchResponse(
    val query: String = "",
    val results: List<AiSemanticSearchResult> = emptyList(),
    val indexed_count: Int = 0,
)

@Serializable
data class AiMonthlyReportRequest(
    val year: Int,
    val month: Int,
)

@Serializable
data class AiMonthlyReportResponse(
    val year: Int,
    val month: Int,
    val text: String = "",
)

@Serializable
data class AiQuestionsRequest(
    val count: Int = 3,
)

@Serializable
data class AiQuestionsResponse(
    val questions: List<String> = emptyList(),
)
