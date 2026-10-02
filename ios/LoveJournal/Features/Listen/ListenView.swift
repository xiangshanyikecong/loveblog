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

import AVFoundation
import Observation
import SwiftUI

import LoveCore

// MARK: - Contracts local to this screen
//
// The history row is a FLAT `SongMeta + played_at_ms` (server
// `ListenHistoryItem`), not the nested shape of
// `MediaSyncDTOs.HistoryEntry`; the toplist entry has no LoveCore twin yet.
// Both live here until they graduate into LoveCore.

struct ToplistItem: Decodable, Identifiable {
    var toplistId: String
    var name: String
    var coverUrl: String?
    var updateFrequency: String?
    var trackCount: Int

    var id: String { toplistId }

    enum CodingKeys: String, CodingKey {
        case name
        case toplistId = "toplist_id"
        case coverUrl = "cover_url"
        case updateFrequency = "update_frequency"
        case trackCount = "track_count"
    }
}

private struct ToplistList: Decodable {
    var items: [ToplistItem]
}

struct ListenHistoryRow: Decodable, Identifiable {
    var songId: String
    var name: String
    var artists: [String]?
    var album: String?
    var durationMs: Int?
    var coverUrl: String?
    var playedAtMs: Int
    var startedByUid: String

    var id: String { songId + String(playedAtMs) }
    var artistLine: String { artists?.joined(separator: " / ") ?? "" }

    enum CodingKeys: String, CodingKey {
        case name, artists, album
        case songId = "song_id"
        case durationMs = "duration_ms"
        case coverUrl = "cover_url"
        case playedAtMs = "played_at_ms"
        case startedByUid = "started_by_uid"
    }
}

private struct HistoryList: Decodable {
    var items: [ListenHistoryRow]
}

private struct SongMetaList: Decodable {
    var items: [MediaSyncDTOs.SongMeta]
}

// MARK: - View model

/// Drives the shared listen-together room: room state over REST, playback
/// sync over WebSocket frames, AVPlayer as the local engine.
///
/// Sync model (mirrors the Android client, no incremental frame math):
/// any room event → `GET /state` → realign the player. Local actions drive
/// the player FIRST, then broadcast the frame.
@MainActor
@Observable
final class ListenViewModel {
    // Room / connection
    var loading = true
    var error: String?
    var message: String?
    var connected = false
    var roomState: MediaSyncDTOs.ListenState?
    var loginPanelForced = false
    var importingCookie = false

    // Playback snapshot (player-driven, refreshed every 0.5s)
    var positionMs = 0
    var durationMs = 0
    var isPlaying = false
    var resolvingUrl = false

    // Lyric
    var lyricLines: [MediaSyncDTOs.SongLyricLine] = []
    var lyricKind = "none"
    var lyricLoading = false

    // Library tabs
    var searchKeyword = ""
    var searchResults: [MediaSyncDTOs.SongMeta] = []
    var searchLoading = false
    var toplists: [ToplistItem] = []
    var toplistTracks: [MediaSyncDTOs.SongMeta] = []
    var selectedToplist: ToplistItem?
    var chartsLoading = false
    var history: [ListenHistoryRow] = []
    var historyLoading = false
    var localTracks: [MediaSyncDTOs.SongMeta] = []
    var localLoading = false

    let player = AVPlayer()

    private let api: LoveAPIClient
    private let selfUid: String?
    private let socket: CottageSocket
    private var heartbeatTimer: Timer?
    private var timeObserver: Any?
    private var endObserver: NSObjectProtocol?
    private var started = false
    private var lastResolvedSongId: String?
    private var lastMediaUrl: URL?
    private var lastAppliedEventSeq = -1
    private var lastLyricSongId: String?
    private var lyricTask: Task<Void, Never>?

    init(api: LoveAPIClient, selfUid: String?) {
        self.api = api
        self.selfUid = selfUid
        socket = CottageSocket(makeURL: { ServerSettings.webSocketURL(path: "/cottage/listen/ws") })
        player.automaticallyWaitsToMinimizeStalling = false
    }

    // MARK: Derived

    var current: MediaSyncDTOs.ListenCurrent? { roomState?.current }
    var queue: [MediaSyncDTOs.SongMeta] { roomState?.queue ?? [] }
    var partners: [MediaSyncDTOs.ListenPartner] { roomState?.partners ?? [] }

    var selfNeteaseLoggedIn: Bool {
        partners.first(where: { $0.userUid == selfUid })?.neteaseLoggedIn ?? false
    }

    /// Show the cookie panel while the room is loaded and either the state
    /// says we are logged out, or a 409 / COOKIE_EXPIRED forced it open.
    var needLoginPanel: Bool {
        roomState != nil && (loginPanelForced || !selfNeteaseLoggedIn)
    }

    // MARK: Lifecycle

    func start() {
        guard !started else { return }
        started = true
        socket.onOpen = { [weak self] in
            self?.connected = true
            // Auto-reconnect may have missed frames: realign with the room.
            Task { await self?.loadState(silent: true) }
        }
        socket.onClose = { [weak self] _ in self?.connected = false }
        socket.onError = { [weak self] _ in self?.connected = false }
        socket.onFrame = { [weak self] frame in self?.handleFrame(frame) }
        socket.connect()
        startHeartbeat()
        observePlayer()
        Task {
            await loadState()
            await loadHistory()
            await loadLocalTracks()
            await loadToplists()
        }
    }

