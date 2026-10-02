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

// MARK: - View model

/// "You draw, I guess" over `WS /cottage/draw/ws`.
///
/// Stroke protocol notes (mirrors the Web client):
/// - segments carry normalized 0...1 coordinates on a 960×600 logical frame;
/// - every STATE broadcast wipes the local canvas by contract — the drawer
///   repaints from its own stroke log and re-pushes a SYNC so the guesser
///   repaints too, and a reconnecting guesser asks via SYNC_REQUEST;
/// - the secret word only ever arrives in the private YOUR_WORD frame.
@MainActor
@Observable
final class DrawGameViewModel {
    struct GuessBubble: Identifiable {
        let fromUid: String?
        let text: String
        let correct: Bool
        let id = UUID()
    }

    struct EmotePop: Identifiable {
        let emote: String
        let id = UUID()
    }

    static let emoteChoices = ["🖌️", "🎨", "❤️", "😘", "😝", "👍", "🤝", "😭", "🎉", "🤔"]

    // MARK: Published state

    private(set) var connected = false
    private(set) var state: GameDTOs.DrawState?
    private(set) var strokes: [GameDTOs.Stroke] = []
    private(set) var guesses: [GuessBubble] = []
    private(set) var emotePops: [EmotePop] = []
    private(set) var myWord: String?
    private(set) var remainingSec = 0
    private(set) var partnerOnline = false
    var toast: String?

    // Brush configuration (drawer side).
    var colorIndex = 0
    var sizeIndex = 1
    var eraserOn = false

    let selfUid: String?

    private var socket: CottageSocket?
    /// Own stroke log — kept even when STATE wipes the render list so the
    /// drawer can repaint itself and re-push a SYNC to the guesser.
    private var myStrokes: [GameDTOs.Stroke] = []
    private var currentSid: String?
    private var lastPoint: (x: Double, y: Double)?
    /// Round identity: every round (and every fresh game) gets a new
    /// `round_started_ms`, so a rematch that restarts at round 1 is still
    /// detected as a new board even though the round number repeats.
    private var lastRoundStartedMs: Int?
    private var timeoutSent = false
    private var outSegs: [GameDTOs.StrokeSeg] = []
    private var flushTask: Task<Void, Never>?
    private var tickerTask: Task<Void, Never>?
    private var toastTask: Task<Void, Never>?
    private var emotePruneTask: Task<Void, Never>?

    init(selfUid: String?) {
        self.selfUid = selfUid
    }

    // MARK: Derived

    var phase: String? { state?.phase }
    var isDrawingPhase: Bool { phase == "drawing" }
    var isRoundEnd: Bool { phase == "round_end" }

    /// The drawer of the current (or just finished) round.
    var isDrawerForRound: Bool {
        guard let selfUid else { return false }
        return state?.drawerUid == selfUid
    }

    /// Only the active drawer may paint, and only while the round runs.
    var canPaint: Bool { isDrawerForRound && isDrawingPhase }

    var myScore: Int {
        guard let selfUid, let scores = state?.scores else { return 0 }
        return scores[selfUid] ?? 0
    }

    var partnerScore: Int {
        guard let scores = state?.scores,
              let other = scores.keys.first(where: { $0 != selfUid })
        else { return 0 }
        return scores[other] ?? 0
    }

    // MARK: Lifecycle

