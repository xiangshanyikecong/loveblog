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
import com.lovejournal.app.data.remote.dto.ArticleDetail
import com.lovejournal.app.data.remote.dto.ArticleCreateRequest
import com.lovejournal.app.data.remote.dto.ArticlePatchRequest
import com.lovejournal.app.data.remote.dto.ArticleSummary
import com.lovejournal.app.data.remote.dto.CommentCreateRequest
import com.lovejournal.app.data.remote.dto.CommentNode
import com.lovejournal.app.data.remote.dto.ContentVersion
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ArticlesRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun list(): Result<List<ArticleSummary>> = runCatching {
        api.articles(onlyPublished = false).items
    }

    suspend fun detail(aid: String): Result<ArticleDetail> = runCatching {
        api.article(aid)
    }

    suspend fun create(body: ArticleCreateRequest): Result<ArticleDetail> = runCatching { api.createArticle(body) }
    suspend fun update(aid: String, body: ArticleCreateRequest): Result<ArticleDetail> = runCatching { api.replaceArticle(aid, body) }
    suspend fun delete(aid: String): Result<Unit> = runCatching { api.deleteArticle(aid); Unit }
    suspend fun comment(aid: String, content: String, parentCid: String? = null): Result<CommentNode> =
        runCatching { api.commentArticle(aid, CommentCreateRequest(content, parentCid)) }
    suspend fun versions(aid: String): Result<List<ContentVersion>> = runCatching { api.articleVersions(aid).items }
    suspend fun rollback(aid: String, version: Int): Result<ArticleDetail> = runCatching { api.rollbackArticle(aid, version) }
}