    func stop() {
        started = false
        heartbeatTimer?.invalidate()
        heartbeatTimer = nil
        lyricTask?.cancel()
        if let timeObserver {
            player.removeTimeObserver(timeObserver)
            self.timeObserver = nil
        }
        if let endObserver {
            NotificationCenter.default.removeObserver(endObserver)
            self.endObserver = nil
        }
        socket.close()
    }

    private func startHeartbeat() {
        let socket = socket
        let timer = Timer(timeInterval: 20, repeats: true) { _ in
            socket.send(type: "HEARTBEAT")
        }
        heartbeatTimer = timer
        RunLoop.main.add(timer, forMode: .common)
    }

    private func observePlayer() {
        let interval = CMTime(seconds: 0.5, preferredTimescale: 600)
        timeObserver = player.addPeriodicTimeObserver(forInterval: interval, queue: .main) { [weak self] _ in
            Task { @MainActor [weak self] in self?.updatePlaybackSnapshot() }
        }
        endObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self, let songId = self.current?.songId else { return }
                // Song ended: advance the shared room, then re-pull state
                // after the server applied the queue pop (250ms like Android).
                self.socket.send(type: "NEXT", payload: ["expected_song_id": songId])
                try? await Task.sleep(nanoseconds: 250_000_000)
                await self.loadState(silent: true)
            }
        }
    }

    // MARK: WebSocket

    private func handleFrame(_ frame: CottageSocket.Frame) {
        switch frame.type {
        case "COOKIE_EXPIRED":
            if selfUid == nil || frame.payload?["user_uid"] as? String == selfUid {
                loginPanelForced = true
                message = String(localized: "m4.listen.netease.expired")
            }
            Task { await loadState(silent: true) }
        case "LOGIN_OK", "LOGOUT":
            Task { await loadState(silent: true) }
        case "AUTO_PAUSED":
            message = String(localized: "m4.listen.auto.paused")
            Task { await loadState(silent: true) }
        case "PLAY", "PAUSE", "SEEK", "NEXT", "PREV",
             "QUEUE_APPEND", "QUEUE_REMOVE", "QUEUE_CLEAR":
            // No incremental frame math: re-pull the room and realign.
            if frame.type == "PLAY" || frame.type == "NEXT" {
                Task { await loadHistory() }
            }
            Task { await loadState(silent: true) }
        default:
            break
        }
    }

    // MARK: Room state

    func loadState(silent: Bool = false) async {
        if !silent { loading = true }
        do {
            let state = try await api.request(
                MediaSyncDTOs.ListenState.self, "GET", "/cottage/listen/state"
            )
            // Guard against event_seq regression: a slow REST reply must
            // never roll back state already applied from a newer WS event.
            let seq = state.current?.eventSeq ?? state.eventSeq
            if seq >= lastAppliedEventSeq {
                lastAppliedEventSeq = seq
                roomState = state
                error = nil
                await syncPlayer(state.current)
                maybeLoadLyric(state.current?.songId)
            }
        } catch {
            if roomState == nil {
                self.error = friendly(error)
            } else {
                message = friendly(error)
            }
        }
        loading = false
    }

    /// Realigned the player with the authoritative room head.
    private func syncPlayer(_ current: MediaSyncDTOs.ListenCurrent?) async {
        guard let current, let songId = current.songId, !songId.isEmpty else {
            player.replaceCurrentItem(with: nil)
            lastResolvedSongId = nil
            lastMediaUrl = nil
            positionMs = 0
            durationMs = 0
            isPlaying = false
            resolvingUrl = false
            return
        }

        let needsResolve = songId != lastResolvedSongId
        if needsResolve {
            await resolveSong(songId)
        }

        if lastMediaUrl != nil {
            let drift = abs(playerPositionMs() - current.positionMs)
            // Re-seek on song change, on drift beyond 1.5s, or whenever the
            // room is paused (a paused head must never be "close enough").
            if needsResolve || drift > 1500 || current.paused {
                seekPlayer(toMs: current.positionMs, rate: current.paused ? 0 : 1)
            } else {
                applyRate(current.paused ? 0 : 1)
            }
        }
        updatePlaybackSnapshot()
    }

    /// Fetches the playable URL for `songId` and swaps the AVPlayer item.
    /// `url == null` (copyright / VIP) shows a hint and does NOT auto-skip.
    private func resolveSong(_ songId: String) async {
        resolvingUrl = true
        defer { resolvingUrl = false }
        do {
            let resp = try await api.request(
                MediaSyncDTOs.SongUrl.self, "GET", "/cottage/listen/songs/\(songId)/url"
            )
            lastResolvedSongId = songId
            if let raw = resp.url, let url = ServerSettings.mediaURL(raw) {
                lastMediaUrl = url
                player.replaceCurrentItem(with: AVPlayerItem(asset: Self.mediaAsset(for: url)))
            } else {
                lastMediaUrl = nil
                player.replaceCurrentItem(with: nil)
                message = resp.errorKind != nil
                    ? String(localized: "m4.listen.unavailable")
                    : String(localized: "m4.listen.no.url")
            }
        } catch {
            lastResolvedSongId = songId
            lastMediaUrl = nil
            player.replaceCurrentItem(with: nil)
            message = friendly(error)
        }
    }

    private func updatePlaybackSnapshot() {
        let playerDurationMs = playerDuration()
        let remoteDuration = current?.songMeta?.durationMs ?? 0
        durationMs = max(playerDurationMs, remoteDuration)
        if player.currentItem != nil {
            positionMs = max(0, playerPositionMs())
        } else if let remote = current?.positionMs {
            positionMs = remote
        }
        isPlaying = player.timeControlStatus == .playing
    }

    private func playerPositionMs() -> Int {
        let seconds = player.currentTime().seconds
        guard seconds.isFinite else { return 0 }
        return Int(max(0, seconds * 1000))
    }

    private func playerDuration() -> Int {
        let seconds = player.currentItem?.duration.seconds ?? 0
        guard seconds.isFinite, seconds > 0 else { return 0 }
        return Int(seconds * 1000)
    }

    /// Cookie-gated asset: `/uploads/**` media needs the session cookie,
    /// NetEase CDN links simply carry no matching cookie through.
    static func mediaAsset(for url: URL) -> AVURLAsset {
        let cookies = HTTPCookieStorage.shared.cookies(for: url) ?? []
        // The ObjC constant AVURLAssetOptionsCookiesKey is not exposed to
        // Swift in this SDK; its value is the literal key string below.
        return AVURLAsset(url: url, options: ["AVURLAssetOptionsCookiesKey": cookies])
    }

    /// AVPlayer seeks are async: park the rate and apply it in the
    /// completion handler so playback never starts from a stale position.
    private func seekPlayer(toMs: Int, rate: Float) {
        let clamped = max(0, toMs)
        let time = CMTime(value: CMTimeValue(clamped), timescale: 1000)
        player.seek(
            to: time,
            toleranceBefore: .positiveInfinity,
            toleranceAfter: .positiveInfinity
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.applyRate(rate)
            }
        }
        positionMs = clamped
    }

    private func applyRate(_ rate: Float) {
        if rate == 0 {
            player.pause()
        } else {
            player.rate = rate
        }
        isPlaying = rate != 0
    }

    // MARK: Local controls (drive the player first, then broadcast)

    func playPause() {
        guard let current else { return }
        let pos = player.currentItem != nil ? playerPositionMs() : positionMs
        if current.paused {
            applyRate(1)
            setPausedOptimistic(false)
            var payload: [String: Any] = ["song_id": current.songId ?? "", "position_ms": pos]
            if let meta = current.songMeta {
                payload["song_meta"] = Self.songMetaPayload(meta)
            }
            socket.send(type: "PLAY", payload: payload)
        } else {
            player.pause()
            isPlaying = false
            setPausedOptimistic(true)
            socket.send(type: "PAUSE", payload: ["position_ms": pos])
        }
    }

    func next() {
        var payload: [String: Any] = [:]
        if let songId = current?.songId { payload["expected_song_id"] = songId }
        socket.send(type: "NEXT", payload: payload.isEmpty ? nil : payload)
        Task {
            try? await Task.sleep(nanoseconds: 250_000_000)
            await loadState(silent: true)
        }
    }

    /// PREV restarts the current song from zero.
    func prev() {
        seekPlayer(toMs: 0, rate: current?.paused == true ? 0 : 1)
        socket.send(type: "PREV")
        Task {
            try? await Task.sleep(nanoseconds: 250_000_000)
            await loadState(silent: true)
        }
    }

    func seekTo(_ ms: Int) {
        let clamped = max(0, ms)
        seekPlayer(toMs: clamped, rate: current?.paused == true ? 0 : 1)
        socket.send(type: "SEEK", payload: ["position_ms": clamped])
    }

    /// Optimistically resolve + start the song locally, then broadcast PLAY.
    func playNow(
        songId: String,
        name: String,
        artists: [String]?,
        album: String?,
        durationMs: Int?,
        coverUrl: String?
    ) {
        guard !songId.isEmpty else { return }
        message = nil
        lastResolvedSongId = nil
        Task {
            await resolveSong(songId)
            if lastMediaUrl != nil {
                seekPlayer(toMs: 0, rate: 1)
            }
            socket.send(type: "PLAY", payload: [
                "song_id": songId,
                "song_meta": Self.songMetaPayload(
                    songId: songId, name: name, artists: artists, album: album,
                    durationMs: durationMs, coverUrl: coverUrl
                ),
                "position_ms": 0,
            ])
            try? await Task.sleep(nanoseconds: 250_000_000)
            await loadState(silent: true)
        }
    }

    func playNow(_ song: MediaSyncDTOs.SongMeta) {
        playNow(
            songId: song.songId, name: song.name, artists: song.artists,
            album: song.album, durationMs: song.durationMs, coverUrl: song.coverUrl
        )
    }

    func appendQueue(_ song: MediaSyncDTOs.SongMeta) {
        guard !song.songId.isEmpty else { return }
        socket.send(type: "QUEUE_APPEND", payload: [
            "song_id": song.songId,
            "song_meta": Self.songMetaPayload(song),
        ])
        message = String(localized: "m4.listen.queue.added")
    }

    func removeQueue(at index: Int) {
        guard let room = roomState, queue.indices.contains(index) else { return }
        let song = queue[index]
        roomState?.queue.remove(at: index)
        socket.send(type: "QUEUE_REMOVE", payload: ["index": index, "song_id": song.songId])
    }

    func clearQueue() {
        roomState?.queue.removeAll()
        socket.send(type: "QUEUE_CLEAR")
    }

    private func setPausedOptimistic(_ paused: Bool) {
        // ListenCurrent has no public initializer, so patch in place.
        roomState?.current?.paused = paused
    }

    static func songMetaPayload(_ song: MediaSyncDTOs.SongMeta) -> [String: Any] {
        songMetaPayload(
            songId: song.songId, name: song.name, artists: song.artists,
            album: song.album, durationMs: song.durationMs, coverUrl: song.coverUrl
        )
    }

    private static func songMetaPayload(
        songId: String,
        name: String,
        artists: [String]?,
        album: String?,
        durationMs: Int?,
        coverUrl: String?
    ) -> [String: Any] {
        var meta: [String: Any] = ["song_id": songId, "name": name, "artists": artists ?? []]
        if let album { meta["album"] = album }
        if let durationMs { meta["duration_ms"] = durationMs }
        if let coverUrl { meta["cover_url"] = coverUrl }
        return meta
    }

    // MARK: Lyric

    private func maybeLoadLyric(_ songId: String?) {
        guard let songId, !songId.isEmpty else {
            lastLyricSongId = nil
            lyricLines = []
            lyricKind = "none"
            lyricLoading = false
            lyricTask?.cancel()
            return
        }
        guard songId != lastLyricSongId else { return }
        lastLyricSongId = songId
        lyricTask?.cancel()
        lyricLoading = true
        lyricTask = Task { [weak self] in
            guard let self else { return }
            do {
                let lyric = try await self.api.request(
                    MediaSyncDTOs.SongLyric.self, "GET", "/cottage/listen/songs/\(songId)/lyric"
                )
                guard !Task.isCancelled else { return }
                self.lyricLines = lyric.lines
                self.lyricKind = lyric.kind
            } catch {
                guard !Task.isCancelled else { return }
                self.lyricLines = []
                self.lyricKind = "none"
            }
            self.lyricLoading = false
        }
    }

    // MARK: Library tabs

    func search(_ keyword: String? = nil) async {
        let clean = (keyword ?? searchKeyword).trimmingCharacters(in: .whitespacesAndNewlines)
        if clean.isEmpty {
            searchKeyword = ""
            searchResults = []
            return
        }
        searchKeyword = clean
        searchLoading = true
        do {
            let resp = try await api.request(
                MediaSyncDTOs.SongSearch.self, "GET", "/cottage/listen/search",
                query: [URLQueryItem(name: "keyword", value: clean)]
            )
            searchResults = resp.items
        } catch {
            searchResults = []
            message = friendly(error)
        }
        searchLoading = false
    }

    func loadToplists() async {
        chartsLoading = true
        do {
            toplists = try await api.request(
                ToplistList.self, "GET", "/cottage/listen/discover/toplist"
            ).items
        } catch {
            message = friendly(error)
        }
        chartsLoading = false
    }

    func loadToplistTracks(_ toplist: ToplistItem) async {
        selectedToplist = toplist
        toplistTracks = []
        chartsLoading = true
        do {
            toplistTracks = try await api.request(
                MediaSyncDTOs.SongSearch.self,
                "GET", "/cottage/listen/discover/toplist/\(toplist.toplistId)/tracks"
            ).items
        } catch {
            message = friendly(error)
        }
        chartsLoading = false
    }

    func closeToplist() {
        selectedToplist = nil
        toplistTracks = []
    }

    func loadHistory() async {
        historyLoading = true
        do {
            history = try await api.request(
                HistoryList.self, "GET", "/cottage/listen/history",
                query: [URLQueryItem(name: "limit", value: "50")]
            ).items
        } catch {
            message = friendly(error)
        }
        historyLoading = false
    }

    func loadLocalTracks() async {
        localLoading = true
        do {
            localTracks = try await api.request(
                SongMetaList.self, "GET", "/cottage/listen/local-tracks"
            ).items
        } catch {
            message = friendly(error)
        }
        localLoading = false
    }

    func deleteLocalTrack(_ song: MediaSyncDTOs.SongMeta) async {
        do {
            try await api.requestVoid("DELETE", "/cottage/listen/local-tracks/\(song.songId)")
            localTracks.removeAll { $0.songId == song.songId }
        } catch {
            message = friendly(error)
        }
    }

    // MARK: NetEase login

    func importCookie(_ raw: String) async {
        let cookie = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard cookie.contains("MUSIC_U=") else {
            message = String(localized: "m4.listen.netease.invalid")
            return
        }
        importingCookie = true
        defer { importingCookie = false }
        do {
            try await api.requestVoid(
                "POST", "/cottage/listen/auth/import-cookie",
                body: MediaSyncDTOs.CookieImport(cookie: cookie)
            )
            message = String(localized: "m4.listen.netease.imported")
            loginPanelForced = false
            await loadState(silent: true)
            await loadToplists()
        } catch {
            message = friendly(error)
        }
    }

    // MARK: Errors

    private func friendly(_ error: Error) -> String {
        guard let apiError = error as? APIError else { return error.localizedDescription }
        if case .http(let status, _) = apiError, status == 409 {
            loginPanelForced = true
            return String(localized: "m4.listen.login.required")
        }
        return apiError.message
    }
}

