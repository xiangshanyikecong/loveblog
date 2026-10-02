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

import Observation
import SwiftUI

import LoveCore

// MARK: - Grid fallbacks

/// Engines emit `size` for square boards and `cols`/`rows` otherwise; the
/// fallbacks cover snapshots where neither is present yet (e.g. `waiting`).
enum GameGrid {
    static func fallbackCols(_ game: String) -> Int {
        switch game {
        case "tictactoe": return 3
        case "reversi": return 8
        case "memory": return 4
        case "linklink": return 8
        default: return 15
        }
    }

    static func fallbackRows(_ game: String) -> Int {
        switch game {
        case "tictactoe": return 3
        case "reversi": return 8
        case "memory": return 4
        case "linklink": return 6
        default: return 15
        }
    }
}

// MARK: - Text helpers

/// Localized labels derived from server enum strings.
enum GameText {
    static func endReason(_ reason: String) -> String {
        switch reason {
        case "five": return String(localized: "m5a.reason.five")
        case "draw": return String(localized: "m5a.reason.draw")
        case "count": return String(localized: "m5a.reason.count")
        case "surrender": return String(localized: "m5a.reason.surrender")
        case "score": return String(localized: "m5a.reason.score")
        default: return reason
        }
    }
}

// MARK: - View model

/// One board-game session: REST bootstrap + realtime socket for the shared
/// five-game protocol (`/cottage/games/{game}/ws`).
@MainActor
@Observable
final class GameViewModel {
    struct FloatingEmote: Identifiable {
        let id = UUID()
        let emote: String
        let fromNickname: String
        /// Random horizontal anchor (0…1) for the floating bubble.
        let xRatio: CGFloat
    }

    let game: String
    let selfUid: String?

    private(set) var loading = true
    private(set) var connected = false
    private(set) var state: GameDTOs.GameState?
    private(set) var players: [GameDTOs.GamePlayer] = []
    private(set) var emotes: [FloatingEmote] = []

    var error: String?
    var errorBanner: String?
    var toast: String?
    /// Partner asked for an undo → confirmation dialog.
    var incomingUndo = false

    private let api: LoveAPIClient
    private var socket: CottageSocket?
    private var toastTask: Task<Void, Never>?
    private var bannerTask: Task<Void, Never>?
    /// Latest WS presence; merged into `players` whenever they (re)load, so a
    /// PRESENCE_SNAPSHOT arriving before the REST seats can't get lost.
    private var onlineUids: Set<String> = []

    init(api: LoveAPIClient, game: String, selfUid: String?) {
        self.api = api
        self.game = game
        self.selfUid = selfUid
    }

    // MARK: Derived state

    var cols: Int {
        if let cols = state?.cols { return cols }
        if let size = state?.size { return size }
        return GameGrid.fallbackCols(game)
    }

    var rows: Int {
        if let rows = state?.rows { return rows }
        if let size = state?.size { return size }
        return GameGrid.fallbackRows(game)
    }

    var blackPlayer: GameDTOs.GamePlayer? { players.first { $0.color == "black" } }
    var whitePlayer: GameDTOs.GamePlayer? { players.first { $0.color == "white" } }
    var myColor: String? { players.first { $0.uid == selfUid }?.color }

    var isMyTurn: Bool {
        guard let selfUid, state?.phase == "playing" else { return false }
        return state?.turnUid == selfUid
    }

    var canInteract: Bool { isMyTurn && connected }

    /// memory/linklink carry live pair scores instead of move counts.
    var showScores: Bool { game == "memory" || game == "linklink" }

    var legalPoints: Set<String> {
        var points = Set<String>()
        for move in state?.legalMoves ?? [] where move.count >= 2 {
            points.insert("\(move[0]),\(move[1])")
        }
        return points
    }

    // MARK: Lifecycle

    func start() {
        connectSocket()
        Task { await loadState() }
    }

    func stop() {
        socket?.close()
        socket = nil
        toastTask?.cancel()
        bannerTask?.cancel()
    }

    func retry() async {
        await loadState()
    }

