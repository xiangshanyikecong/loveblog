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
import com.lovejournal.app.data.remote.dto.AlbumDetail
import com.lovejournal.app.data.remote.dto.AlbumCreateRequest
import com.lovejournal.app.data.remote.dto.AlbumPatchRequest
import com.lovejournal.app.data.remote.dto.AlbumSummary
import com.lovejournal.app.data.remote.dto.CommentCreateRequest
import com.lovejournal.app.data.remote.dto.CommentNode
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AlbumsRepository @Inject constructor(
    private val api: LoveApiService,
) {
    suspend fun list(): Result<List<AlbumSummary>> = runCatching {
        api.albums().items
    }

    suspend fun detail(albId: String): Result<AlbumDetail> = runCatching {
        api.album(albId)
    }

    suspend fun create(body: AlbumCreateRequest): Result<AlbumDetail> = runCatching { api.createAlbum(body) }
    suspend fun update(albId: String, body: AlbumCreateRequest): Result<AlbumDetail> = runCatching { api.replaceAlbum(albId, body) }
    suspend fun delete(albId: String): Result<Unit> = runCatching { api.deleteAlbum(albId); Unit }
    suspend fun comment(albId: String, content: String, parentCid: String? = null): Result<CommentNode> =
        runCatching { api.commentAlbum(albId, CommentCreateRequest(content, parentCid)) }
}