// MARK: - View

private enum ListenTab: String, CaseIterable, Identifiable {
    case search
    case charts
    case history
    case local
    case queue

    var id: String { rawValue }

    var titleKey: LocalizedStringKey {
        switch self {
        case .search: "m4.listen.tab.search"
        case .charts: "m4.listen.tab.charts"
        case .history: "m4.listen.tab.history"
        case .local: "m4.listen.tab.local"
        case .queue: "m4.listen.tab.queue"
        }
    }
}

struct CottageListenView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: ListenViewModel?
    @State private var tab: ListenTab = .search

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("m4.listen.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                var uid: String?
                if case .loggedIn(let profile) = environment.session.state { uid = profile.uid }
                model = ListenViewModel(api: environment.api, selfUid: uid)
            }
            model?.start()
        }
        .onDisappear { model?.stop() }
    }

    private func content(_ model: ListenViewModel) -> some View {
        VStack(spacing: 12) {
            if let message = model.message {
                LoveSuccessBanner(message: message)
            }
            if let error = model.error, model.roomState == nil {
                LoveErrorView(message: error) {
                    Task { await model.loadState() }
                }
            } else {
                NowPlayingCard(model: model)
                LyricPanel(model: model)
                    .frame(height: 170)
                if model.needLoginPanel {
                    NeteaseLoginCard(model: model)
                }
                tabPills(model)
                tabContent(model)
                    .frame(maxHeight: .infinity)
            }
        }
        .padding(16)
    }

    private func tabPills(_ model: ListenViewModel) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(ListenTab.allCases) { item in
                    Button {
                        tab = item
                    } label: {
                        Text(item.titleKey)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(tab == item ? .white : LoveTheme.primaryAccessible)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 7)
                            .background(
                                tab == item ? AnyShapeStyle(LoveTheme.gradient) : AnyShapeStyle(LoveTheme.surface),
                                in: Capsule()
                            )
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func tabContent(_ model: ListenViewModel) -> some View {
        switch tab {
        case .search: SearchTab(model: model)
        case .charts: ChartsTab(model: model)
        case .history: HistoryTab(model: model)
        case .local: LocalTab(model: model)
        case .queue: QueueTab(model: model)
        }
    }
}