    private func connectSocket() {
        let game = self.game
        let socket = CottageSocket {
            ServerSettings.webSocketURL(path: "/cottage/games/\(game)/ws")
        }
        socket.onOpen = { [weak self] in self?.connected = true }
        socket.onClose = { [weak self] _ in self?.connected = false }
        socket.onFrame = { [weak self] frame in self?.handleFrame(frame) }
        self.socket = socket
        socket.connect()
    }

    private func loadState() async {
        do {
            let room = try await api.request(
                GameDTOs.GameRoomState.self, "GET", "/cottage/games/\(game)/state"
            )
            apply(room)
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? String(localized: "m5a.error.generic")
        }
        loading = false
    }

    private func apply(_ room: GameDTOs.GameRoomState) {
        state = room.state
        // The WS STATE payload carries no players — keep the REST-loaded
        // seats and refresh them only when the REST response (which does
        // include players) lands.
        if !room.players.isEmpty {
            players = room.players.map { player in
                var updated = player
                updated.online = onlineUids.contains(player.uid)
                return updated
            }
        }
    }

    // MARK: Socket events

    private func handleFrame(_ frame: CottageSocket.Frame) {
        guard let payload = frame.payload else { return }
        switch frame.type {
        case "STATE", "GAME_OVER":
            if let room = Self.decodeRoom(payload) {
                apply(room)
            }
        case "PRESENCE":
            if let uid = payload["uid"] as? String,
               let online = payload["online"] as? Bool {
                if online { onlineUids.insert(uid) } else { onlineUids.remove(uid) }
                updatePresence(uid: uid, online: online)
            }
        case "PRESENCE_SNAPSHOT":
            if let online = payload["online"] as? [Any] {
                onlineUids = Set(online.compactMap { $0 as? String })
                players = players.map { player in
                    var updated = player
                    updated.online = onlineUids.contains(player.uid)
                    return updated
                }
            }
        case "UNDO_REQUEST":
            incomingUndo = true
        case "UNDO_RESULT":
            incomingUndo = false
            let accepted = payload["accepted"] as? Bool ?? false
            let key: String.LocalizationValue =
                accepted ? "m5a.undo.accepted" : "m5a.undo.declined"
            showToast(String(localized: key))
        case "EMOTE":
            let emote = payload["emote"] as? String ?? ""
            let nickname = payload["from_nickname"] as? String ?? ""
            guard !emote.isEmpty else { return }
            spawnEmote(emote, from: nickname)
        case "ERROR":
            showErrorBanner(
                (payload["message"] as? String) ?? String(localized: "m5a.error.generic")
            )
        default:
            break
        }
    }

    private func updatePresence(uid: String, online: Bool) {
        for index in players.indices where players[index].uid == uid {
            players[index].online = online
        }
    }

    /// The WS payload is the flat room snapshot — round-trip through
    /// JSONSerialization and reuse the tolerant REST decoder.
    private static func decodeRoom(_ payload: [String: Any]) -> GameDTOs.GameRoomState? {
        guard let data = try? JSONSerialization.data(withJSONObject: payload) else { return nil }
        return try? LoveAPIClient.decode(GameDTOs.GameRoomState.self, from: data)
    }

    // MARK: Actions

    func play(x: Int, y: Int) {
        guard canInteract else { return }
        socket?.send(type: "MOVE", payload: ["x": x, "y": y])
    }

    func newGame() {
        socket?.send(type: "NEW_GAME")
    }

    func surrender() {
        socket?.send(type: "SURRENDER")
    }

    func requestUndo() {
        socket?.send(type: "UNDO_REQUEST")
        showToast(String(localized: "m5a.undo.sent"))
    }

    func respondUndo(accept: Bool) {
        incomingUndo = false
        socket?.send(type: "UNDO_RESPOND", payload: ["accept": accept])
    }

    func sendEmote(_ emote: String) {
        socket?.send(type: "EMOTE", payload: ["emote": emote])
    }

    // MARK: Transient feedback

