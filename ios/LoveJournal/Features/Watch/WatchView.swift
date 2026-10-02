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
import AVKit
import Observation
import SwiftUI
import UniformTypeIdentifiers

import LoveCore

// MARK: - Patch payloads (server contract: bookmarks REPLACE the full list)

/// A bookmark in its wire shape. `created_at` must round-trip as an
/// ISO-8601 string; `created_by_uid` is always re-stamped server-side.
struct BookmarkPayload: Encodable {
    var bid: String
    var positionMs: Int
    var label: String
    var createdAtIso: String

    enum CodingKeys: String, CodingKey {
        case bid, label
        case positionMs = "position_ms"
        case createdAtIso = "created_at"
    }
}

private struct SourcePatch: Encodable {
    var lastPositionMs: Int?
    var bookmarks: [BookmarkPayload]?

    init(lastPositionMs: Int? = nil, bookmarks: [BookmarkPayload]? = nil) {
        self.lastPositionMs = lastPositionMs
        self.bookmarks = bookmarks
    }

    enum CodingKeys: String, CodingKey {
        case bookmarks
        case lastPositionMs = "last_position_ms"
    }
}

/// Displayable bookmark chip (`MediaSyncDTOs.WatchBookmark` is decode-only,
/// so optimistic inserts/removals go through this mirror).
struct BookmarkChip: Identifiable {
    let bid: String
    let positionMs: Int
    let label: String
    let createdAtIso: String

    var id: String { bid }

    var payload: BookmarkPayload {
        BookmarkPayload(bid: bid, positionMs: positionMs, label: label, createdAtIso: createdAtIso)
    }
}

// MARK: - View model

/// Drives the shared watch-together room. Sync strategy is deliberately
/// simpler than listen: any partner event → `GET /state` → unconditionally
/// seek + set rate + playWhenReady. Local controls drive the player first,
/// then broadcast.
@MainActor
@Observable
final class WatchViewModel {
    var connected = false
    var partnerOnline = false
    var message: String?
    var sources: [MediaSyncDTOs.WatchSource] = []
    var currentTitle: String?
    var currentWsid: String?
    var currentBookmarks: [BookmarkChip] = []
    var isPlaying = false
    var uploading = false
    var deletingWsid: String?
    var loadingSources = true

    let player = AVPlayer()

    private let api: LoveAPIClient
    private let selfUid: String?
    private let socket: CottageSocket
    private var lastUrl: URL?
    private var started = false
    private var heartbeatTimer: Timer?
    private var progressTimer: Timer?
    private var lastProgressSentAt: TimeInterval = 0

    init(api: LoveAPIClient, selfUid: String?) {
        self.api = api
        self.selfUid = selfUid
        socket = CottageSocket(makeURL: { ServerSettings.webSocketURL(path: "/cottage/watch/ws") })
        player.automaticallyWaitsToMinimizeStalling = false
    }

    // MARK: Lifecycle

    func start() {
        guard !started else { return }
        started = true
        socket.onOpen = { [weak self] in
            self?.connected = true
            // Auto-reconnect may have missed frames: realign with the room.
            Task { await self?.refreshState() }
        }
        socket.onClose = { [weak self] _ in self?.connected = false }
        socket.onError = { [weak self] _ in self?.connected = false }
        socket.onFrame = { [weak self] frame in self?.handleFrame(frame) }
        socket.connect()
        startTimers()
        Task {
            await refreshState()
            await loadSources()
        }
    }

    func stop() {
        started = false
        heartbeatTimer?.invalidate()
        heartbeatTimer = nil
        progressTimer?.invalidate()
        progressTimer = nil
        socket.close()
    }