// MARK: - Now playing

private struct NowPlayingCard: View {
    let model: ListenViewModel

    var body: some View {
        LoveSoftCard {
            HStack {
                ConnectionBadge(connected: model.connected, partners: model.partners.count)
                Spacer()
                if model.resolvingUrl {
                    ProgressView()
                        .tint(LoveTheme.primaryAccessible)
                }
            }
            if let current = model.current, let songId = current.songId, !songId.isEmpty {
                HStack(spacing: 12) {
                    LoveAsyncImage(url: ServerSettings.mediaURL(current.songMeta?.coverUrl))
                        .frame(width: 72, height: 72)
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    VStack(alignment: .leading, spacing: 4) {
                        Text((current.songMeta?.name ?? "").isEmpty
                             ? String(localized: "m4.listen.unknown.song")
                             : current.songMeta!.name)
                            .font(.headline)
                            .foregroundStyle(LoveTheme.text)
                            .lineLimit(1)
                        Text(current.songMeta?.artistLine ?? "")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText)
                            .lineLimit(1)
                        if let album = current.songMeta?.album, !album.isEmpty {
                            Text(album)
                                .font(.caption2)
                                .foregroundStyle(LoveTheme.secondaryText)
                                .lineLimit(1)
                        }
                    }
                    Spacer(minLength: 0)
                }
                ListenSeekBar(
                    positionMs: model.positionMs,
                    durationMs: model.durationMs,
                    onSeek: { model.seekTo($0) }
                )
                HStack(spacing: 28) {
                    Button {
                        model.prev()
                    } label: {
                        Image(systemName: "backward.end.fill")
                            .font(.title3)
                            .foregroundStyle(LoveTheme.primaryAccessible)
                    }
                    .accessibilityLabel(Text("m4.listen.prev"))
                    Button {
                        model.playPause()
                    } label: {
                        Image(systemName: current.paused ? "play.circle.fill" : "pause.circle.fill")
                            .font(.system(size: 56))
                            .foregroundStyle(LoveTheme.gradient)
                    }
                    .accessibilityLabel(Text(current.paused ? "m4.listen.play" : "m4.listen.pause"))
                    Button {
                        model.next()
                    } label: {
                        Image(systemName: "forward.end.fill")
                            .font(.title3)
                            .foregroundStyle(LoveTheme.primaryAccessible)
                    }
                    .accessibilityLabel(Text("m4.listen.next"))
                }
                .frame(maxWidth: .infinity)
            } else {
                HStack(spacing: 12) {
                    Image(systemName: "music.note")
                        .font(.title)
                        .foregroundStyle(LoveTheme.secondaryText)
                        .frame(width: 64, height: 64)
                        .background(LoveTheme.outline.opacity(0.3))
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    VStack(alignment: .leading, spacing: 4) {
                        Text("m4.listen.empty.title")
                            .font(.headline)
                            .foregroundStyle(LoveTheme.text)
                        Text("m4.listen.empty.hint")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    Spacer(minLength: 0)
                }
            }
        }
    }
}