    func showToast(_ text: String) {
        toast = text
        toastTask?.cancel()
        toastTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(3))
            guard !Task.isCancelled else { return }
            self?.toast = nil
        }
    }

    func showErrorBanner(_ text: String) {
        errorBanner = text
        bannerTask?.cancel()
        bannerTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(5))
            guard !Task.isCancelled else { return }
            self?.errorBanner = nil
        }
    }

    private func spawnEmote(_ emote: String, from nickname: String) {
        let item = FloatingEmote(
            emote: emote,
            fromNickname: nickname,
            xRatio: CGFloat.random(in: 0.2...0.8)
        )
        emotes.append(item)
        if emotes.count > 6 {
            emotes.removeFirst(emotes.count - 6)
        }
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(2.4))
            self?.emotes.removeAll { $0.id == item.id }
        }
    }
}

// MARK: - Screen

/// One board session shared by the five games (`game` selects the renderer).
struct GameBoardScreen: View {
    @Environment(AppEnvironment.self) private var environment
    let game: String
    @State private var model: GameViewModel?

    var body: some View {
        Group {
            if let model {
                @Bindable var model = model
                screen(model)
                    .confirmationDialog(
                        String(localized: "m5a.undo.incoming"),
                        isPresented: $model.incomingUndo,
                        titleVisibility: .visible
                    ) {
                        Button(String(localized: "m5a.undo.accept")) {
                            model.respondUndo(accept: true)
                        }
                        Button(String(localized: "m5a.undo.decline"), role: .destructive) {
                            model.respondUndo(accept: false)
                        }
                        Button("common.cancel", role: .cancel) {}
                    }
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(GameCatalog.titleKey(game))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                let uid: String?
                if case .loggedIn(let profile) = environment.session.state {
                    uid = profile.uid
                } else {
                    uid = nil
                }
                let viewModel = GameViewModel(api: environment.api, game: game, selfUid: uid)
                model = viewModel
                viewModel.start()
            }
        }
        .onDisappear { model?.stop() }
    }

