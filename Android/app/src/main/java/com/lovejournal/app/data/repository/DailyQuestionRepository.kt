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

package com.lovejournal.app.data.repository

import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.data.remote.dto.DailyQuestionAnswerRequest
import com.lovejournal.app.data.remote.dto.DailyQuestionCreateRequest
import com.lovejournal.app.data.remote.dto.DailyQuestionResponse
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 小屋·每日一问。One shared question per day; each partner answers privately and
 * both answers only unlock after both have replied (the backend enforces the
 * blind reveal — see DailyQuestionResponse.revealed).
 */
@Singleton
class DailyQuestionRepository @Inject constructor(
    private val api: LoveApiService,
) {
    /** Today's question, or null when nobody has set one yet. */
    suspend fun today(): Result<DailyQuestionResponse?> = runCatching {
        api.questionToday().item
    }

    suspend fun create(prompt: String): Result<DailyQuestionResponse> = runCatching {
        api.createQuestion(DailyQuestionCreateRequest(prompt = prompt))
    }

    suspend fun answer(qid: String, content: String): Result<DailyQuestionResponse> = runCatching {
        api.answerQuestion(qid, DailyQuestionAnswerRequest(content))
    }

    suspend fun list(limit: Int = 30): Result<List<DailyQuestionResponse>> = runCatching {
        api.questions(limit).items
    }
}