private struct ConnectionBadge: View {
    let connected: Bool
    let partners: Int

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(connected ? LoveTheme.mint : LoveTheme.outline)
                .frame(width: 8, height: 8)
            Text(connected
                 ? String(localized: "m4.listen.synced \(partners)")
                 : String(localized: "m4.listen.connecting"))
                .font(.caption)
                .foregroundStyle(LoveTheme.secondaryText)
        }
    }
}

private struct ListenSeekBar: View {
    let positionMs: Int
    let durationMs: Int
    let onSeek: (Int) -> Void

    @State private var dragging = false
    @State private var dragValue: Double = 0

    private var fraction: Double {
        durationMs > 0 ? min(1, max(0, Double(positionMs) / Double(durationMs))) : 0
    }

    var body: some View {
        VStack(spacing: 2) {
            Slider(
                value: Binding(
                    get: { dragging ? dragValue : fraction },
                    set: { dragValue = $0 }
                ),
                onEditingChanged: { editing in
                    if editing {
                        dragValue = fraction
                        dragging = true
                    } else {
                        dragging = false
                        if durationMs > 0 {
                            onSeek(Int(dragValue * Double(durationMs)))
                        }
                    }
                }
            )
            .tint(LoveTheme.primaryAccessible)
            .disabled(durationMs <= 0)
            HStack {
                Text(Self.format(displayMs))
                Spacer()
                Text(Self.format(durationMs))
            }
            .font(.caption2)
            .foregroundStyle(LoveTheme.secondaryText)
        }
    }