    private func screen(_ model: GameViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let error = model.error, model.state == nil {
                    LoveErrorView(message: error) {
                        Task { await model.retry() }
                    }
                } else if model.state == nil {
                    LoveLoadingView()
                        .frame(height: 260)
                } else {
                    header(model)
                    if let banner = model.errorBanner {
                        LoveErrorBanner(message: banner)
                    }
                    phaseBanner(model)
                    board(model)
                    if model.state?.phase != "finished" {
                        actionBar(model)
                    }
                }
            }
            .padding(16)
        }
        .overlay {
            floatingEmotes(model)
        }
        .overlay(alignment: .top) {
            toastView(model)
        }
    }

    // MARK: Header

    private func header(_ model: GameViewModel) -> some View {
        LoveSoftCard {
            VStack(spacing: 10) {
                HStack(alignment: .top, spacing: 10) {
                    playerCard(model, player: model.blackPlayer, color: "black")
                    VStack(spacing: 4) {
                        if model.showScores {
                            Text("\(model.state?.blackScore ?? 0) : \(model.state?.whiteScore ?? 0)")
                                .font(.title3.weight(.bold))
                                .foregroundStyle(LoveTheme.text)
                            Text("m5a.board.score")
                                .font(.caption2)
                                .foregroundStyle(LoveTheme.secondaryText)
                        } else {
                            Text("m5a.board.moves \(model.state?.moveCount ?? 0)")
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(LoveTheme.text)
                            Image(systemName: "heart.fill")
                                .font(.caption)
                                .foregroundStyle(LoveTheme.pink)
                        }
                        turnLabel(model)
                            .font(.caption.weight(.semibold))
                            .multilineTextAlignment(.center)
                            .lineLimit(2)
                    }
                    .frame(maxWidth: .infinity)
                    playerCard(model, player: model.whitePlayer, color: "white")
                }
                if let myColor = model.myColor {
                    let key: String.LocalizationValue =
                        myColor == "black" ? "m5a.board.you.black" : "m5a.board.you.white"
                    LovePill(
                        text: String(localized: key),
                        tint: LoveTheme.primaryAccessible
                    )
                }
            }
        }
    }

    private func playerCard(
        _ model: GameViewModel,
        player: GameDTOs.GamePlayer?,
        color: String
    ) -> some View {
        let isTurn = model.state?.phase == "playing" && model.state?.turn == color
        let online = player?.online ?? false
        return VStack(spacing: 6) {
            Circle()
                .fill(color == "black" ? Color.black : Color.white)
                .overlay(Circle().stroke(LoveTheme.outline, lineWidth: 1.5))
                .frame(width: 20, height: 20)
            Text(player?.nickname ?? String(localized: "m5a.board.player"))
                .font(.footnote.weight(.semibold))
                .foregroundStyle(LoveTheme.text)
                .lineLimit(1)
            HStack(spacing: 3) {
                Circle()
                    .fill(online ? LoveTheme.mint : LoveTheme.secondaryText)
                    .frame(width: 5, height: 5)
                (online ? Text("m5a.board.online") : Text("m5a.board.offline"))
                    .font(.caption2)
                    .foregroundStyle(LoveTheme.secondaryText)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(
            isTurn
                ? AnyShapeStyle(LoveTheme.primaryAccessible.opacity(0.1))
                : AnyShapeStyle(Color.clear)
        )
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(
                    isTurn ? LoveTheme.primaryAccessible.opacity(0.6) : LoveTheme.outline,
                    lineWidth: 1
                )
        )
    }

    @ViewBuilder
    private func turnLabel(_ model: GameViewModel) -> some View {
        if model.state?.phase == "playing", let turn = model.state?.turn {
            if model.isMyTurn {
                Text("m5a.board.my.turn")
                    .foregroundStyle(LoveTheme.mint)
            } else {
                let nickname = turn == "black"
                    ? model.blackPlayer?.nickname
                    : model.whitePlayer?.nickname
                Text("m5a.board.their.turn \(nickname ?? String(localized: "m5a.board.player"))")
                    .foregroundStyle(LoveTheme.secondaryText)
            }
        } else if model.state?.phase == "waiting" {
            Text("m5a.board.waiting")
                .foregroundStyle(LoveTheme.secondaryText)
        }
    }

    // MARK: Phase banners

    @ViewBuilder
    private func phaseBanner(_ model: GameViewModel) -> some View {
        if let state = model.state {
            switch state.phase {
            case "waiting":
                LoveSoftCard {
                    HStack(spacing: 8) {
                        Image(systemName: "hourglass")
                            .foregroundStyle(LoveTheme.peach)
                        Text("m5a.board.waiting")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText)
                        Spacer()
                    }
                }
            case "finished":
                LoveSoftCard {
                    VStack(spacing: 10) {
                        Text(resultText(model, state))
                            .font(.headline)
                            .foregroundStyle(LoveTheme.primaryAccessible)
                        if let reason = state.endReason {
                            LovePill(text: GameText.endReason(reason), tint: LoveTheme.lavender)
                        }
                        LovePrimaryButton(titleKey: "m5a.action.again") {
                            model.newGame()
                        }
                    }
                }
            default:
                EmptyView()
            }
        }
    }

    private func resultText(_ model: GameViewModel, _ state: GameDTOs.GameState) -> String {
        guard let winner = state.winner, winner != "draw" else {
            return String(localized: "m5a.result.draw")
        }
        let winnerUid = winner == "black" ? state.blackUid : state.whiteUid
        if let selfUid = model.selfUid, let winnerUid {
            if winnerUid == selfUid {
                return String(localized: "m5a.result.you.win")
            }
            return String(localized: "m5a.result.you.lose")
        }
        let nickname = winner == "black"
            ? (model.blackPlayer?.nickname ?? "")
            : (model.whitePlayer?.nickname ?? "")
        return String(localized: "m5a.result.winner \(nickname)")
    }

    // MARK: Board

    @ViewBuilder
    private func board(_ model: GameViewModel) -> some View {
        switch game {
        case "tictactoe":
            TicTacToeBoard(state: model.state, enabled: model.canInteract) { x, y in
                model.play(x: x, y: y)
            }
        case "reversi":
            ReversiBoard(state: model.state, enabled: model.canInteract) { x, y in
                model.play(x: x, y: y)
            }
        case "memory":
            MemoryBoard(state: model.state, enabled: model.canInteract) { x, y in
                model.play(x: x, y: y)
            }
        case "linklink":
            LinkLinkBoard(state: model.state, enabled: model.canInteract) { x, y in
                model.play(x: x, y: y)
            }
        default:
            GomokuBoard(state: model.state, enabled: model.canInteract) { x, y in
                model.play(x: x, y: y)
            }
        }
    }

    // MARK: Actions

    private func actionBar(_ model: GameViewModel) -> some View {
        VStack(spacing: 10) {
            HStack(spacing: 10) {
                LoveSecondaryButton(titleKey: "m5a.action.undo") {
                    model.requestUndo()
                }
                LoveSecondaryButton(titleKey: "m5a.action.surrender") {
                    model.surrender()
                }
            }
            LovePrimaryButton(titleKey: "m5a.action.new.game") {
                model.newGame()
            }
            emoteRow(model)
        }
    }

    private func emoteRow(_ model: GameViewModel) -> some View {
        VStack(spacing: 6) {
            Text("m5a.emote")
                .font(.caption.weight(.medium))
                .foregroundStyle(LoveTheme.secondaryText)
            HStack(spacing: 4) {
                ForEach(GameCatalog.emotes, id: \.self) { emote in
                    Button {
                        model.sendEmote(emote)
                    } label: {
                        Text(emote)
                            .font(.title3)
                            .frame(width: 36, height: 36)
                            .background(LoveTheme.surface, in: Circle())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: Overlays

    private func floatingEmotes(_ model: GameViewModel) -> some View {
        GeometryReader { geo in
            ForEach(model.emotes) { item in
                FloatingEmoteBubble(item: item, size: geo.size)
            }
        }
        .allowsHitTesting(false)
    }

    private func toastView(_ model: GameViewModel) -> some View {
        Group {
            if let toast = model.toast {
                Text(toast)
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(.black.opacity(0.75), in: Capsule())
                    .padding(.top, 6)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        .animation(.easeOut(duration: 0.2), value: model.toast)
    }
}

// MARK: - Floating emote

private struct FloatingEmoteBubble: View {
    let item: GameViewModel.FloatingEmote
    let size: CGSize
    @State private var risen = false

    var body: some View {
        VStack(spacing: 4) {
            Text(item.emote)
                .font(.system(size: 44))
            Text(item.fromNickname)
                .font(.caption2.weight(.medium))
                .foregroundStyle(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(.black.opacity(0.45), in: Capsule())
        }
        .position(
            x: size.width * item.xRatio,
            y: size.height * (risen ? 0.18 : 0.85)
        )
        .opacity(risen ? 0.1 : 1)
        .onAppear {
            withAnimation(.easeOut(duration: 2.2)) { risen = true }
        }
        .allowsHitTesting(false)
    }
}

// MARK: - Gomoku board (15×15 line board, Canvas-rendered)

private struct GomokuBoard: View {
    let state: GameDTOs.GameState?
    let enabled: Bool
    let onPlay: (Int, Int) -> Void

    private var cols: Int {
        if let cols = state?.cols { return cols }
        if let size = state?.size { return size }
        return 15
    }

    private var rows: Int {
        if let rows = state?.rows { return rows }
        if let size = state?.size { return size }
        return 15
    }

    private var cells: [Int] { state?.cells ?? [] }

    /// Shared grid math so the Canvas painter and the tap handler agree.
    private struct Metrics {
        let pad: CGFloat
        let stepX: CGFloat
        let stepY: CGFloat

        init(size: CGSize, cols: Int, rows: Int) {
            pad = min(size.width, size.height) / CGFloat(max(cols, rows)) * 0.5
            stepX = (size.width - pad * 2) / CGFloat(max(cols - 1, 1))
            stepY = (size.height - pad * 2) / CGFloat(max(rows - 1, 1))
        }

        func point(_ x: Int, _ y: Int) -> CGPoint {
            CGPoint(x: pad + CGFloat(x) * stepX, y: pad + CGFloat(y) * stepY)
        }
    }

    var body: some View {
        GeometryReader { geo in
            Canvas { context, size in
                drawBoard(&context, size: size)
            }
            .contentShape(Rectangle())
            .onTapGesture { location in
                handleTap(location, in: geo.size)
            }
        }
        .aspectRatio(CGFloat(cols) / CGFloat(rows), contentMode: .fit)
        .frame(maxWidth: 340)
        .frame(maxWidth: .infinity)
        .background(Color(red: 0.95, green: 0.88, blue: 0.78))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(LoveTheme.outline, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.06), radius: 8, y: 3)
    }

    private func drawBoard(_ context: inout GraphicsContext, size: CGSize) {
        let metrics = Metrics(size: size, cols: cols, rows: rows)
        let lineColor = Color(red: 0.55, green: 0.42, blue: 0.30)

        var grid = Path()
        for i in 0..<cols {
            grid.move(to: metrics.point(i, 0))
            grid.addLine(to: metrics.point(i, rows - 1))
        }
        for j in 0..<rows {
            grid.move(to: metrics.point(0, j))
            grid.addLine(to: metrics.point(cols - 1, j))
        }
        context.stroke(grid, with: .color(lineColor), lineWidth: 1)

        // Star points (five on a standard 15×15 board).
        if cols == 15 && rows == 15 {
            for point in [(3, 3), (3, 11), (11, 3), (11, 11), (7, 7)] {
                let center = metrics.point(point.0, point.1)
                let radius = min(metrics.stepX, metrics.stepY) * 0.09
                context.fill(
                    Path(ellipseIn: CGRect(
                        x: center.x - radius,
                        y: center.y - radius,
                        width: radius * 2,
                        height: radius * 2
                    )),
                    with: .color(lineColor)
                )
            }
        }

        let radius = min(metrics.stepX, metrics.stepY) * 0.46
        for (index, value) in cells.enumerated() where value != 0 {
            let center = metrics.point(index % cols, index / cols)
            let stone = Path(ellipseIn: CGRect(
                x: center.x - radius,
                y: center.y - radius,
                width: radius * 2,
                height: radius * 2
            ))
            context.fill(stone, with: .color(value == 1 ? .black : .white))
            context.stroke(stone, with: .color(Color(white: 0.35, opacity: 0.6)), lineWidth: 1)
        }

        // Winning line, drawn over the stones.
        if let line = state?.winLine, line.count >= 2,
           let first = line.first, let last = line.last,
           first.count >= 2, last.count >= 2 {
            var winPath = Path()
            winPath.move(to: metrics.point(first[0], first[1]))
            winPath.addLine(to: metrics.point(last[0], last[1]))
            context.stroke(
                winPath,
                with: .color(LoveTheme.rose.opacity(0.9)),
                style: StrokeStyle(lineWidth: 5, lineCap: .round)
            )
        }

        if let last = state?.lastMove {
            let center = metrics.point(last.x, last.y)
            context.stroke(
                Path(ellipseIn: CGRect(
                    x: center.x - radius,
                    y: center.y - radius,
                    width: radius * 2,
                    height: radius * 2
                )),
                with: .color(LoveTheme.rose),
                lineWidth: 2
            )
        }
    }

    private func handleTap(_ location: CGPoint, in size: CGSize) {
        guard enabled else { return }
        let metrics = Metrics(size: size, cols: cols, rows: rows)
        let x = Int(((location.x - metrics.pad) / metrics.stepX).rounded())
        let y = Int(((location.y - metrics.pad) / metrics.stepY).rounded())
        guard x >= 0, x < cols, y >= 0, y < rows else { return }
        let index = y * cols + x
        guard index < cells.count, cells[index] == 0 else { return }
        onPlay(x, y)
    }
}

// MARK: - Tic-tac-toe board (3×3)

private struct TicTacToeBoard: View {
    let state: GameDTOs.GameState?
    let enabled: Bool
    let onPlay: (Int, Int) -> Void

    private var cells: [Int] { state?.cells ?? [] }

    private func value(at index: Int) -> Int {
        index < cells.count ? cells[index] : 0
    }

    var body: some View {
        ZStack {
            LazyVGrid(
                columns: Array(repeating: GridItem(.flexible(), spacing: 6), count: 3),
                spacing: 6
            ) {
                ForEach(0..<9, id: \.self) { index in
                    cell(index)
                }
            }
            winLineOverlay
        }
        .aspectRatio(1, contentMode: .fit)
        .frame(maxWidth: 300)
        .frame(maxWidth: .infinity)
    }

    private func cell(_ index: Int) -> some View {
        let value = value(at: index)
        return Button {
            onPlay(index % 3, index / 3)
        } label: {
            ZStack {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(LoveTheme.surface)
                if value == 1 {
                    Image(systemName: "xmark")
                        .font(.system(size: 38, weight: .bold))
                        .foregroundStyle(LoveTheme.rose)
                } else if value == 2 {
                    Image(systemName: "circle")
                        .font(.system(size: 34, weight: .semibold))
                        .foregroundStyle(LoveTheme.lavender)
                }
            }
            .aspectRatio(1, contentMode: .fit)
        }
        .buttonStyle(.plain)
        .disabled(!enabled || value != 0)
    }

    @ViewBuilder
    private var winLineOverlay: some View {
        if let line = state?.winLine, line.count >= 2,
           let first = line.first, let last = line.last,
           first.count >= 2, last.count >= 2 {
            Canvas { context, size in
                let step = size.width / 3
                var path = Path()
                path.move(to: CGPoint(
                    x: (CGFloat(first[0]) + 0.5) * step,
                    y: (CGFloat(first[1]) + 0.5) * step
                ))
                path.addLine(to: CGPoint(
                    x: (CGFloat(last[0]) + 0.5) * step,
                    y: (CGFloat(last[1]) + 0.5) * step
                ))
                context.stroke(
                    path,
                    with: .color(LoveTheme.rose),
                    style: StrokeStyle(lineWidth: 6, lineCap: .round)
                )
            }
            .allowsHitTesting(false)
        }
    }
}

// MARK: - Reversi board (8×8)

private struct ReversiBoard: View {
    let state: GameDTOs.GameState?
    let enabled: Bool
    let onPlay: (Int, Int) -> Void

    private var cells: [Int] { state?.cells ?? [] }

    private var legal: Set<String> {
        var points = Set<String>()
        for move in state?.legalMoves ?? [] where move.count >= 2 {
            points.insert("\(move[0]),\(move[1])")
        }
        return points
    }

    var body: some View {
        LazyVGrid(
            columns: Array(repeating: GridItem(.flexible(), spacing: 2), count: 8),
            spacing: 2
        ) {
            ForEach(0..<64, id: \.self) { index in
                cell(index)
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .frame(maxWidth: 340)
        .frame(maxWidth: .infinity)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }

    private func cell(_ index: Int) -> some View {
        let x = index % 8
        let y = index / 8
        let value = index < cells.count ? cells[index] : 0
        let isLegal = legal.contains("\(x),\(y)")
        // Without a legal-move list the engine still validates server-side,
        // so fall back to allowing taps on empty cells.
        let allowTap = enabled && (legal.isEmpty ? value == 0 : isLegal)
        return Button {
            onPlay(x, y)
        } label: {
            ZStack {
                Rectangle()
                    .fill(Color(red: 0.16, green: 0.45, blue: 0.32))
                if value == 1 {
                    Circle()
                        .fill(Color.black)
                        .padding(4)
                        .overlay(Circle().stroke(.white.opacity(0.45), lineWidth: 1).padding(4))
                } else if value == 2 {
                    Circle()
                        .fill(Color.white)
                        .padding(4)
                } else if isLegal {
                    Circle()
                        .fill(Color.white.opacity(0.55))
                        .frame(width: 10, height: 10)
                }
            }
            .aspectRatio(1, contentMode: .fit)
        }
        .buttonStyle(.plain)
        .disabled(!allowTap)
    }
}

// MARK: - Memory board (4×4 cards)

private struct MemoryBoard: View {
    let state: GameDTOs.GameState?
    let enabled: Bool
    let onPlay: (Int, Int) -> Void

    private var tiles: [Int] { state?.tiles ?? [] }
    private var cardStates: [Int] { state?.states ?? [] }
    private var icons: [String] { state?.icons ?? [] }

    private var cols: Int {
        if let cols = state?.cols { return cols }
        if let size = state?.size { return size }
        return 4
    }

    private var rows: Int {
        if let rows = state?.rows { return rows }
        if let size = state?.size { return size }
        return 4
    }

    var body: some View {
        LazyVGrid(
            columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: cols),
            spacing: 8
        ) {
            ForEach(0..<(cols * rows), id: \.self) { index in
                card(index)
            }
        }
        .aspectRatio(CGFloat(cols) / CGFloat(rows), contentMode: .fit)
        .frame(maxWidth: 320)
        .frame(maxWidth: .infinity)
    }

    private func card(_ index: Int) -> some View {
        let cardState = index < cardStates.count ? cardStates[index] : 0
        let iconIndex = index < tiles.count ? tiles[index] : -1
        let icon = iconIndex >= 0 && iconIndex < icons.count ? icons[iconIndex] : "❔"
        return Button {
            onPlay(index % cols, index / cols)
        } label: {
            ZStack {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(
                        cardState == 2
                            ? AnyShapeStyle(LoveTheme.surface.opacity(0.55))
                            : AnyShapeStyle(LoveTheme.gradient)
                    )
                if cardState == 0 {
                    Image(systemName: "heart.fill")
                        .font(.title2)
                        .foregroundStyle(.white.opacity(0.85))
                } else {
                    Text(icon)
                        .font(.system(size: 30))
                        .opacity(cardState == 2 ? 0.35 : 1)
                }
            }
            .aspectRatio(1, contentMode: .fit)
        }
        .buttonStyle(.plain)
        .disabled(!enabled || cardState == 2)
    }
}

// MARK: - Link-link board (8×6 colored blocks)

private struct LinkLinkBoard: View {
    let state: GameDTOs.GameState?
    let enabled: Bool
    let onPlay: (Int, Int) -> Void

    private var cells: [Int] { state?.cells ?? [] }
    private var pending: [Int] { state?.pending ?? [] }

    private var cols: Int {
        if let cols = state?.cols { return cols }
        return 8
    }

    private var rows: Int {
        if let rows = state?.rows { return rows }
        return 6
    }

    var body: some View {
        LazyVGrid(
            columns: Array(repeating: GridItem(.flexible(), spacing: 4), count: cols),
            spacing: 4
        ) {
            ForEach(0..<(cols * rows), id: \.self) { index in
                block(index)
            }
        }
        .aspectRatio(CGFloat(cols) / CGFloat(rows), contentMode: .fit)
        .frame(maxWidth: 360)
        .frame(maxWidth: .infinity)
    }

    private func blockColor(_ id: Int) -> Color {
        Color(
            hue: Double((id - 1) % 24) / 24.0,
            saturation: 0.62,
            brightness: 0.88
        )
    }

    private func block(_ index: Int) -> some View {
        let x = index % cols
        let y = index / cols
        let id = index < cells.count ? cells[index] : 0
        let isPending = pending.count >= 2 && pending[0] == x && pending[1] == y
        return Button {
            onPlay(x, y)
        } label: {
            ZStack {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(id > 0 ? AnyShapeStyle(blockColor(id)) : AnyShapeStyle(LoveTheme.surface.opacity(0.5)))
                if id > 0 {
                    Text("\(id)")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(.white.opacity(0.9))
                }
            }
            .aspectRatio(1, contentMode: .fit)
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(isPending ? Color.white : Color.clear, lineWidth: 3)
            )
        }
        .buttonStyle(.plain)
        .disabled(!enabled || id == 0)
    }
}