    func start() {
        connectSocket()
        tickerTask?.cancel()
        tickerTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                self.tick()
                try? await Task.sleep(for: .milliseconds(250))
            }
        }
    }

    func stop() {
        socket?.close()
        socket = nil
        tickerTask?.cancel()
        flushTask?.cancel()
        toastTask?.cancel()
        emotePruneTask?.cancel()
    }

    private func connectSocket() {
        let socket = CottageSocket {
            ServerSettings.webSocketURL(path: "/cottage/draw/ws")
        }
        socket.onOpen = { [weak self] in
            guard let self else { return }
            self.connected = true
            // (Re)connect handshake: whoever holds the board answers SYNC.
            self.socket?.send(type: "SYNC_REQUEST")
        }
        socket.onClose = { [weak self] _ in self?.connected = false }
        socket.onFrame = { [weak self] frame in self?.handleFrame(frame) }
        self.socket = socket
        socket.connect()
    }

    // MARK: Round timer

    private func tick() {
        guard isDrawingPhase, let deadline = state?.roundDeadlineMs else { return }
        let remaining = max(0, Int(ceil(Double(deadline - Self.nowMs()) / 1000.0)))
        remainingSec = remaining
        if remaining <= 0, !timeoutSent, connected {
            timeoutSent = true
            socket?.send(type: "ROUND_TIMEOUT")
        }
    }

    private static func nowMs() -> Int {
        Int(Date().timeIntervalSince1970 * 1000)
    }

    // MARK: Socket events

    private func handleFrame(_ frame: CottageSocket.Frame) {
        guard let payload = frame.payload else { return }
        switch frame.type {
        case "STATE", "ROUND_END", "GAME_OVER":
            if let snapshot = StrokeIO.decode(GameDTOs.DrawState.self, fromJSON: payload) {
                applyState(snapshot)
            }
        case "YOUR_WORD":
            myWord = payload["word"] as? String
        case "STROKE":
            if let segs = StrokeIO.decode([GameDTOs.StrokeSeg].self, fromJSON: payload["segs"] ?? []) {
                applyRemoteSegs(segs)
            }
        case "UNDO":
            if let sid = payload["sid"] as? String {
                strokes.removeAll { $0.sid == sid }
                myStrokes.removeAll { $0.sid == sid }
            }
        case "CLEAR":
            strokes = []
            myStrokes = []
        case "SYNC_REQUEST":
            replySyncRequest()
        case "SYNC":
            if let synced = StrokeIO.decode([GameDTOs.Stroke].self, fromJSON: payload["strokes"] ?? []) {
                strokes = synced
            }
        case "GUESS":
            let fromUid = payload["from_uid"] as? String
            let text = payload["text"] as? String ?? ""
            let correct = payload["correct"] as? Bool ?? false
            guesses.append(GuessBubble(fromUid: fromUid, text: text, correct: correct))
            if guesses.count > 30 { guesses.removeFirst(guesses.count - 30) }
        case "EMOTE":
            if let emote = payload["emote"] as? String { popEmote(emote) }
        case "PRESENCE_SNAPSHOT":
            if let online = payload["online"] as? [Any] {
                let uids = online.compactMap { $0 as? String }
                partnerOnline = uids.contains { $0 != selfUid }
            }
        case "PRESENCE":
            if let uid = payload["uid"] as? String, uid != selfUid {
                partnerOnline = payload["online"] as? Bool ?? false
            }
        case "ERROR":
            if let message = payload["message"] as? String { showToast(message) }
        default:
            break
        }
    }

    private func applyState(_ snapshot: GameDTOs.DrawState) {
        let newBoard = snapshot.roundStartedMs != lastRoundStartedMs || snapshot.phase == "waiting"
        state = snapshot
        if newBoard {
            // Fresh round (or fresh room): blank canvas + per-round UI.
            lastRoundStartedMs = snapshot.roundStartedMs
            strokes = []
            myStrokes = []
            guesses = []
            myWord = nil
            timeoutSent = false
        } else {
            // Same-round STATE (a guess, a reconnect snapshot…): the protocol
            // wipes local strokes, so the drawer repaints from its own log
            // and re-pushes a SYNC so the guesser repaints as well.
            strokes = []
            if isDrawerForRound, !myStrokes.isEmpty {
                strokes = myStrokes
                sendSync(myStrokes)
            }
        }
    }

    private func replySyncRequest() {
        // Only the active drawer holds the authoritative in-progress board.
        guard canPaint, !myStrokes.isEmpty else { return }
        sendSync(myStrokes)
    }

    private func sendSync(_ payload: [GameDTOs.Stroke]) {
        socket?.send(type: "SYNC", payload: ["strokes": StrokeIO.jsonDicts(from: payload)])
    }

    private func applyRemoteSegs(_ segs: [GameDTOs.StrokeSeg]) {
        for seg in segs {
            if let index = strokes.lastIndex(where: { $0.sid == seg.sid }) {
                strokes[index].segs.append(seg)
            } else {
                strokes.append(GameDTOs.Stroke(sid: seg.sid, segs: [seg]))
            }
        }
    }

    private func popEmote(_ emote: String) {
        emotePops.append(EmotePop(emote: emote))
        if emotePops.count > 6 { emotePops.removeFirst(emotePops.count - 6) }
        emotePruneTask?.cancel()
        emotePruneTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(4))
            guard !Task.isCancelled else { return }
            self?.emotePops.removeAll()
        }
    }

    // MARK: Painting (drawer only)

    func beginStroke(x: Double, y: Double) {
        guard canPaint else { return }
        let sid = UUID().uuidString
        currentSid = sid
        lastPoint = (x, y)
        recordSeg(GameDTOs.StrokeSeg(
            sid: sid, x0: x, y0: y, x1: x, y1: y,
            color: brushHex, size: brushSize, eraser: eraserOn ? true : nil
        ))
    }

    func extendStroke(x: Double, y: Double) {
        guard canPaint, let sid = currentSid, let last = lastPoint else { return }
        guard abs(x - last.x) > 0.0015 || abs(y - last.y) > 0.0015 else { return }
        recordSeg(GameDTOs.StrokeSeg(
            sid: sid, x0: last.x, y0: last.y, x1: x, y1: y,
            color: brushHex, size: brushSize, eraser: eraserOn ? true : nil
        ))
        lastPoint = (x, y)
    }

    func endStroke() {
        currentSid = nil
        lastPoint = nil
        flushPendingSegs()
    }

    private var brushHex: String {
        let index = min(max(colorIndex, 0), M5BPalette.hexes.count - 1)
        return eraserOn ? "#FFFFFF" : M5BPalette.hexes[index]
    }

    private var brushSize: Double {
        let index = min(max(sizeIndex, 0), M5BPalette.sizes.count - 1)
        return M5BPalette.sizes[index]
    }

    private func recordSeg(_ seg: GameDTOs.StrokeSeg) {
        if let index = strokes.lastIndex(where: { $0.sid == seg.sid }) {
            strokes[index].segs.append(seg)
        } else {
            strokes.append(GameDTOs.Stroke(sid: seg.sid, segs: [seg]))
        }
        if let index = myStrokes.lastIndex(where: { $0.sid == seg.sid }) {
            myStrokes[index].segs.append(seg)
        } else {
            myStrokes.append(GameDTOs.Stroke(sid: seg.sid, segs: [seg]))
        }
        outSegs.append(seg)
        scheduleFlush()
    }

    /// Batches segments into ~one STROKE frame per 60 ms (like the Web client
    /// batching on animation frames) instead of one frame per finger move.
    private func scheduleFlush() {
        guard flushTask == nil else { return }
        flushTask = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(60))
            guard let self, !Task.isCancelled else { return }
            self.flushPendingSegs()
        }
    }

    private func flushPendingSegs() {
        flushTask = nil
        guard !outSegs.isEmpty else { return }
        let segs = outSegs
        outSegs = []
        socket?.send(type: "STROKE", payload: ["segs": StrokeIO.jsonDicts(from: segs)])
    }

    func undoMineStroke() {
        guard canPaint, let last = myStrokes.last else { return }
        myStrokes.removeLast()
        strokes.removeAll { $0.sid == last.sid }
        socket?.send(type: "UNDO", payload: ["sid": last.sid])
    }

    func clearBoard() {
        guard canPaint else { return }
        strokes = []
        myStrokes = []
        socket?.send(type: "CLEAR")
    }

    // MARK: Game actions

    func sendGuess(_ raw: String) {
        let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, isDrawingPhase, !isDrawerForRound else { return }
        socket?.send(type: "GUESS", payload: ["text": String(text.prefix(50))])
    }

    func sendEmote(_ emote: String) {
        socket?.send(type: "EMOTE", payload: ["emote": emote])
    }

    func newGame() {
        socket?.send(type: "NEW_GAME")
    }

    func nextRound() {
        socket?.send(type: "NEXT_ROUND")
    }

    func endGame() {
        socket?.send(type: "END_GAME")
    }

    // MARK: Toast

    func showToast(_ text: String) {
        toast = text
        toastTask?.cancel()
        toastTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(4))
            guard !Task.isCancelled else { return }
            self?.toast = nil
        }
    }
}