    private func startTimers() {
        let socket = socket
        let heartbeat = Timer(timeInterval: 20, repeats: true) { _ in
            socket.send(type: "HEARTBEAT")
        }
        heartbeatTimer = heartbeat
        RunLoop.main.add(heartbeat, forMode: .common)
        let progress = Timer(timeInterval: 5, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in self?.flushProgress() }
        }
        progressTimer = progress
        RunLoop.main.add(progress, forMode: .common)
    }

    // MARK: WebSocket

    private func handleFrame(_ frame: CottageSocket.Frame) {
        switch frame.type {
        case "PRESENCE":
            let uid = frame.payload?["user_uid"] as? String
            let online = frame.payload?["online"] as? Bool ?? false
            if uid != selfUid {
                partnerOnline = online
            }
        case "ROOM_CLEARED":
            stopPlayback()
            message = String(localized: "m4.watch.room.cleared")
            Task { await loadSources() }
        case "LOAD", "PLAY", "PAUSE", "SEEK", "RATE":
            // Our own echoes are already applied locally.
            if frame.originUid != selfUid {
                Task { await refreshState() }
            }
        default:
            break
        }
    }

    private func stopPlayback() {
        player.replaceCurrentItem(with: nil)
        lastUrl = nil
        currentTitle = nil
        currentWsid = nil
        currentBookmarks = []
        isPlaying = false
    }

    // MARK: Room state

    func refreshState() async {
        guard let state = try? await api.request(
            MediaSyncDTOs.WatchState.self, "GET", "/cottage/watch/state"
        ) else { return }
        applyCurrent(state.current)
        partnerOnline = state.partners.contains { $0.online && $0.userUid != selfUid }
    }

    /// Applies the authoritative room head: swap the item when the source
    /// changes, then unconditionally seek + rate + playWhenReady.
    private func applyCurrent(_ current: MediaSyncDTOs.WatchCurrent?) {
        guard let current else {
            if lastUrl != nil { stopPlayback() }
            return
        }
        let url = ServerSettings.mediaURL(current.sourceUrl)
        if url == nil {
            if lastUrl != nil {
                player.replaceCurrentItem(with: nil)
                lastUrl = nil
            }
        } else if url != lastUrl {
            let item = AVPlayerItem(asset: Self.mediaAsset(for: url!))
            player.replaceCurrentItem(with: item)
            lastUrl = url
        }
        if url != nil {
            let rate: Float = current.paused ? 0 : Float(current.rate)
            seekPlayer(toMs: current.positionMs, rate: rate)
        }
        if let wsid = current.sourceWsid {
            currentWsid = wsid
            currentTitle = current.sourceTitle
            currentBookmarks = Self.chips(
                from: sources.first(where: { $0.wsid == wsid })?.bookmarks,
                fallback: currentBookmarks
            )
        }
        isPlaying = !current.paused && url != nil
    }

    static func chips(
        from bookmarks: [MediaSyncDTOs.WatchBookmark]?,
        fallback: [BookmarkChip]
    ) -> [BookmarkChip] {
        guard let bookmarks else { return fallback }
        return bookmarks
            .map {
                BookmarkChip(
                    bid: $0.bid,
                    positionMs: $0.positionMs,
                    label: $0.label,
                    createdAtIso: WatchViewModel.isoFormatter.string(from: $0.createdAt)
                )
            }
            .sorted { $0.positionMs < $1.positionMs }
    }

    private static let isoFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    /// Cookie-gated asset for `/uploads/**` videos (the media route is
    /// partner-only; direct links just carry no matching cookie).
    static func mediaAsset(for url: URL) -> AVURLAsset {
        let cookies = HTTPCookieStorage.shared.cookies(for: url) ?? []
        // The ObjC constant AVURLAssetOptionsCookiesKey is not exposed to
        // Swift in this SDK; its value is the literal key string below.
        return AVURLAsset(url: url, options: ["AVURLAssetOptionsCookiesKey": cookies])
    }

    /// AVPlayer seeks are async: apply the rate in the completion handler
    /// so playback never resumes from a stale position.
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
    }

    private func applyRate(_ rate: Float) {
        if rate == 0 {
            player.pause()
            isPlaying = false
        } else {
            player.rate = rate
            isPlaying = true
        }
    }

    func playerPositionMs() -> Int {
        let seconds = player.currentTime().seconds
        guard seconds.isFinite else { return 0 }
        return Int(max(0, seconds * 1000))
    }

    // MARK: Library

    func loadSources() async {
        do {
            let list = try await api.request(
                MediaSyncDTOs.WatchSourceList.self, "GET", "/cottage/watch/sources"
            )
            sources = list.items
            if let wsid = currentWsid {
                currentBookmarks = Self.chips(
                    from: list.items.first(where: { $0.wsid == wsid })?.bookmarks,
                    fallback: currentBookmarks
                )
            }
        } catch {
            message = friendly(error)
        }
        loadingSources = false
    }

    // MARK: Local controls (drive the player first, then broadcast)

    func togglePlay() {
        let pos = playerPositionMs()
        if player.timeControlStatus == .playing {
            player.pause()
            isPlaying = false
            socket.send(type: "PAUSE", payload: ["position_ms": pos])
            // Flush immediately so a background/tab-close a moment later
            // still preserves the resume position.
            flushProgress(force: true)
        } else {
            player.play()
            isPlaying = true
            socket.send(type: "PLAY", payload: ["position_ms": pos])
        }
    }

    func seekBy(_ deltaMs: Int) {
        let target = max(0, playerPositionMs() + deltaMs)
        seekPlayer(toMs: target, rate: player.timeControlStatus == .playing ? 1 : 0)
        socket.send(type: "SEEK", payload: ["position_ms": target])
    }

    /// Loads a library source: seed the player at the server-side resume
    /// position (paused), then announce LOAD{0} + SEEK{resume} so the
    /// partner lands on the same spot.
    func loadSource(_ source: MediaSyncDTOs.WatchSource) {
        guard let url = ServerSettings.mediaURL(source.url) else { return }
        let startMs = max(0, source.lastPositionMs ?? 0)
        player.replaceCurrentItem(with: AVPlayerItem(asset: Self.mediaAsset(for: url)))
        lastUrl = url
        player.pause()
        isPlaying = false
        seekPlayer(toMs: startMs, rate: 0)
        socket.send(type: "LOAD", payload: [
            "source_wsid": source.wsid,
            "source_url": source.url,
            "source_title": source.title,
            "source_kind": source.kind,
            "position_ms": 0,
        ])
        if startMs > 0 {
            socket.send(type: "SEEK", payload: ["position_ms": startMs])
        }
        currentTitle = source.title
        currentWsid = source.wsid
        currentBookmarks = Self.chips(from: source.bookmarks, fallback: [])
    }

    func invite() async {
        do {
            try await api.requestVoid("POST", "/cottage/watch/invite")
            message = String(localized: "m4.watch.invited")
        } catch {
            message = friendly(error)
        }
    }

    // MARK: Bookmarks

    func addBookmark() {
        guard let wsid = currentWsid else { return }
        let pos = playerPositionMs()
        guard pos > 0 else {
            message = String(localized: "m4.watch.bookmark.too.early")
            return
        }
        guard currentBookmarks.count < 200 else {
            message = String(localized: "m4.watch.bookmark.limit")
            return
        }
        var next = currentBookmarks.map(\.payload)
        next.append(BookmarkPayload(
            bid: UUID().uuidString,
            positionMs: pos,
            label: String(localized: "m4.watch.bookmark.label \(Self.formatTime(pos))"),
            createdAtIso: Self.isoFormatter.string(from: Date())
        ))
        patchBookmarks(wsid: wsid, payloads: next)
    }

    func jumpToBookmark(_ chip: BookmarkChip) {
        seekPlayer(toMs: chip.positionMs, rate: player.timeControlStatus == .playing ? 1 : 0)
        socket.send(type: "SEEK", payload: ["position_ms": chip.positionMs])
        flushProgress(force: true)
    }

    /// Long-press delete: PATCH the full list minus this chip.
    func deleteBookmark(_ chip: BookmarkChip) {
        guard let wsid = currentWsid else { return }
        let next = currentBookmarks.filter { $0.bid != chip.bid }.map(\.payload)
        patchBookmarks(wsid: wsid, payloads: next)
    }

    private func patchBookmarks(wsid: String, payloads: [BookmarkPayload]) {
        let optimistic = payloads
            .map {
                BookmarkChip(bid: $0.bid, positionMs: $0.positionMs, label: $0.label, createdAtIso: $0.createdAtIso)
            }
            .sorted { $0.positionMs < $1.positionMs }
        currentBookmarks = optimistic
        Task { [weak self] in
            guard let self else { return }
            do {
                try await self.api.requestVoid(
                    "PATCH", "/cottage/watch/sources/\(wsid)",
                    body: SourcePatch(bookmarks: payloads)
                )
                await self.loadSources()
            } catch {
                self.message = self.friendly(error)
                await self.loadSources()
            }
        }
    }

    // MARK: Progress reporting

    /// PATCHes the resume position; throttled to ≥4s on top of the 5s loop.
    func flushProgress(force: Bool = false) {
        guard let wsid = currentWsid, !wsid.isEmpty else { return }
        let pos = playerPositionMs()
        guard pos > 0 else { return }
        let now = Date().timeIntervalSince1970
        if !force {
            guard now - lastProgressSentAt >= 4 else { return }
        }
        lastProgressSentAt = now
        let payload = SourcePatch(lastPositionMs: pos)
        Task { [weak self] in
            try? await self?.api.requestVoid("PATCH", "/cottage/watch/sources/\(wsid)", body: payload)
        }
    }

    // MARK: Library management

    func addSource(title: String, url: String) async {
        let cleanTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanUrl = url.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanTitle.isEmpty, !cleanUrl.isEmpty else {
            message = String(localized: "m4.watch.source.missing")
            return
        }
        do {
            _ = try await api.request(
                MediaSyncDTOs.WatchSource.self, "POST", "/cottage/watch/sources",
                body: MediaSyncDTOs.WatchSourceCreate(title: cleanTitle, url: cleanUrl)
            )
            message = String(localized: "m4.watch.source.added")
            await loadSources()
        } catch {
            message = friendly(error)
        }
    }

    func deleteSource(_ source: MediaSyncDTOs.WatchSource) async {
        deletingWsid = source.wsid
        defer { deletingWsid = nil }
        do {
            try await api.requestVoid("DELETE", "/cottage/watch/sources/\(source.wsid)")
            sources.removeAll { $0.wsid == source.wsid }
            message = String(localized: "m4.watch.deleted")
            // If it was on stage the room is cleared server-side (ROOM_CLEARED
            // arrives too); refresh to pick the new head either way.
            await refreshState()
        } catch {
            message = friendly(error)
        }
    }

    /// Streams the picked video into a multipart temp file (a 2GB upload
    /// must never be fully materialized in memory), then POSTs it with the
    /// session cookie from `HTTPCookieStorage`.
    func uploadVideo(from url: URL) async {
        uploading = true
        defer { uploading = false }
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        let fileName = url.lastPathComponent.isEmpty ? "video.mp4" : url.lastPathComponent
        let tempURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("watch-upload-\(UUID().uuidString)")
        do {
            let boundary = try Self.writeMultipartBody(fromFile: url, fileName: fileName, to: tempURL)
            defer { try? FileManager.default.removeItem(at: tempURL) }
            guard let endpoint = URL(string: ServerSettings.apiBase + "/cottage/watch/sources/upload") else {
                throw APIError.serverNotConfigured
            }
            var request = URLRequest(url: endpoint)
            request.httpMethod = "POST"
            request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
            request.timeoutInterval = 3600
            let (_, response) = try await URLSession.shared.upload(for: request, fromFile: tempURL)
            guard let http = response as? HTTPURLResponse else {
                throw APIError.transport(.other("watch upload: no response"))
            }
            guard (200...299).contains(http.statusCode) else {
                throw APIError.http(status: http.statusCode, detail: APIError.serverDetail(from: nil))
            }
            message = String(localized: "m4.watch.uploaded")
            await loadSources()
        } catch {
            message = friendly(error)
        }
    }

    /// Builds the multipart body on disk and returns the boundary used.
    private static func writeMultipartBody(
        fromFile fileURL: URL,
        fileName: String,
        to destination: URL
    ) throws -> String {
        let boundary = "LoveJournal-\(UUID().uuidString)"
        FileManager.default.createFile(atPath: destination.path, contents: nil)
        let output = try FileHandle(forWritingTo: destination)
        defer { try? output.close() }
        output.write(Data((
            "--\(boundary)\r\n"
            + "Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName)\"\r\n"
            + "Content-Type: video/mp4\r\n\r\n"
        ).utf8))
        let input = try FileHandle(forReadingFrom: fileURL)
        defer { try? input.close() }
        while let chunk = try input.read(upToCount: 4 * 1024 * 1024), !chunk.isEmpty {
            output.write(chunk)
        }
        output.write(Data("\r\n--\(boundary)--\r\n".utf8))
        return boundary
    }

    static func formatTime(_ ms: Int) -> String {
        let total = max(0, ms) / 1000
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        let seconds = total % 60
        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, seconds)
        }
        return String(format: "%d:%02d", minutes, seconds)
    }

    private func friendly(_ error: Error) -> String {
        if let apiError = error as? APIError { return apiError.message }
        return error.localizedDescription
    }
}