    private var displayMs: Int {
        if dragging, durationMs > 0 {
            return Int(dragValue * Double(durationMs))
        }
        return positionMs
    }

    static func format(_ ms: Int) -> String {
        let total = max(0, ms) / 1000
        return String(format: "%d:%02d", total / 60, total % 60)
    }
}

// MARK: - Lyric

private struct LyricPanel: View {
    let model: ListenViewModel

    private var currentIndex: Int {
        guard !model.lyricLines.isEmpty else { return 0 }
        var index = 0
        for (offset, line) in model.lyricLines.enumerated() where line.timeMs <= model.positionMs {
            index = offset
        }
        return index
    }

    var body: some View {
        Group {
            if model.lyricLoading {
                VStack(spacing: 8) {
                    ProgressView().tint(LoveTheme.primaryAccessible)
                    Text("m4.listen.lyric.loading")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                .frame(maxHeight: .infinity)
            } else if model.lyricKind == "instrumental" {
                Text("m4.listen.lyric.instrumental")
                    .font(.subheadline)
                    .foregroundStyle(LoveTheme.secondaryText)
                    .frame(maxHeight: .infinity)
            } else if model.lyricLines.isEmpty {
                Text("m4.listen.lyric.none")
                    .font(.subheadline)
                    .foregroundStyle(LoveTheme.secondaryText)
                    .frame(maxHeight: .infinity)
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 10) {
                            ForEach(Array(model.lyricLines.enumerated()), id: \.offset) { offset, line in
                                let active = offset == currentIndex
                                VStack(spacing: 2) {
                                    Text(line.text)
                                        .font(active ? .body.weight(.semibold) : .subheadline)
                                        .foregroundStyle(active ? LoveTheme.primaryAccessible : LoveTheme.secondaryText)
                                        .multilineTextAlignment(.center)
                                    if let translation = line.translation, !translation.isEmpty {
                                        Text(translation)
                                            .font(.caption)
                                            .foregroundStyle(LoveTheme.secondaryText)
                                            .multilineTextAlignment(.center)
                                    }
                                }
                                .id(offset)
                            }
                        }
                        .padding(.vertical, 12)
                        .frame(maxWidth: .infinity)
                    }
                    .onChange(of: currentIndex) { _, newValue in
                        withAnimation {
                            proxy.scrollTo(newValue, anchor: .center)
                        }
                    }
                }
            }
        }
        .background(LoveTheme.surface.opacity(0.6))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

// MARK: - NetEase login

private struct NeteaseLoginCard: View {
    let model: ListenViewModel
    @State private var cookieText = ""

    var body: some View {
        LoveSoftCard {
            Text("m4.listen.netease.title")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(LoveTheme.text)
            Text("m4.listen.netease.hint")
                .font(.footnote)
                .foregroundStyle(LoveTheme.secondaryText)
            HStack(spacing: 6) {
                ForEach(model.partners, id: \.userUid) { partner in
                    LovePill(
                        text: partner.nickname + " · " + String(
                            localized: partner.neteaseLoggedIn
                                ? "m4.listen.netease.on" : "m4.listen.netease.off"
                        ),
                        tint: partner.neteaseLoggedIn ? LoveTheme.mint : LoveTheme.outline
                    )
                }
            }
            TextEditor(text: $cookieText)
                .font(.footnote)
                .frame(height: 72)
                .scrollContentBackground(.hidden)
                .padding(8)
                .background(LoveTheme.background.opacity(0.6))
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .stroke(LoveTheme.outline, lineWidth: 1)
                }
                .overlay(alignment: .topLeading) {
                    if cookieText.isEmpty {
                        Text("m4.listen.netease.paste")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText.opacity(0.6))
                            .padding(12)
                            .allowsHitTesting(false)
                    }
                }
            LovePrimaryButton(
                titleKey: "m4.listen.netease.import",
                loading: model.importingCookie,
                enabled: cookieText.contains("MUSIC_U=")
            ) {
                Task { await model.importCookie(cookieText) }
            }
        }
    }
}

