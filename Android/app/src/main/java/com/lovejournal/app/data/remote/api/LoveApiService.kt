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

package com.lovejournal.app.data.remote.api

import com.lovejournal.app.data.remote.dto.AlbumDetail
import com.lovejournal.app.data.remote.dto.AlbumCreateRequest
import com.lovejournal.app.data.remote.dto.AlbumListResponse
import com.lovejournal.app.data.remote.dto.AlbumPatchRequest
import com.lovejournal.app.data.remote.dto.ArticleDetail
import com.lovejournal.app.data.remote.dto.ArticleCreateRequest
import com.lovejournal.app.data.remote.dto.ArticleListResponse
import com.lovejournal.app.data.remote.dto.ArticlePatchRequest
import com.lovejournal.app.data.remote.dto.CommentCreateRequest
import com.lovejournal.app.data.remote.dto.CommentNode
import com.lovejournal.app.data.remote.dto.ContentVersionListResponse
import com.lovejournal.app.data.remote.dto.VaultEntryCreateRequest
import com.lovejournal.app.data.remote.dto.VaultEntryResponse
import com.lovejournal.app.data.remote.dto.VaultEntryUpdateRequest
import com.lovejournal.app.data.remote.dto.VaultMetaResponse
import com.lovejournal.app.data.remote.dto.VaultRekeyRequest
import com.lovejournal.app.data.remote.dto.VaultSetupRequest
import com.lovejournal.app.data.remote.dto.ChatHistoryResponse
import com.lovejournal.app.data.remote.dto.ChatMessageResponse
import com.lovejournal.app.data.remote.dto.ChatSendRequest
import com.lovejournal.app.data.remote.dto.ChatStateResponse
import com.lovejournal.app.data.remote.dto.ChatSearchResponse
import com.lovejournal.app.data.remote.dto.ChatKeyMetaResponse
import com.lovejournal.app.data.remote.dto.ChatKeySetupRequest
import com.lovejournal.app.data.remote.dto.ChatKeyVerifyRequest
import com.lovejournal.app.data.remote.dto.ChatKeyRekeyRequest
import com.lovejournal.app.data.remote.dto.ChatFavoriteListResponse
import com.lovejournal.app.data.remote.dto.ChatFutureMessagesResponse
import com.lovejournal.app.data.remote.dto.ChatKeywordsResponse
import com.lovejournal.app.data.remote.dto.ChatMediaPanelResponse
import com.lovejournal.app.data.remote.dto.ChatMemoryCardResponse
import com.lovejournal.app.data.remote.dto.ChatPinnedQuoteRequest
import com.lovejournal.app.data.remote.dto.ChatPinnedQuoteResponse
import com.lovejournal.app.data.remote.dto.CouponCreateRequest
import com.lovejournal.app.data.remote.dto.CouponListResponse
import com.lovejournal.app.data.remote.dto.CouponResponse
import com.lovejournal.app.data.remote.dto.CouponUpdateRequest
import com.lovejournal.app.data.remote.dto.DailyQuestionAnswerRequest
import com.lovejournal.app.data.remote.dto.DailyQuestionCreateRequest
import com.lovejournal.app.data.remote.dto.DailyQuestionListResponse
import com.lovejournal.app.data.remote.dto.DailyQuestionResponse
import com.lovejournal.app.data.remote.dto.DailyQuestionTodayResponse
import com.lovejournal.app.data.remote.dto.DashboardResponse
import com.lovejournal.app.data.remote.dto.GameMatchListResponse
import com.lovejournal.app.data.remote.dto.GameStateResponse
import com.lovejournal.app.data.remote.dto.ImportCookieRequest
import com.lovejournal.app.data.remote.dto.ListenHistoryResponse
import com.lovejournal.app.data.remote.dto.LikedTracksResponse
import com.lovejournal.app.data.remote.dto.LikedStatusResponse
import com.lovejournal.app.data.remote.dto.LikedToggleRequest
import com.lovejournal.app.data.remote.dto.LikedToggleResponse
import com.lovejournal.app.data.remote.dto.MyPlaylistCreateRequest
import com.lovejournal.app.data.remote.dto.MyPlaylistUpdateRequest
import com.lovejournal.app.data.remote.dto.MyPlaylistTrackAddRequest
import com.lovejournal.app.data.remote.dto.MyPlaylistDetail
import com.lovejournal.app.data.remote.dto.LocalTracksResponse
import com.lovejournal.app.data.remote.dto.PlaylistTracksResponse
import com.lovejournal.app.data.remote.dto.PlaylistsResponse
import com.lovejournal.app.data.remote.dto.QrKeyResponse
import com.lovejournal.app.data.remote.dto.QrStatusResponse
import com.lovejournal.app.data.remote.dto.ReminderCreateRequest
import com.lovejournal.app.data.remote.dto.ReminderListResponse
import com.lovejournal.app.data.remote.dto.ReminderResponse
import com.lovejournal.app.data.remote.dto.RoomStateResponse
import com.lovejournal.app.data.remote.dto.SongLyricResponse
import com.lovejournal.app.data.remote.dto.SongMeta
import com.lovejournal.app.data.remote.dto.SongSearchResponse
import com.lovejournal.app.data.remote.dto.SongUrlResponse
import com.lovejournal.app.data.remote.dto.ToplistResponse
import com.lovejournal.app.data.remote.dto.EventCreateRequest
import com.lovejournal.app.data.remote.dto.EventListResponse
import com.lovejournal.app.data.remote.dto.EventResponse
import com.lovejournal.app.data.remote.dto.LoginRequest
import com.lovejournal.app.data.remote.dto.MessageCreateRequest
import com.lovejournal.app.data.remote.dto.MessageListResponse
import com.lovejournal.app.data.remote.dto.MessageResponse
import com.lovejournal.app.data.remote.dto.MoodCalendarResponse
import com.lovejournal.app.data.remote.dto.MomentCreateRequest
import com.lovejournal.app.data.remote.dto.MoodCheckinRequest
import com.lovejournal.app.data.remote.dto.MoodResponse
import com.lovejournal.app.data.remote.dto.MoodTodayResponse
import com.lovejournal.app.data.remote.dto.PokeRequest
import com.lovejournal.app.data.remote.dto.TokenResponse
import com.lovejournal.app.data.remote.dto.UploadResponse
import com.lovejournal.app.data.remote.dto.UserProfile
import com.lovejournal.app.data.remote.dto.WatchSourceCreateRequest
import com.lovejournal.app.data.remote.dto.WatchSourceListResponse
import com.lovejournal.app.data.remote.dto.WatchSourcePatchRequest
import com.lovejournal.app.data.remote.dto.WatchSourceResponse
import com.lovejournal.app.data.remote.dto.WatchStateResponse
import com.lovejournal.app.data.remote.dto.WishCreateRequest
import com.lovejournal.app.data.remote.dto.WishListResponse
import com.lovejournal.app.data.remote.dto.WishResponse
import com.lovejournal.app.data.remote.dto.WishUpdateRequest
import com.lovejournal.app.data.remote.dto.CottageMonthlyReportResponse
import com.lovejournal.app.data.remote.dto.FootprintResponse
import com.lovejournal.app.data.remote.dto.FcmTokenDeleteRequest
import com.lovejournal.app.data.remote.dto.FcmTokenResponse
import com.lovejournal.app.data.remote.dto.FcmTokenUpsertRequest
import com.lovejournal.app.data.remote.dto.LedgerCreateRequest
import com.lovejournal.app.data.remote.dto.LedgerListResponse
import com.lovejournal.app.data.remote.dto.LedgerResponse
import com.lovejournal.app.data.remote.dto.LedgerSummaryResponse
import com.lovejournal.app.data.remote.dto.PeriodCreateRequest
import com.lovejournal.app.data.remote.dto.PeriodListResponse
import com.lovejournal.app.data.remote.dto.PeriodResponse
import com.lovejournal.app.data.remote.dto.PeriodSummaryResponse
import com.lovejournal.app.data.remote.dto.PlanCreateRequest
import com.lovejournal.app.data.remote.dto.PlanListResponse
import com.lovejournal.app.data.remote.dto.PlanResponse
import com.lovejournal.app.data.remote.dto.PlanUpdateRequest
import com.lovejournal.app.data.remote.dto.NotificationListResponse
import com.lovejournal.app.data.remote.dto.NotificationReadAllResponse
import com.lovejournal.app.data.remote.dto.NotificationResponse
import com.lovejournal.app.data.remote.dto.SearchResponse
import com.lovejournal.app.data.remote.dto.TotpStatusResponse
import com.lovejournal.app.data.remote.dto.TotpSetupResponse
import com.lovejournal.app.data.remote.dto.TotpEnableRequest
import com.lovejournal.app.data.remote.dto.TotpEnableResponse
import com.lovejournal.app.data.remote.dto.TotpDisableRequest
import com.lovejournal.app.data.remote.dto.LoginDeviceResponse
import com.lovejournal.app.data.remote.dto.DeviceRevokeResponse
import com.lovejournal.app.data.remote.dto.DevicesRevokeAllResponse
import com.lovejournal.app.data.remote.dto.PasswordRecoveryRequest
import com.lovejournal.app.data.remote.dto.OnThisDayResponse
import com.lovejournal.app.data.remote.dto.AnnualReportResponse
import com.lovejournal.app.data.remote.dto.StorageUsageResponse
import com.lovejournal.app.data.remote.dto.RecycleBinResponse
import com.lovejournal.app.data.remote.dto.ChangePasswordRequest
import com.lovejournal.app.data.remote.dto.RevokeSessionsRequest
import com.lovejournal.app.data.remote.dto.CheckInCreateRequest
import com.lovejournal.app.data.remote.dto.CheckInLatestResponse
import com.lovejournal.app.data.remote.dto.CheckInListResponse
import com.lovejournal.app.data.remote.dto.CheckInResponse
import com.lovejournal.app.data.remote.dto.CapsuleCreateRequest
import com.lovejournal.app.data.remote.dto.CapsuleResponse
import com.lovejournal.app.data.remote.dto.CanvasArtworkCreateRequest
import com.lovejournal.app.data.remote.dto.CanvasArtworkListResponse
import com.lovejournal.app.data.remote.dto.CanvasArtworkResponse
import com.lovejournal.app.data.remote.dto.SiteSettingResponse
import com.lovejournal.app.data.remote.dto.SiteSettingUpdateRequest
import com.lovejournal.app.data.remote.dto.MomentResponse
import com.lovejournal.app.data.remote.dto.TimelineListResponse
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.ResponseBody
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.HTTP
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface LoveApiService {

    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): Response<TokenResponse>

    @POST("auth/logout")
    suspend fun logout(): Response<Unit>

    @GET("auth/me")
    suspend fun me(): UserProfile

    @GET("dashboard")
    suspend fun dashboard(): DashboardResponse

    @PUT("push/fcm-tokens")
    suspend fun upsertFcmToken(@Body body: FcmTokenUpsertRequest): FcmTokenResponse

    @HTTP(method = "DELETE", path = "push/fcm-tokens", hasBody = true)
    suspend fun deleteFcmToken(@Body body: FcmTokenDeleteRequest): Response<Unit>

    @GET("events")
    suspend fun events(): EventListResponse

    @POST("events")
    suspend fun createEvent(@Body body: EventCreateRequest): EventResponse

    @PUT("events/{eid}")
    suspend fun updateEvent(@Path("eid") eid: String, @Body body: EventCreateRequest): EventResponse

    @DELETE("events/{eid}")
    suspend fun deleteEvent(@Path("eid") eid: String): Response<Unit>

    @GET("articles")
    suspend fun articles(@Query("only_published") onlyPublished: Boolean = false): ArticleListResponse

    @GET("articles/{aid}")
    suspend fun article(@Path("aid") aid: String): ArticleDetail

    @POST("articles")
    suspend fun createArticle(@Body body: ArticleCreateRequest): ArticleDetail

    @PUT("articles/{aid}")
    suspend fun replaceArticle(@Path("aid") aid: String, @Body body: ArticleCreateRequest): ArticleDetail

    @PATCH("articles/{aid}")
    suspend fun patchArticle(@Path("aid") aid: String, @Body body: ArticlePatchRequest): ArticleDetail

    @DELETE("articles/{aid}")
    suspend fun deleteArticle(@Path("aid") aid: String): Response<Unit>

    @POST("articles/{aid}/comments")
    suspend fun commentArticle(@Path("aid") aid: String, @Body body: CommentCreateRequest): CommentNode

    @GET("articles/{aid}/versions")
    suspend fun articleVersions(@Path("aid") aid: String): ContentVersionListResponse

    @POST("articles/{aid}/versions/{version}/rollback")
    suspend fun rollbackArticle(@Path("aid") aid: String, @Path("version") version: Int): ArticleDetail

    @GET("albums")
    suspend fun albums(): AlbumListResponse

    @GET("albums/{albId}")
    suspend fun album(@Path("albId") albId: String): AlbumDetail

    @POST("albums")
    suspend fun createAlbum(@Body body: AlbumCreateRequest): AlbumDetail

    @PUT("albums/{albId}")
    suspend fun replaceAlbum(@Path("albId") albId: String, @Body body: AlbumCreateRequest): AlbumDetail

    @PATCH("albums/{albId}")
    suspend fun patchAlbum(@Path("albId") albId: String, @Body body: AlbumPatchRequest): AlbumDetail

    @DELETE("albums/{albId}")
    suspend fun deleteAlbum(@Path("albId") albId: String): Response<Unit>

    @POST("albums/{albId}/comments")
    suspend fun commentAlbum(@Path("albId") albId: String, @Body body: CommentCreateRequest): CommentNode

    @GET("messages")
    suspend fun messages(
        @Query("include_private") includePrivate: Boolean = true,
        // Incremental-sync cursor: only rows updated after this ISO timestamp
        // are returned (including tombstones, so local rows can be pruned).
        @Query("updated_after") updatedAfter: String? = null,
        @Query("page_size") pageSize: Int? = null,
    ): MessageListResponse

    @POST("messages")
    suspend fun createMessage(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: MessageCreateRequest,
    ): MessageResponse

    @POST("timeline")
    suspend fun createMoment(
        @Header("Idempotency-Key") idempotencyKey: String? = null,
        @Body body: MomentCreateRequest,
    ): MomentResponse

    @POST("cottage/mood")
    suspend fun upsertMood(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: MoodCheckinRequest,
    ): MoodResponse

    @GET("cottage/mood/today")
    suspend fun moodToday(@Query("on") on: String? = null): MoodTodayResponse

    @GET("cottage/mood/calendar")
    suspend fun moodCalendar(
        @Query("year") year: Int,
        @Query("month") month: Int,
    ): MoodCalendarResponse

    @Multipart
    @POST("uploads/checkin")
    suspend fun uploadCheckinImage(@Part file: MultipartBody.Part): UploadResponse

    @Multipart
    @POST("uploads/avatars")
    suspend fun uploadAvatar(@Part file: MultipartBody.Part): UploadResponse

    @Multipart
    @POST("uploads/albums")
    suspend fun uploadAlbumImage(@Part file: MultipartBody.Part): UploadResponse

    @Multipart
    @POST("uploads/articles")
    suspend fun uploadArticleImage(@Part file: MultipartBody.Part): UploadResponse

    // ---- 小屋·心愿单 (cottage wishlist) ----

    @GET("cottage/wishes")
    suspend fun wishes(@Query("status") status: String? = null): WishListResponse

    @POST("cottage/wishes")
    suspend fun createWish(
        @Header("Idempotency-Key") idempotencyKey: String? = null,
        @Body body: WishCreateRequest,
    ): WishResponse

    @PATCH("cottage/wishes/{wid}")
    suspend fun updateWish(@Path("wid") wid: String, @Body body: WishUpdateRequest): WishResponse

    @POST("cottage/wishes/{wid}/complete")
    suspend fun completeWish(@Path("wid") wid: String): WishResponse

    @POST("cottage/wishes/{wid}/reopen")
    suspend fun reopenWish(@Path("wid") wid: String): WishResponse

    @DELETE("cottage/wishes/{wid}")
    suspend fun deleteWish(@Path("wid") wid: String): Response<Unit>

    // ---- 小屋·每日一问 (cottage daily questions) ----

    @GET("cottage/questions/today")
    suspend fun questionToday(@Query("on") on: String? = null): DailyQuestionTodayResponse

    @GET("cottage/questions")
    suspend fun questions(@Query("limit") limit: Int = 30): DailyQuestionListResponse

    @POST("cottage/questions")
    suspend fun createQuestion(@Body body: DailyQuestionCreateRequest): DailyQuestionResponse

    @POST("cottage/questions/{qid}/answer")
    suspend fun answerQuestion(
        @Path("qid") qid: String,
        @Body body: DailyQuestionAnswerRequest,
    ): DailyQuestionResponse

    // ---- 小屋·聊天 (cottage chat) ----

    @GET("cottage/chat/messages")
    suspend fun chatMessages(
        @Query("before_id") beforeId: Int? = null,
        @Query("limit") limit: Int = 30,
    ): ChatHistoryResponse

    // 关键词搜索（仅明文消息；E2EE 消息需客户端本地搜索）。
    @GET("cottage/chat/search")
    suspend fun searchChatMessages(
        @Query("q") q: String,
        @Query("limit") limit: Int = 20,
    ): ChatSearchResponse

    @POST("cottage/chat/messages")
    suspend fun sendChatMessage(
        @Header("Idempotency-Key") idempotencyKey: String? = null,
        @Body body: ChatSendRequest,
    ): ChatMessageResponse

    @GET("cottage/chat/favorites")
    suspend fun chatFavorites(): ChatFavoriteListResponse

    @GET("cottage/chat/future")
    suspend fun chatFuture(): ChatFutureMessagesResponse

    @POST("cottage/chat/messages/{mid}/recall")
    suspend fun recallChatMessage(@Path("mid") mid: String): ChatMessageResponse

    @POST("cottage/chat/messages/{mid}/favorite")
    suspend fun favoriteChatMessage(@Path("mid") mid: String): ChatMessageResponse

    @DELETE("cottage/chat/messages/{mid}/favorite")
    suspend fun unfavoriteChatMessage(@Path("mid") mid: String): ChatMessageResponse

    @GET("cottage/chat/media-panel")
    suspend fun chatMediaPanel(@Query("limit") limit: Int = 18): ChatMediaPanelResponse

    @GET("cottage/chat/pinned-quote")
    suspend fun chatPinnedQuote(): ChatPinnedQuoteResponse

    @PUT("cottage/chat/pinned-quote")
    suspend fun pinChatQuote(@Body body: ChatPinnedQuoteRequest): ChatPinnedQuoteResponse

    @DELETE("cottage/chat/pinned-quote")
    suspend fun clearChatPinnedQuote(): ChatPinnedQuoteResponse

    @GET("cottage/chat/keywords")
    suspend fun chatKeywords(@Query("on") on: String? = null): ChatKeywordsResponse

    @GET("cottage/chat/memory-card")
    suspend fun chatMemoryCard(@Query("on") on: String? = null): ChatMemoryCardResponse

    @POST("cottage/chat/read")
    suspend fun markChatRead(): Response<Unit>

    @GET("cottage/chat/state")
    suspend fun chatState(): ChatStateResponse

    // ---- 小屋·聊天 端到端加密密钥托管 ----

    @GET("cottage/chat/keys/meta")
    suspend fun chatKeyMeta(): ChatKeyMetaResponse

    @POST("cottage/chat/keys/setup")
    suspend fun setupChatKey(@Body body: ChatKeySetupRequest): ChatKeyMetaResponse

    // 服务端返回 204 No Content：必须用 Response<Unit>，声明实体类会在空响应体上崩溃。
    @POST("cottage/chat/keys/verify")
    suspend fun verifyChatKey(@Body body: ChatKeyVerifyRequest): Response<Unit>

    @POST("cottage/chat/keys/rekey")
    suspend fun rekeyChatKey(@Body body: ChatKeyRekeyRequest): ChatKeyMetaResponse

    @POST("cottage/poke")
    suspend fun poke(@Body body: PokeRequest): Response<Unit>

    @GET("cottage/draw/state") suspend fun drawState(): JsonObject
    @GET("cottage/draw/matches") suspend fun drawMatches(): GameMatchListResponse
    @POST("cottage/draw/invite") suspend fun inviteDraw(): Response<Unit>

    // ---- 小屋·协作画板 作品集 (cottage canvas artwork gallery) ----

    @GET("cottage/canvas/artworks")
    suspend fun canvasArtworks(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): CanvasArtworkListResponse

    @POST("cottage/canvas/artworks")
    suspend fun createCanvasArtwork(
        @Header("Idempotency-Key") idempotencyKey: String? = null,
        @Body body: CanvasArtworkCreateRequest,
    ): CanvasArtworkResponse

    @GET("cottage/canvas/artworks/{caid}")
    suspend fun canvasArtwork(@Path("caid") caid: String): CanvasArtworkResponse

    @DELETE("cottage/canvas/artworks/{caid}")
    suspend fun deleteCanvasArtwork(@Path("caid") caid: String): Response<Unit>

    @GET("cottage/coupons/{cpid}")
    suspend fun coupon(@Path("cpid") cpid: String): CouponResponse

    @PATCH("cottage/ledger/{leid}")
    suspend fun patchLedger(@Path("leid") leid: String, @Body body: JsonObject): LedgerResponse

    @PATCH("cottage/period/{pcid}")
    suspend fun patchPeriod(@Path("pcid") pcid: String, @Body body: JsonObject): PeriodResponse

    @GET("cottage/plans/{pid}")
    suspend fun plan(@Path("pid") pid: String): PlanResponse

    @GET("cottage/questions/{qid}")
    suspend fun question(@Path("qid") qid: String): DailyQuestionResponse

    @GET("cottage/reminders/{rid}")
    suspend fun reminder(@Path("rid") rid: String): ReminderResponse

    @PATCH("cottage/reminders/{rid}")
    suspend fun patchReminder(@Path("rid") rid: String, @Body body: JsonObject): ReminderResponse

    @GET("cottage/wishes/{wid}")
    suspend fun wish(@Path("wid") wid: String): WishResponse

    // ---- 小屋·一起玩 (cottage games) ----

    @GET("cottage/games/{game}/state")
    suspend fun gameState(@Path("game") game: String): GameStateResponse

    @GET("cottage/games/{game}/matches")
    suspend fun gameMatches(
        @Path("game") game: String,
        @Query("limit") limit: Int = 20,
    ): GameMatchListResponse

    @POST("cottage/games/{game}/invite")
    suspend fun inviteGame(@Path("game") game: String): Response<Unit>

    // ---- 小屋·一起看 (cottage watch) ----

    @GET("cottage/watch/state")
    suspend fun watchState(): WatchStateResponse

    @GET("cottage/watch/sources")
    suspend fun watchSources(): WatchSourceListResponse

    @POST("cottage/watch/sources")
    suspend fun addWatchSource(@Body body: WatchSourceCreateRequest): WatchSourceResponse

    @Multipart
    @POST("cottage/watch/sources/upload")
    suspend fun uploadWatchSource(@Part file: MultipartBody.Part): WatchSourceResponse

    @PATCH("cottage/watch/sources/{wsid}")
    suspend fun patchWatchSource(
        @Path("wsid") wsid: String,
        @Body body: WatchSourcePatchRequest,
    ): WatchSourceResponse

    @DELETE("cottage/watch/sources/{wsid}")
    suspend fun deleteWatchSource(@Path("wsid") wsid: String): Response<Unit>

    @POST("cottage/watch/invite")
    suspend fun inviteWatch(): Response<Unit>

    // ---- 小屋·一起听 (cottage listen) ----

    @GET("cottage/listen/state")
    suspend fun listenState(): RoomStateResponse

    @GET("cottage/listen/local-tracks")
    suspend fun listenLocalTracks(): LocalTracksResponse

    @Multipart
    @POST("cottage/listen/local-tracks")
    suspend fun uploadListenLocalTrack(
        @Part file: MultipartBody.Part,
        @Part("name") name: RequestBody? = null,
        @Part("artist") artist: RequestBody? = null,
        @Part("album") album: RequestBody? = null,
        @Part("duration_ms") durationMs: RequestBody? = null,
        @Part("cover_url") coverUrl: RequestBody? = null,
    ): SongMeta

    @DELETE("cottage/listen/local-tracks/{tid}")
    suspend fun deleteListenLocalTrack(@Path("tid") tid: String): Response<Unit>

    @GET("cottage/listen/songs/{songId}/url")
    suspend fun listenSongUrl(@Path("songId") songId: String): SongUrlResponse

    @GET("cottage/listen/songs/{songId}/lyric")
    suspend fun listenSongLyric(@Path("songId") songId: String): SongLyricResponse

    @GET("cottage/listen/search")
    suspend fun listenSearch(
        @Query("keyword") keyword: String,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): SongSearchResponse

    @GET("cottage/listen/playlists")
    suspend fun listenPlaylists(): PlaylistsResponse

    @GET("cottage/listen/playlists/{playlistId}/tracks")
    suspend fun listenPlaylistTracks(
        @Path("playlistId") playlistId: String,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): PlaylistTracksResponse

    @GET("cottage/listen/discover/recommend-songs")
    suspend fun listenDiscoverRecommendSongs(): SongSearchResponse

    @GET("cottage/listen/discover/playlists")
    suspend fun listenDiscoverPlaylists(@Query("limit") limit: Int = 12): PlaylistsResponse

    @GET("cottage/listen/discover/playlists/{playlistId}/tracks")
    suspend fun listenDiscoverPlaylistTracks(
        @Path("playlistId") playlistId: String,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): PlaylistTracksResponse

    @GET("cottage/listen/discover/toplist")
    suspend fun listenDiscoverToplist(): ToplistResponse

    @GET("cottage/listen/discover/toplist/{toplistId}/tracks")
    suspend fun listenDiscoverToplistTracks(
        @Path("toplistId") toplistId: String,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): PlaylistTracksResponse

    @GET("cottage/listen/history")
    suspend fun listenHistory(@Query("limit") limit: Int = 50): ListenHistoryResponse

    // ---- 小屋·一起听 我的音乐库（收藏 + 自建歌单）----

    @GET("cottage/listen/liked")
    suspend fun listenLikedTracks(
        @Query("limit") limit: Int = 100,
        @Query("offset") offset: Int = 0,
    ): LikedTracksResponse

    @GET("cottage/listen/liked/status")
    suspend fun listenLikedStatus(@Query("song_ids") songIds: String): LikedStatusResponse

    @PUT("cottage/listen/liked/toggle")
    suspend fun listenToggleLiked(@Body body: LikedToggleRequest): LikedToggleResponse

    @DELETE("cottage/listen/liked/{songId}")
    suspend fun listenRemoveLiked(@Path("songId") songId: String): Response<Unit>

    @GET("cottage/listen/playlists/mine")
    suspend fun listenMyPlaylists(): List<MyPlaylistDetail>

    @POST("cottage/listen/playlists/mine")
    suspend fun listenCreateMyPlaylist(@Body body: MyPlaylistCreateRequest): Response<Unit>

    @GET("cottage/listen/playlists/mine/{pid}")
    suspend fun listenMyPlaylist(@Path("pid") pid: String): MyPlaylistDetail

    @PUT("cottage/listen/playlists/mine/{pid}")
    suspend fun listenUpdateMyPlaylist(@Path("pid") pid: String, @Body body: MyPlaylistUpdateRequest): Response<Unit>

    @DELETE("cottage/listen/playlists/mine/{pid}")
    suspend fun listenDeleteMyPlaylist(@Path("pid") pid: String): Response<Unit>

    @POST("cottage/listen/playlists/mine/{pid}/tracks")
    suspend fun listenAddTrackToMyPlaylist(
        @Path("pid") pid: String,
        @Body body: MyPlaylistTrackAddRequest,
    ): Response<Unit>

    @DELETE("cottage/listen/playlists/mine/{pid}/tracks/{songId}")
    suspend fun listenRemoveTrackFromMyPlaylist(@Path("pid") pid: String, @Path("songId") songId: String): Response<Unit>

    @POST("cottage/listen/playlists/mine/{pid}/play")
    suspend fun listenPlayMyPlaylist(@Path("pid") pid: String): Response<Unit>

    @GET("cottage/listen/auth/qr-key")
    suspend fun listenQrKey(): QrKeyResponse

    @GET("cottage/listen/auth/qr-status")
    suspend fun listenQrStatus(@Query("key") key: String): QrStatusResponse

    @POST("cottage/listen/auth/import-cookie")
    suspend fun listenImportCookie(@Body body: ImportCookieRequest): QrStatusResponse

    @POST("cottage/listen/auth/logout")
    suspend fun listenLogout(): Response<Unit>

    // ---- 小屋·甜蜜兑换券 (cottage coupons) ----

    @GET("cottage/coupons")
    suspend fun coupons(
        @Query("box") box: String = "all",
        @Query("status") status: String? = null,
    ): CouponListResponse

    @POST("cottage/coupons")
    suspend fun createCoupon(@Body body: CouponCreateRequest): CouponResponse

    @PATCH("cottage/coupons/{cpid}")
    suspend fun updateCoupon(@Path("cpid") cpid: String, @Body body: CouponUpdateRequest): CouponResponse

    @POST("cottage/coupons/{cpid}/redeem")
    suspend fun redeemCoupon(@Path("cpid") cpid: String): CouponResponse

    @DELETE("cottage/coupons/{cpid}")
    suspend fun deleteCoupon(@Path("cpid") cpid: String): Response<Unit>

    // ---- 小屋·提醒 (cottage reminders) ----

    @GET("cottage/reminders")
    suspend fun reminders(
        @Query("include_done") includeDone: Boolean = false,
        @Query("limit") limit: Int = 100,
    ): ReminderListResponse

    @POST("cottage/reminders")
    suspend fun createReminder(@Body body: ReminderCreateRequest): ReminderResponse

    @POST("cottage/reminders/{rid}/done")
    suspend fun markReminderDone(@Path("rid") rid: String): ReminderResponse

    @POST("cottage/reminders/{rid}/reopen")
    suspend fun reopenReminder(@Path("rid") rid: String): ReminderResponse

    @DELETE("cottage/reminders/{rid}")
    suspend fun deleteReminder(@Path("rid") rid: String): Response<Unit>

    // ---- 小屋·情侣账本 (cottage ledger) ----

    @GET("cottage/ledger")
    suspend fun ledger(
        @Query("category") category: String? = null,
        @Query("month") month: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 30,
    ): LedgerListResponse

    @POST("cottage/ledger")
    suspend fun createLedger(@Body body: LedgerCreateRequest): LedgerResponse

    @GET("cottage/ledger/summary")
    suspend fun ledgerSummary(@Query("month") month: String? = null): LedgerSummaryResponse

    @DELETE("cottage/ledger/{leid}")
    suspend fun deleteLedger(@Path("leid") leid: String): Response<Unit>

    // ---- 小屋·生理期 (cottage period) ----

    @GET("cottage/period")
    suspend fun periodCycles(@Query("limit") limit: Int = 60): PeriodListResponse

    @POST("cottage/period")
    suspend fun createPeriod(@Body body: PeriodCreateRequest): PeriodResponse

    @GET("cottage/period/summary")
    suspend fun periodSummary(): PeriodSummaryResponse

    @DELETE("cottage/period/{pcid}")
    suspend fun deletePeriod(@Path("pcid") pcid: String): Response<Unit>

    // ---- 小屋·恋爱月报 (cottage reports) ----

    @GET("cottage/reports/monthly")
    suspend fun monthlyReport(
        @Query("year") year: Int,
        @Query("month") month: Int,
    ): CottageMonthlyReportResponse

    // ---- 小屋·约会计划 (cottage plans) ----

    @GET("cottage/plans")
    suspend fun plans(@Query("status") status: String? = null): PlanListResponse

    @POST("cottage/plans")
    suspend fun createPlan(@Body body: PlanCreateRequest): PlanResponse

    @PATCH("cottage/plans/{pid}")
    suspend fun updatePlan(@Path("pid") pid: String, @Body body: PlanUpdateRequest): PlanResponse

    @POST("cottage/plans/{pid}/complete")
    suspend fun completePlan(@Path("pid") pid: String): PlanResponse

    @POST("cottage/plans/{pid}/reopen")
    suspend fun reopenPlan(@Path("pid") pid: String): PlanResponse

    @DELETE("cottage/plans/{pid}")
    suspend fun deletePlan(@Path("pid") pid: String): Response<Unit>

    // ---- 小屋·足迹地图 (cottage footprints) ----

    @GET("cottage/footprints")
    suspend fun footprints(): FootprintResponse

    // ---- 主端·通知中心 (notifications) ----

    @GET("notifications")
    suspend fun notifications(
        @Query("unread_only") unreadOnly: Boolean = false,
        @Query("limit") limit: Int = 50,
    ): NotificationListResponse

    @POST("notifications/{nid}/read")
    suspend fun markNotificationRead(@Path("nid") nid: String): NotificationResponse

    @POST("notifications/read-all")
    suspend fun markAllNotificationsRead(): NotificationReadAllResponse

    // ---- 主端·全局搜索 (search) ----

    @GET("search")
    suspend fun search(
        @Query("q") q: String,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): SearchResponse

    // ---- 主端·时间胶囊 (capsules) ----

    @GET("capsules")
    suspend fun capsules(): List<CapsuleResponse>

    @POST("capsules")
    suspend fun createCapsule(@Body body: CapsuleCreateRequest): CapsuleResponse

    @DELETE("capsules/{uuid}")
    suspend fun deleteCapsule(@Path("uuid") uuid: String): Response<Unit>

    // ---- 主端·设置 (settings) ----

    @GET("settings")
    suspend fun settings(): SiteSettingResponse

    @PUT("settings")
    suspend fun updateSettings(@Body body: SiteSettingUpdateRequest): SiteSettingResponse

    // ---- 主端·时间线 (timeline) ----

    @GET("timeline")
    suspend fun timeline(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
        @Query("sort") sort: String = "desc",
    ): TimelineListResponse

    @DELETE("timeline/{mid}")
    suspend fun deleteMoment(@Path("mid") mid: String): Response<Unit>

    @PATCH("events/{eid}")
    suspend fun patchEvent(@Path("eid") eid: String, @Body body: JsonObject): EventResponse

    @PATCH("messages/{msgId}")
    suspend fun patchMessage(@Path("msgId") msgId: String, @Body body: JsonObject): MessageResponse

    @DELETE("messages/{msgId}")
    suspend fun deleteMessage(@Path("msgId") msgId: String): Response<Unit>

    @GET("messages/{msgId}/versions")
    suspend fun messageVersions(@Path("msgId") msgId: String): ContentVersionListResponse

    @POST("messages/{msgId}/versions/{version}/rollback")
    suspend fun rollbackMessage(@Path("msgId") msgId: String, @Path("version") version: Int): MessageResponse

    @POST("timeline/{mid}/comments")
    suspend fun commentMoment(@Path("mid") mid: String, @Body body: CommentCreateRequest): CommentNode

    @GET("timeline/memories")
    suspend fun timelineMemories(): List<MomentResponse>

    // ---- 小屋·私密空间 ----

    @GET("cottage/vault/meta")
    suspend fun vaultMeta(): VaultMetaResponse

    @POST("cottage/vault/setup")
    suspend fun setupVault(@Body body: VaultSetupRequest): VaultMetaResponse

    @GET("cottage/vault/entries")
    suspend fun vaultEntries(): List<VaultEntryResponse>

    @POST("cottage/vault/entries")
    suspend fun createVaultEntry(@Body body: VaultEntryCreateRequest): VaultEntryResponse

    @PUT("cottage/vault/entries/{vid}")
    suspend fun updateVaultEntry(@Path("vid") vid: String, @Body body: VaultEntryUpdateRequest): VaultEntryResponse

    @DELETE("cottage/vault/entries/{vid}")
    suspend fun deleteVaultEntry(@Path("vid") vid: String): Response<Unit>

    @POST("cottage/vault/rekey")
    suspend fun rekeyVault(@Body body: VaultRekeyRequest): VaultMetaResponse

    @POST("cottage/vault/reset")
    suspend fun resetVault(): Response<Unit>

    // ---- 主端·报备签到 (check-ins) ----

    @GET("checkins/latest")
    suspend fun checkinLatest(): CheckInLatestResponse

    @GET("checkins")
    suspend fun checkins(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): CheckInListResponse

    @POST("checkins")
    suspend fun createCheckin(
        @Header("Idempotency-Key") idempotencyKey: String? = null,
        @Body body: CheckInCreateRequest,
    ): CheckInResponse

    // ---- 主端·回收站 (recycle bin) ----

    @GET("recycle-bin")
    suspend fun recycleBin(@Query("type") type: String? = null): RecycleBinResponse

    @POST("recycle-bin/{type}/{id}/restore")
    suspend fun restoreRecycleItem(@Path("type") type: String, @Path("id") id: String): Response<Unit>

    @DELETE("recycle-bin/{type}/{id}")
    suspend fun deleteRecycleItem(@Path("type") type: String, @Path("id") id: String): Response<Unit>

    @DELETE("recycle-bin")
    suspend fun clearRecycleBin(@Query("type") type: String? = null): Response<Unit>

    // ---- 主端·账号安全 (security) ----

    @POST("security/users/{uid}/change-password")
    suspend fun changePassword(@Path("uid") uid: String, @Body body: ChangePasswordRequest): Response<Unit>

    @POST("security/users/{uid}/revoke-own-sessions")
    suspend fun revokeOwnSessions(@Path("uid") uid: String, @Body body: RevokeSessionsRequest): Response<Unit>

    // ---- 管理、维护与完整服务器能力 ----

    @GET("health") suspend fun health(): JsonElement
    @GET("health/system") suspend fun systemHealth(): JsonElement
    @GET("audit-logs") suspend fun auditLogs(@Query("page") page: Int = 1, @Query("page_size") pageSize: Int = 50): JsonElement
    @GET("auth/bootstrap-status") suspend fun bootstrapStatus(): JsonElement
    @POST("auth/bootstrap")
    suspend fun bootstrap(
        @Header("X-Bootstrap-Token") bootstrapToken: String?,
        @Body body: JsonObject,
    ): JsonElement
    @POST("auth/register") suspend fun register(@Body body: JsonObject): JsonElement
    @GET("auth/partners") suspend fun partners(): JsonElement
    @PUT("auth/partners/{uid}") suspend fun updatePartner(@Path("uid") uid: String, @Body body: JsonObject): JsonElement
    @GET("auth/visitors") suspend fun visitors(): JsonElement
    @GET("auth/visitors/{uid}") suspend fun visitor(@Path("uid") uid: String): JsonElement
    @PUT("auth/visitors/{uid}") suspend fun updateVisitor(@Path("uid") uid: String, @Body body: JsonObject): JsonElement
    @POST("auth/visitors/{uid}/toggle-ban") suspend fun toggleVisitorBan(@Path("uid") uid: String): JsonElement

    // ---- 账号安全扩展（TOTP / 登录设备 / 密码找回，对齐网页端）----

    @GET("auth/totp/status") suspend fun totpStatus(): TotpStatusResponse
    @POST("auth/totp/setup") suspend fun totpSetup(): TotpSetupResponse
    @POST("auth/totp/enable") suspend fun totpEnable(@Body body: TotpEnableRequest): TotpEnableResponse
    @POST("auth/totp/disable") suspend fun totpDisable(@Body body: TotpDisableRequest): TotpStatusResponse

    @GET("auth/devices") suspend fun loginDevices(): List<LoginDeviceResponse>
    @DELETE("auth/devices/{did}") suspend fun revokeLoginDevice(@Path("did") did: String): DeviceRevokeResponse
    @DELETE("auth/devices") suspend fun revokeAllLoginDevices(): DevicesRevokeAllResponse

    @POST("auth/password-recovery") suspend fun passwordRecovery(
        @Header("X-Bootstrap-Token") bootstrapToken: String,
        @Body body: PasswordRecoveryRequest,
    ): Response<Unit>

    // ---- 回忆 / 年报 / 存储用量 ----

    @GET("memories/on-this-day") suspend fun onThisDay(@Query("date") date: String? = null): OnThisDayResponse
    @GET("reports/annual") suspend fun annualReport(@Query("year") year: Int): AnnualReportResponse
    @GET("storage/usage") suspend fun storageUsage(): StorageUsageResponse

    // 隐私中心（对齐网页端 PrivacyCenterView）：服务端保存了哪些数据、
    // 加密状态、导出策略与最近的隐私相关审计事件。
    @GET("privacy/summary") suspend fun privacySummary(): JsonObject
    @POST("privacy/recovery-events") suspend fun recordPrivacyRecoveryEvent(@Body body: JsonObject): JsonObject
    @GET("health/system/history") suspend fun healthHistory(
        @Query("hours") hours: Int = 24,
        @Query("limit") limit: Int = 50,
    ): JsonElement
    @POST("health/system/remediate") suspend fun healthRemediate(): JsonElement

    @GET("security/users") suspend fun securityUsers(): JsonElement
    @POST("security/users/{uid}/reset-password") suspend fun adminResetPassword(@Path("uid") uid: String, @Body body: JsonObject): Response<Unit>
    @POST("security/users/{uid}/revoke-sessions") suspend fun adminRevokeSessions(@Path("uid") uid: String): Response<Unit>
    @POST("security/users/{uid}/unlock") suspend fun adminUnlock(@Path("uid") uid: String): Response<Unit>

    @GET("push/fcm-tokens") suspend fun fcmTokens(): JsonElement
    @GET("push/public-key") suspend fun pushPublicKey(): JsonElement
    @GET("push/subscriptions") suspend fun pushSubscriptions(): JsonElement
    @PUT("push/subscriptions") suspend fun updatePushSubscription(@Body body: JsonObject): JsonElement
    @DELETE("push/subscriptions") suspend fun deletePushSubscription(@Body body: JsonObject): Response<Unit>

    @GET("export/preflight") suspend fun exportPreflight(): JsonElement
    @GET("export/schedule") suspend fun exportSchedule(): JsonElement
    @PUT("export/schedule") suspend fun updateExportSchedule(@Body body: JsonObject): JsonElement
    @POST("export/auto/run") suspend fun runAutoExport(): JsonElement
    @GET("export/history") suspend fun exportHistory(): JsonElement
    @GET("export/all") suspend fun exportAll(): ResponseBody
    // 备份恢复是 multipart 上传（服务端 UploadFile = File(...)），用 JSON 裸体会 422。
    @Multipart @POST("export/restore/preflight") suspend fun restorePreflight(@Part file: MultipartBody.Part): JsonElement
    @Multipart @POST("export/restore") suspend fun restoreExport(@Part file: MultipartBody.Part): JsonElement

    @POST("uploads/avatars/from-qq") suspend fun uploadAvatarFromQq(@Body body: JsonObject): UploadResponse
    @Multipart @POST("uploads/timeline") suspend fun uploadTimeline(@Part file: MultipartBody.Part): UploadResponse
    @Multipart @POST("uploads/chat-audio") suspend fun uploadChatAudio(@Part file: MultipartBody.Part): UploadResponse
    @Multipart @POST("uploads/videos") suspend fun uploadVideo(@Part file: MultipartBody.Part): UploadResponse
    @Multipart @POST("uploads/capsule") suspend fun uploadCapsule(@Part file: MultipartBody.Part): UploadResponse
    @GET("uploads/storage-stats") suspend fun storageStats(): JsonElement
    // 服务端只接受 dry_run 查询参数（无请求体），发 JSON 体会被忽略导致永远 dry-run。
    @POST("uploads/cleanup") suspend fun cleanupUploads(@Query("dry_run") dryRun: Boolean = true): JsonElement
}