// MARK: - View

struct DrawGameView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: DrawGameViewModel?
    @State private var guessDraft = ""

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("m5b.draw.title")
        .navigationBarTitleDisplayMode(.inline)
        .overlay(alignment: .top) { StrokeToastBanner(toast: model?.toast) }
        .onAppear {
            if model == nil {
                let uid: String?
                if case .loggedIn(let profile) = environment.session.state {
                    uid = profile.uid
                } else {
                    uid = nil
                }
                let viewModel = DrawGameViewModel(selfUid: uid)
                model = viewModel
                viewModel.start()
            }
        }
        .onDisappear { model?.stop() }
    }

    private func content(_ model: DrawGameViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                headerCard(model)
                wordCard(model)
                canvasCard(model)
                toolsCard(model)
                guessBar(model)
                controls(model)
                emoteBar(model)
                guessFeed(model)
            }
            .padding(16)
        }
    }

    // MARK: Scoreboard

    private func headerCard(_ model: DrawGameViewModel) -> some View {
        LoveSoftCard {
            HStack(alignment: .center) {
                VStack(spacing: 2) {
                    Text(roleKey(model))
                        .font(.caption2.weight(.medium))
                        .foregroundStyle(LoveTheme.secondaryText)
                    Text("\(model.myScore)")
                        .font(.title2.weight(.bold))
                        .foregroundStyle(LoveTheme.text)
                }
                .frame(maxWidth: .infinity)

                VStack(spacing: 4) {
                    if let round = model.state?.round, let total = model.state?.totalRounds {
                        Text("m5b.draw.round \(round) \(total)")
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    if model.isDrawingPhase {
                        Text("⏱ \(model.remainingSec)s")
                            .font(.headline.weight(.bold))
                            .foregroundStyle(
                                model.remainingSec <= 10 ? LoveTheme.rose : LoveTheme.primaryAccessible
                            )
                    } else {
                        LovePill(text: phaseLabel(model), tint: LoveTheme.lavender)
                    }
                }
                .frame(maxWidth: .infinity)

                VStack(spacing: 2) {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(model.partnerOnline ? LoveTheme.mint : LoveTheme.secondaryText)
                            .frame(width: 6, height: 6)
                        Text("m5b.draw.partner")
                            .font(.caption2.weight(.medium))
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    Text("\(model.partnerScore)")
                        .font(.title2.weight(.bold))
                        .foregroundStyle(LoveTheme.text)
                }
                .frame(maxWidth: .infinity)
            }
        }
    }

    private func roleKey(_ model: DrawGameViewModel) -> LocalizedStringKey {
        guard model.isDrawingPhase else { return "m5b.draw.me" }
        return model.isDrawerForRound ? "m5b.draw.youDraw" : "m5b.draw.youGuess"
    }

    private func phaseLabel(_ model: DrawGameViewModel) -> String {
        switch model.phase {
        case "drawing": return String(localized: "m5b.draw.phase.drawing")
        case "round_end": return String(localized: "m5b.draw.phase.roundEnd")
        case "finished": return String(localized: "m5b.draw.phase.finished")
        default: return String(localized: "m5b.draw.phase.waiting")
        }
    }

    // MARK: Word line / round result

    @ViewBuilder
    private func wordCard(_ model: DrawGameViewModel) -> some View {
        switch model.phase {
        case "drawing":
            LoveSoftCard {
                HStack(spacing: 10) {
                    if model.isDrawerForRound {
                        Text("m5b.draw.yourWord")
                            .font(.footnote.weight(.medium))
                            .foregroundStyle(LoveTheme.secondaryText)
                        if let word = model.myWord {
                            Text(word)
                                .font(.headline.weight(.bold))
                                .foregroundStyle(LoveTheme.rose)
                        } else {
                            ProgressView().tint(LoveTheme.primaryAccessible)
                        }
                    } else {
                        Text("m5b.draw.maskHint")
                            .font(.footnote.weight(.medium))
                            .foregroundStyle(LoveTheme.secondaryText)
                        Text(model.state?.wordMask ?? "")
                            .font(.system(.title3, design: .monospaced).weight(.bold))
                            .kerning(3)
                            .foregroundStyle(LoveTheme.primaryAccessible)
                    }
                    Spacer(minLength: 0)
                }
            }
        case "round_end":
            LoveSoftCard {
                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 8) {
                        Text("m5b.draw.answerIs")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText)
                        Text(model.state?.revealedWord ?? "")
                            .font(.headline.weight(.bold))
                            .foregroundStyle(LoveTheme.rose)
                    }
                    if let winner = model.state?.roundWinnerUid {
                        Text(
                            winner == model.selfUid
                                ? "m5b.draw.roundWinnerYou"
                                : "m5b.draw.roundWinnerPartner"
                        )
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(LoveTheme.mint)
                    } else {
                        Text("m5b.draw.nobody")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                }
            }
        case "finished":
            LoveSoftCard {
                VStack(alignment: .leading, spacing: 6) {
                    Text(finishedHeadline(model))
                        .font(.headline.weight(.bold))
                        .foregroundStyle(LoveTheme.text)
                    HStack(spacing: 6) {
                        Text("m5b.draw.finalScore")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText)
                        Text("\(model.myScore) : \(model.partnerScore)")
                            .font(.title3.weight(.bold))
                            .foregroundStyle(LoveTheme.primaryAccessible)
                    }
                }
            }
        default:
            LoveSoftCard {
                Text("m5b.draw.waitingHint")
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
            }
        }
    }

    private func finishedHeadline(_ model: DrawGameViewModel) -> LocalizedStringKey {
        guard let winner = model.state?.winnerUid else { return "m5b.draw.finalDraw" }
        return winner == model.selfUid ? "m5b.draw.finalYouWin" : "m5b.draw.finalPartnerWin"
    }

    // MARK: Canvas

    private func canvasCard(_ model: DrawGameViewModel) -> some View {
        StrokeBoard(
            strokes: model.strokes,
            drawable: model.canPaint,
            hintKey: (model.isDrawingPhase && !model.canPaint) ? "m5b.draw.readonlyHint" : nil,
            onBegin: { x, y in model.beginStroke(x: x, y: y) },
            onMove: { x, y in model.extendStroke(x: x, y: y) },
            onEnd: { model.endStroke() }
        )
        .overlay(alignment: .bottomTrailing) {
            // Incoming emotes float over the artwork for a few seconds.
            VStack(alignment: .trailing, spacing: 4) {
                ForEach(model.emotePops) { pop in
                    Text(pop.emote)
                        .font(.title2)
                }
            }
            .padding(10)
            .allowsHitTesting(false)
        }
    }

    // MARK: Drawer tools

    @ViewBuilder
    private func toolsCard(_ model: DrawGameViewModel) -> some View {
        if model.canPaint {
            LoveSoftCard {
                @Bindable var model = model
                PaintToolbar(
                    colorIndex: $model.colorIndex,
                    sizeIndex: $model.sizeIndex,
                    eraserOn: $model.eraserOn,
                    onUndo: { model.undoMineStroke() },
                    onClear: { model.clearBoard() }
                )
            }
        }
    }

    // MARK: Guesser input

    @ViewBuilder
    private func guessBar(_ model: DrawGameViewModel) -> some View {
        if model.isDrawingPhase, !model.isDrawerForRound {
            HStack(spacing: 8) {
                TextField("m5b.draw.guessPlaceholder", text: $guessDraft)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 11)
                    .background(LoveTheme.surface)
                    .clipShape(Capsule())
                    .overlay(Capsule().stroke(LoveTheme.outline, lineWidth: 1))
                    .submitLabel(.send)
                    .onSubmit { submitGuess(model) }
                Button {
                    submitGuess(model)
                } label: {
                    Image(systemName: "paperplane.fill")
                        .font(.title3)
                        .foregroundStyle(.white)
                        .frame(width: 42, height: 42)
                        .background(LoveTheme.gradient, in: Circle())
                }
                .buttonStyle(.plain)
                .disabled(guessDraft.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
    }

    private func submitGuess(_ model: DrawGameViewModel) {
        let text = guessDraft
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        guessDraft = ""
        model.sendGuess(text)
    }

    // MARK: Controls

    @ViewBuilder
    private func controls(_ model: DrawGameViewModel) -> some View {
        switch model.phase {
        case "drawing", "round_end":
            HStack(spacing: 12) {
                if model.isRoundEnd {
                    LovePrimaryButton(titleKey: "m5b.draw.nextRound", enabled: model.connected) {
                        model.nextRound()
                    }
                }
                LoveSecondaryButton(titleKey: "m5b.draw.endGame") {
                    model.endGame()
                }
                .disabled(!model.connected)
            }
        default:
            // `waiting` → start; `finished` → rematch.
            LovePrimaryButton(
                titleKey: model.phase == "finished" ? "m5b.draw.rematch" : "m5b.draw.newGame",
                enabled: model.connected
            ) {
                model.newGame()
            }
        }
    }

    // MARK: Emotes

    private func emoteBar(_ model: DrawGameViewModel) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 16) {
                ForEach(DrawGameViewModel.emoteChoices, id: \.self) { emote in
                    Button {
                        model.sendEmote(emote)
                    } label: {
                        Text(emote)
                            .font(.title3)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 6)
        }
        .disabled(!model.connected)
    }

    // MARK: Guess feed

    @ViewBuilder
    private func guessFeed(_ model: DrawGameViewModel) -> some View {
        let visible = model.guesses.suffix(12)
        if !visible.isEmpty {
            LoveSoftCard {
                VStack(alignment: .leading, spacing: 6) {
                    Text("m5b.draw.guessFeed")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(LoveTheme.secondaryText)
                    ForEach(Array(visible)) { guess in
                        HStack(spacing: 8) {
                            Text(
                                guess.fromUid == model.selfUid
                                    ? String(localized: "m5b.draw.me")
                                    : String(localized: "m5b.draw.partner")
                            )
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(LoveTheme.lavender)
                            Text(
                                guess.correct
                                    ? String(localized: "m5b.draw.guessedCorrect")
                                    : guess.text
                            )
                            .font(.footnote)
                            .foregroundStyle(guess.correct ? LoveTheme.mint : LoveTheme.text)
                            Spacer(minLength: 0)
                        }
                        .padding(.horizontal, 8)
                        .padding(.vertical, 5)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(
                            guess.correct
                                ? LoveTheme.mint.opacity(0.14)
                                : LoveTheme.background.opacity(0.6),
                            in: RoundedRectangle(cornerRadius: 10, style: .continuous)
                        )
                    }
                }
            }
        }
    }
}