// MARK: - Tabs

private struct SearchTab: View {
    let model: ListenViewModel

    var body: some View {
        VStack(spacing: 10) {
            HStack(spacing: 8) {
                TextField("m4.listen.search.placeholder", text: Binding(
                    get: { model.searchKeyword },
                    set: { model.searchKeyword = $0 }
                ))
                .onSubmit { Task { await model.search() } }
                .submitLabel(.search)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(LoveTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                Button {
                    Task { await model.search() }
                } label: {
                    Image(systemName: "magnifyingglass")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                        .frame(width: 42, height: 42)
                        .background(LoveTheme.gradient, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
            }
            if model.searchLoading {
                ProgressView()
                    .tint(LoveTheme.primaryAccessible)
                    .frame(maxWidth: .infinity)
            } else if model.searchResults.isEmpty {
                LoveEmptyState(
                    systemImage: "music.quarternote.3",
                    titleKey: "m4.listen.tab.search",
                    messageKey: model.searchKeyword.isEmpty
                        ? "m4.listen.search.hint" : "m4.listen.search.empty"
                )
            } else {
                SongList(songs: model.searchResults, model: model)
            }
        }
    }
}

private struct ChartsTab: View {
    let model: ListenViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: 8) {
                if let selected = model.selectedToplist {
                    HStack {
                        Button {
                            model.closeToplist()
                        } label: {
                            Label("m4.listen.back", systemImage: "chevron.left")
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(LoveTheme.primaryAccessible)
                        }
                        Spacer()
                        Text(selected.name)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.text)
                            .lineLimit(1)
                        Spacer()
                        LovePill(text: String(localized: "m4.listen.tracks.count \(model.toplistTracks.count)"))
                    }
                    .padding(.horizontal, 4)
                    if model.chartsLoading {
                        ProgressView().tint(LoveTheme.primaryAccessible)
                    }
                    ForEach(model.toplistTracks) { song in
                        SongRow(song: song, model: model)
                    }
                } else if model.chartsLoading, model.toplists.isEmpty {
                    ProgressView()
                        .tint(LoveTheme.primaryAccessible)
                        .padding(.top, 24)
                } else if model.toplists.isEmpty {
                    LoveEmptyState(
                        systemImage: "chart.bar.fill",
                        titleKey: "m4.listen.tab.charts",
                        messageKey: "m4.listen.charts.empty"
                    )
                } else {
                    ForEach(model.toplists) { toplist in
                        Button {
                            Task { await model.loadToplistTracks(toplist) }
                        } label: {
                            LoveSoftCard {
                                HStack(spacing: 12) {
                                    LoveAsyncImage(url: ServerSettings.mediaURL(toplist.coverUrl))
                                        .frame(width: 48, height: 48)
                                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(toplist.name)
                                            .font(.subheadline.weight(.semibold))
                                            .foregroundStyle(LoveTheme.text)
                                            .lineLimit(1)
                                        Text([toplist.updateFrequency, String(localized: "m4.listen.tracks.count \(toplist.trackCount)")]
                                            .compactMap { $0 }
                                            .joined(separator: " · "))
                                            .font(.caption)
                                            .foregroundStyle(LoveTheme.secondaryText)
                                    }
                                    Spacer(minLength: 0)
                                    Image(systemName: "chevron.right")
                                        .font(.caption)
                                        .foregroundStyle(LoveTheme.outline)
                                }
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .padding(.vertical, 4)
        }
    }
}

private struct HistoryTab: View {
    let model: ListenViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: 8) {
                if model.historyLoading, model.history.isEmpty {
                    ProgressView()
                        .tint(LoveTheme.primaryAccessible)
                        .padding(.top, 24)
                } else if model.history.isEmpty {
                    LoveEmptyState(
                        systemImage: "clock.arrow.circlepath",
                        titleKey: "m4.listen.tab.history",
                        messageKey: "m4.listen.history.empty"
                    )
                } else {
                    ForEach(model.history) { row in
                        LoveSoftCard {
                            HStack(spacing: 12) {
                                LoveAsyncImage(url: ServerSettings.mediaURL(row.coverUrl))
                                    .frame(width: 46, height: 46)
                                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(row.name.isEmpty ? String(localized: "m4.listen.unknown.song") : row.name)
                                        .font(.subheadline.weight(.medium))
                                        .foregroundStyle(LoveTheme.text)
                                        .lineLimit(1)
                                    Text(row.artistLine)
                                        .font(.caption)
                                        .foregroundStyle(LoveTheme.secondaryText)
                                        .lineLimit(1)
                                }
                                Spacer(minLength: 0)
                                Button {
                                    model.playNow(
                                        songId: row.songId, name: row.name, artists: row.artists,
                                        album: row.album, durationMs: row.durationMs, coverUrl: row.coverUrl
                                    )
                                } label: {
                                    Image(systemName: "play.fill")
                                        .font(.subheadline)
                                        .foregroundStyle(LoveTheme.primaryAccessible)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
            }
            .padding(.vertical, 4)
        }
        .refreshable { await model.loadHistory() }
    }
}

private struct LocalTab: View {
    let model: ListenViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: 8) {
                if model.localLoading, model.localTracks.isEmpty {
                    ProgressView()
                        .tint(LoveTheme.primaryAccessible)
                        .padding(.top, 24)
                } else if model.localTracks.isEmpty {
                    LoveEmptyState(
                        systemImage: "waveform",
                        titleKey: "m4.listen.tab.local",
                        messageKey: "m4.listen.local.empty"
                    )
                } else {
                    ForEach(model.localTracks) { song in
                        SongRow(song: song, model: model, trailing: {
                            AnyView(
                                Image(systemName: "trash")
                                    .font(.footnote)
                                    .foregroundStyle(LoveTheme.rose)
                            )
                        }, trailingAction: {
                            Task { await model.deleteLocalTrack(song) }
                        })
                    }
                }
            }
            .padding(.vertical, 4)
        }
        .refreshable { await model.loadLocalTracks() }
    }
}

private struct QueueTab: View {
    let model: ListenViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: 8) {
                HStack {
                    LovePill(text: String(localized: "m4.listen.tracks.count \(model.queue.count)"))
                    Spacer()
                    Button("m4.listen.queue.clear") {
                        model.clearQueue()
                    }
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(LoveTheme.rose)
                    .disabled(model.queue.isEmpty)
                }
                .padding(.horizontal, 4)
                if model.queue.isEmpty {
                    LoveEmptyState(
                        systemImage: "list.bullet",
                        titleKey: "m4.listen.tab.queue",
                        messageKey: "m4.listen.queue.empty"
                    )
                } else {
                    ForEach(Array(model.queue.enumerated()), id: \.offset) { index, song in
                        LoveSoftCard {
                            HStack(spacing: 12) {
                                Text("\(index + 1)")
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(LoveTheme.primaryAccessible)
                                    .frame(width: 24)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(song.name.isEmpty ? String(localized: "m4.listen.unknown.song") : song.name)
                                        .font(.subheadline.weight(.medium))
                                        .foregroundStyle(LoveTheme.text)
                                        .lineLimit(1)
                                    Text(song.artistLine)
                                        .font(.caption)
                                        .foregroundStyle(LoveTheme.secondaryText)
                                        .lineLimit(1)
                                }
                                Spacer(minLength: 0)
                                Button {
                                    model.removeQueue(at: index)
                                } label: {
                                    Image(systemName: "minus.circle.fill")
                                        .font(.subheadline)
                                        .foregroundStyle(LoveTheme.rose)
                                }
                                .buttonStyle(.plain)
                            }
                            .contentShape(Rectangle())
                            .onTapGesture { model.playNow(song) }
                        }
                    }
                }
            }
            .padding(.vertical, 4)
        }
    }
}