// MARK: - View

struct CottageWatchView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: WatchViewModel?
    @State private var importerPresented = false
    @State private var addSheetPresented = false

    private static var videoTypes: [UTType] {
        var types: [UTType] = [.movie, .mpeg4Movie, .quickTimeMovie]
        if let webm = UTType(filenameExtension: "webm"), !types.contains(webm) {
            types.append(webm)
        }
        return types
    }

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("m4.watch.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                var uid: String?
                if case .loggedIn(let profile) = environment.session.state { uid = profile.uid }
                model = WatchViewModel(api: environment.api, selfUid: uid)
            }
            model?.start()
        }
        .onDisappear { model?.stop() }
        .fileImporter(
            isPresented: $importerPresented,
            allowedContentTypes: Self.videoTypes,
            allowsMultipleSelection: false
        ) { result in
            if case .success(let urls) = result, let url = urls.first {
                Task { await model?.uploadVideo(from: url) }
            }
        }
        .sheet(isPresented: $addSheetPresented) {
            if let model {
                AddSourceSheet(model: model)
            }
        }
    }

    private func content(_ model: WatchViewModel) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                statusRow(model)
                VideoPlayer(player: model.player)
                    .aspectRatio(16.0 / 9.0, contentMode: .fit)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                controlRow(model)
                titleAndBookmarks(model)
                Divider()
                libraryHeader(model)
                if model.loadingSources, model.sources.isEmpty {
                    ProgressView()
                        .tint(LoveTheme.primaryAccessible)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 20)
                } else if model.sources.isEmpty {
                    LoveEmptyState(
                        systemImage: "film.stack",
                        titleKey: "m4.watch.library",
                        messageKey: "m4.watch.empty.hint"
                    )
                } else {
                    ForEach(model.sources) { source in
                        SourceRow(
                            source: source,
                            isCurrent: source.wsid == model.currentWsid,
                            deleting: model.deletingWsid == source.wsid
                        ) {
                            model.loadSource(source)
                        } onDelete: {
                            Task { await model.deleteSource(source) }
                        }
                    }
                }
            }
            .padding(16)
        }
        .refreshable { await model.loadSources() }
    }

    private func statusRow(_ model: WatchViewModel) -> some View {
        HStack(spacing: 6) {
            Circle()
                .fill(model.connected ? (model.partnerOnline ? LoveTheme.mint : LoveTheme.peach) : LoveTheme.outline)
                .frame(width: 8, height: 8)
            Text(statusText(model))
                .font(.caption)
                .foregroundStyle(LoveTheme.secondaryText)
        }
    }

    private func statusText(_ model: WatchViewModel) -> String {
        if !model.connected { return String(localized: "m4.watch.connecting") }
        return model.partnerOnline
            ? String(localized: "m4.watch.partner.online")
            : String(localized: "m4.watch.partner.offline")
    }

    private func controlRow(_ model: WatchViewModel) -> some View {
        HStack(spacing: 10) {
            Button {
                model.togglePlay()
            } label: {
                Label(
                    model.isPlaying ? "m4.watch.pause" : "m4.watch.play",
                    systemImage: model.isPlaying ? "pause.fill" : "play.fill"
                )
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.white)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(LoveTheme.gradient, in: Capsule())
            }
            Button {
                model.seekBy(-10_000)
            } label: {
                Text("-10s")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(LoveTheme.primaryAccessible)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .overlay(Capsule().stroke(LoveTheme.primaryAccessible.opacity(0.5), lineWidth: 1))
            }
            .buttonStyle(.plain)
            Button {
                model.seekBy(10_000)
            } label: {
                Text("+10s")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(LoveTheme.primaryAccessible)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .overlay(Capsule().stroke(LoveTheme.primaryAccessible.opacity(0.5), lineWidth: 1))
            }
            .buttonStyle(.plain)
            Spacer()
            Button {
                Task { await model.invite() }
            } label: {
                Label("m4.watch.invite", systemImage: "envelope")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(LoveTheme.primaryAccessible)
            }
        }
        .buttonStyle(.plain)
    }

    private func titleAndBookmarks(_ model: WatchViewModel) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(model.currentTitle ?? String(localized: "m4.watch.empty.title"))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                    .lineLimit(2)
                Spacer()
                if model.currentWsid != nil {
                    Button {
                        model.addBookmark()
                    } label: {
                        Label(
                            String(localized: "m4.watch.bookmarks.count \(model.currentBookmarks.count)"),
                            systemImage: "bookmark"
                        )
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(LoveTheme.primaryAccessible)
                    }
                    .buttonStyle(.plain)
                }
            }
            if !model.currentBookmarks.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(model.currentBookmarks) { chip in
                            Button {
                                model.jumpToBookmark(chip)
                            } label: {
                                HStack(spacing: 4) {
                                    Text(chip.label.isEmpty
                                         ? String(localized: "m4.watch.bookmark.untitled")
                                         : chip.label)
                                        .lineLimit(1)
                                    Text(WatchViewModel.formatTime(chip.positionMs))
                                        .fontWeight(.semibold)
                                }
                                .font(.caption2)
                                .foregroundStyle(LoveTheme.primaryAccessible)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(LoveTheme.primaryAccessible.opacity(0.12), in: Capsule())
                            }
                            .buttonStyle(.plain)
                            .contextMenu {
                                Button(role: .destructive) {
                                    model.deleteBookmark(chip)
                                } label: {
                                    Label("m4.watch.delete", systemImage: "trash")
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    private func libraryHeader(_ model: WatchViewModel) -> some View {
        HStack {
            Text("m4.watch.library")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(LoveTheme.text)
            Spacer()
            Button {
                importerPresented = true
            } label: {
                HStack(spacing: 4) {
                    if model.uploading {
                        ProgressView()
                            .tint(LoveTheme.primaryAccessible)
                    } else {
                        Image(systemName: "arrow.up.circle")
                    }
                    Text(model.uploading ? "m4.watch.uploading" : "m4.watch.upload")
                }
                .font(.footnote)
                .foregroundStyle(LoveTheme.primaryAccessible)
            }
            .buttonStyle(.plain)
            .disabled(model.uploading)
            Button {
                addSheetPresented = true
            } label: {
                Label("m4.watch.add.link", systemImage: "link")
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.primaryAccessible)
            }
            .buttonStyle(.plain)
        }
    }
}

// MARK: - Rows & sheets

private struct SourceRow: View {
    let source: MediaSyncDTOs.WatchSource
    let isCurrent: Bool
    let deleting: Bool
    let onPlay: () -> Void
    let onDelete: () -> Void

    var body: some View {
        Button(action: onPlay) {
            LoveSoftCard {
                HStack(spacing: 10) {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 8) {
                            Text(source.title)
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(LoveTheme.text)
                                .lineLimit(1)
                            if isCurrent {
                                LovePill(text: String(localized: "m4.watch.playing"))
                            }
                        }
                        HStack(spacing: 8) {
                            LovePill(
                                text: String(localized: source.kind == "upload" ? "m4.watch.source.upload" : "m4.watch.source.direct"),
                                tint: LoveTheme.lavender
                            )
                            if let last = source.lastPositionMs, last > 0 {
                                Text(String(localized: "m4.watch.last.position \(WatchViewModel.formatTime(last))"))
                                    .font(.caption2)
                                    .foregroundStyle(LoveTheme.primaryAccessible)
                            }
                            if !source.bookmarks.isEmpty {
                                Label(
                                    String(localized: "m4.watch.bookmarks.count \(source.bookmarks.count)"),
                                    systemImage: "bookmark"
                                )
                                .font(.caption2)
                                .foregroundStyle(LoveTheme.secondaryText)
                            }
                        }
                    }
                    Spacer(minLength: 0)
                    Button {
                        onDelete()
                    } label: {
                        if deleting {
                            ProgressView()
                                .tint(LoveTheme.rose)
                        } else {
                            Image(systemName: "trash")
                                .font(.footnote)
                                .foregroundStyle(LoveTheme.rose)
                        }
                    }
                    .buttonStyle(.plain)
                    .disabled(deleting)
                }
            }
        }
        .buttonStyle(.plain)
    }
}

private struct AddSourceSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: WatchViewModel
    @State private var title = ""
    @State private var url = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: "m4.watch.source.title") {
                        TextField("m4.watch.source.title", text: $title)
                    }
                    LoveField(labelKey: "m4.watch.source.url") {
                        TextField("m4.watch.source.url", text: $url)
                            .keyboardType(.URL)
                    }
                    LovePrimaryButton(titleKey: "m4.watch.source.add", enabled: !title.isEmpty && !url.isEmpty) {
                        let cleanTitle = title
                        let cleanUrl = url
                        dismiss()
                        Task { await model.addSource(title: cleanTitle, url: cleanUrl) }
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle("m4.watch.add.link")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("common.cancel") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium])
    }
}