// MARK: - Song rows

private struct SongList: View {
    let songs: [MediaSyncDTOs.SongMeta]
    let model: ListenViewModel

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 8) {
                ForEach(songs) { song in
                    SongRow(song: song, model: model)
                }
            }
            .padding(.vertical, 4)
        }
    }
}

/// Reusable library row: tap = play now, plus = queue append.
private struct SongRow: View {
    let song: MediaSyncDTOs.SongMeta
    let model: ListenViewModel
    var trailingIcon: AnyView?
    var trailingAction: (() -> Void)?

    init(
        song: MediaSyncDTOs.SongMeta,
        model: ListenViewModel,
        trailing: (() -> AnyView)? = nil,
        trailingAction: (() -> Void)? = nil
    ) {
        self.song = song
        self.model = model
        self.trailingIcon = trailing.map { $0() }
        self.trailingAction = trailingAction
    }

    var body: some View {
        LoveSoftCard {
            HStack(spacing: 12) {
                LoveAsyncImage(url: ServerSettings.mediaURL(song.coverUrl))
                    .frame(width: 46, height: 46)
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                VStack(alignment: .leading, spacing: 3) {
                    Text(song.name.isEmpty ? String(localized: "m4.listen.unknown.song") : song.name)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(LoveTheme.text)
                        .lineLimit(1)
                    Text(song.artistLine)
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
                Button {
                    model.playNow(song)
                } label: {
                    Image(systemName: "play.fill")
                        .font(.subheadline)
                        .foregroundStyle(LoveTheme.primaryAccessible)
                }
                .buttonStyle(.plain)
                Button {
                    model.appendQueue(song)
                } label: {
                    Image(systemName: "plus.circle")
                        .font(.subheadline)
                        .foregroundStyle(LoveTheme.primaryAccessible.opacity(0.7))
                }
                .buttonStyle(.plain)
                .accessibilityLabel(Text("m4.listen.queue.added"))
                if let trailingIcon {
                    Button {
                        trailingAction?()
                    } label: {
                        trailingIcon
                    }
                    .buttonStyle(.plain)
                }
            }
            .contentShape(Rectangle())
            .onTapGesture { model.playNow(song) }
        }
    }
}
