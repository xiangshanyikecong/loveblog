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
import UIKit

import LoveCore

// MARK: - Shared painting primitives (used by DrawGameView too)

/// Shared brush palette; stroke widths are logical pixels on the 960×600 frame.
enum M5BPalette {
    /// 黑 / 红 / 蓝 / 绿 / 黄 — the eraser paints `#FFFFFF` with `eraser: true`.
    static let hexes = ["#1E293B", "#EF4444", "#3B82F6", "#10B981", "#F59E0B"]
    static let sizes: [Double] = [4, 12, 26]
    static let logicalWidth = 960
    static let logicalHeight = 600
}

/// JSON bridge between Codable stroke values and the `[String: Any]` payloads
/// the `CottageSocket` API speaks.
enum StrokeIO {
    static func jsonDicts<T: Encodable>(from values: [T]) -> [[String: Any]] {
        guard let data = try? JSONEncoder().encode(values),
              let array = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]]
        else { return [] }
        return array
    }

    static func decode<T: Decodable>(_ type: T.Type, fromJSON json: Any) -> T? {
        guard JSONSerialization.isValidJSONObject(json),
              let data = try? JSONSerialization.data(withJSONObject: json)
        else { return nil }
        return try? LoveAPIClient.decode(T.self, from: data)
    }
}

extension UIColor {
    /// Parses a wire `#rrggbb` string (fallback: black).
    convenience init(strokeHex hex: String) {
        let digits = hex.hasPrefix("#") ? String(hex.dropFirst()) : hex
        let value = UInt64(digits, radix: 16) ?? 0
        self.init(hex: UInt32(truncatingIfNeeded: value))
    }
}

extension Color {
    init(strokeHex hex: String) {
        self.init(uiColor: UIColor(strokeHex: hex))
    }
}

/// Normalized-coordinate painting surface on the 960×600 logical frame.
/// Strokes are stored 0...1 and scaled by the actual render size; the line
/// width scales with `size.width / 960` so a `size: 12` segment stays
/// proportional on any screen.
struct StrokeBoard: View {
    var strokes: [GameDTOs.Stroke]
    var drawable = true
    /// Partner pointer in normalized coordinates (relay canvas only).
    var remoteCursor: CGPoint?
    var hintKey: LocalizedStringKey?
    var onBegin: ((Double, Double) -> Void)?
    var onMove: ((Double, Double) -> Void)?
    var onEnd: (() -> Void)?
    var onCursor: ((Double, Double) -> Void)?
    var onCursorLeave: (() -> Void)?

    @State private var strokeActive = false

    private static let logicalSize = CGSize(
        width: M5BPalette.logicalWidth, height: M5BPalette.logicalHeight
    )

    var body: some View {
        GeometryReader { proxy in
            Group {
                if isInteractive {
                    boardContent(proxy.size)
                        .gesture(dragGesture(proxy.size))
                } else {
                    boardContent(proxy.size)
                }
            }
        }
        .aspectRatio(Self.logicalSize.width / Self.logicalSize.height, contentMode: .fit)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(LoveTheme.outline, lineWidth: 1)
        )
    }

    private func boardContent(_ size: CGSize) -> some View {
        ZStack(alignment: .topLeading) {
            canvas
            if let remoteCursor {
                Circle()
                    .fill(LoveTheme.rose.opacity(0.75))
                    .frame(width: 10, height: 10)
                    .position(
                        x: remoteCursor.x * size.width,
                        y: remoteCursor.y * size.height
                    )
                    .allowsHitTesting(false)
            }
            if let hintKey {
                Text(hintKey)
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(.white.opacity(0.85), in: Capsule())
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .allowsHitTesting(false)
            }
        }
        .frame(width: size.width, height: size.height)
        .contentShape(Rectangle())
    }

    private var canvas: some View {
        Canvas { context, size in
            context.fill(Path(CGRect(origin: .zero, size: size)), with: .color(.white))
            let scale = size.width / Self.logicalSize.width
            for stroke in strokes {
                for seg in stroke.segs {
                    Self.draw(seg, in: &context, canvasSize: size, scale: scale)
                }
            }
        }
        .allowsHitTesting(false)
    }

    private var isInteractive: Bool {
        drawable || onCursor != nil || onCursorLeave != nil || onBegin != nil
    }

    private func dragGesture(_ size: CGSize) -> some Gesture {
        DragGesture(minimumDistance: 0, coordinateSpace: .local)
            .onChanged { value in
                let point = Self.normalize(value.location, in: size)
                if drawable {
                    if strokeActive {
                        onMove?(point.x, point.y)
                    } else {
                        strokeActive = true
                        onBegin?(point.x, point.y)
                    }
                }
                onCursor?(point.x, point.y)
            }
            .onEnded { _ in
                if drawable, strokeActive {
                    strokeActive = false
                    onEnd?()
                }
                onCursorLeave?()
            }
    }

    private static func normalize(_ point: CGPoint, in size: CGSize) -> (x: Double, y: Double) {
        let x = size.width > 0 ? min(1, max(0, Double(point.x / size.width))) : 0
        let y = size.height > 0 ? min(1, max(0, Double(point.y / size.height))) : 0
        return (x, y)
    }

    private static func draw(
        _ seg: GameDTOs.StrokeSeg,
        in context: inout GraphicsContext,
        canvasSize: CGSize,
        scale: CGFloat
    ) {
        let p0 = CGPoint(
            x: seg.x0 * Double(canvasSize.width),
            y: seg.y0 * Double(canvasSize.height)
        )
        let p1 = CGPoint(
            x: seg.x1 * Double(canvasSize.width),
            y: seg.y1 * Double(canvasSize.height)
        )
        let width = max(1.5, CGFloat(seg.size) * scale)
        let color = Color(strokeHex: seg.color)
        if abs(p1.x - p0.x) < 0.5, abs(p1.y - p0.y) < 0.5 {
            // Zero-length segments are dots (tap-to-dot).
            let dot = CGRect(
                x: p0.x - width / 2, y: p0.y - width / 2, width: width, height: width
            )
            context.fill(Path(ellipseIn: dot), with: .color(color))
        } else {
            var path = Path()
            path.move(to: p0)
            path.addLine(to: p1)
            context.stroke(
                path,
                with: .color(color),
                style: StrokeStyle(lineWidth: width, lineCap: .round, lineJoin: .round)
            )
        }
    }
}

/// Brush controls shared by the draw game and the relay canvas.
struct PaintToolbar: View {
    @Binding var colorIndex: Int
    @Binding var sizeIndex: Int
    @Binding var eraserOn: Bool
    var onUndo: () -> Void
    var onClear: () -> Void
    /// Extra trailing control (e.g. the canvas "save" button).
    var trailing: AnyView? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                ForEach(Array(M5BPalette.hexes.enumerated()), id: \.offset) { index, hex in
                    Button {
                        colorIndex = index
                        eraserOn = false
                    } label: {
                        Circle()
                            .fill(Color(strokeHex: hex))
                            .frame(width: 24, height: 24)
                            .overlay(
                                Circle().stroke(
                                    index == colorIndex && !eraserOn
                                        ? LoveTheme.text
                                        : LoveTheme.outline,
                                    lineWidth: index == colorIndex && !eraserOn ? 2 : 1
                                )
                            )
                    }
                    .buttonStyle(.plain)
                }
                Spacer(minLength: 0)
                HStack(spacing: 8) {
                    ForEach(Array(M5BPalette.sizes.enumerated()), id: \.offset) { index, _ in
                        Button {
                            sizeIndex = index
                        } label: {
                            Circle()
                                .fill(LoveTheme.text.opacity(index == sizeIndex ? 0.9 : 0.35))
                                .frame(width: CGFloat(6 + index * 5), height: CGFloat(6 + index * 5))
                                .frame(width: 22, height: 22)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            HStack(spacing: 10) {
                Button {
                    eraserOn.toggle()
                } label: {
                    Label("m5b.tool.eraser", systemImage: eraserOn ? "eraser.fill" : "eraser")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(eraserOn ? .white : LoveTheme.primaryAccessible)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 7)
                        .background(
                            eraserOn ? AnyShapeStyle(LoveTheme.gradient) : AnyShapeStyle(LoveTheme.surface),
                            in: Capsule()
                        )
                }
                .buttonStyle(.plain)
                Button {
                    onUndo()
                } label: {
                    Label("m5b.tool.undo", systemImage: "arrow.uturn.backward")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(LoveTheme.primaryAccessible)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 7)
                        .background(LoveTheme.surface, in: Capsule())
                }
                .buttonStyle(.plain)
                Button {
                    onClear()
                } label: {
                    Label("m5b.tool.clear", systemImage: "trash")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(LoveTheme.rose)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 7)
                        .background(LoveTheme.surface, in: Capsule())
                }
                .buttonStyle(.plain)
                Spacer(minLength: 0)
                if let trailing { trailing }
            }
        }
    }
}

/// Compact toast reused by the M5B screens (mirrors the chat toast).
struct StrokeToastBanner: View {
    let toast: String?

    var body: some View {
        Group {
            if let toast {
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
        .animation(.easeOut(duration: 0.2), value: toast)
    }
}

// MARK: - data: URL thumbnails

enum DataURLDecoder {
    /// Decodes an inline `data:image/...;base64,...` artwork thumbnail.
    static func image(fromDataURL dataUrl: String) -> UIImage? {
        guard let comma = dataUrl.firstIndex(of: ","),
              dataUrl[..<comma].hasPrefix("data:image/")
        else { return nil }
        let base64 = String(dataUrl[dataUrl.index(after: comma)...])
        guard let data = Data(base64Encoded: base64) else { return nil }
        return UIImage(data: data)
    }
}

/// Inline-image view for `thumb_data_url` payloads (base64-decoded once).
struct DataURLImageView: View {
    let dataUrl: String?
    var contentMode: SwiftUI.ContentMode = .fill

    @State private var image: UIImage?

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image)
                    .resizable()
                    .aspectRatio(contentMode: contentMode)
            } else {
                Image(systemName: "photo")
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(LoveTheme.outline.opacity(0.3))
            }
        }
        .onAppear { reload() }
        .onChange(of: dataUrl) { _, _ in reload() }
    }

    private func reload() {
        image = dataUrl.flatMap(DataURLDecoder.image(fromDataURL:))
    }
}

// MARK: - Board view model

/// Shared whiteboard over `WS /cottage/canvas/ws` (a pure relay). Both
/// partners paint at once; STROKE/UNDO/CLEAR/CURSOR are relayed live, and a
/// SYNC handshake on (re)connect restores whatever the other side holds.
@MainActor
@Observable
final class CanvasBoardViewModel {
    private(set) var strokes: [GameDTOs.Stroke] = []
    private(set) var remoteCursor: CGPoint?
    private(set) var connected = false
    private(set) var saving = false
    var toast: String?

    // Brush configuration.
    var colorIndex = 0
    var sizeIndex = 1
    var eraserOn = false

    let selfUid: String?

    private let api: LoveAPIClient
    private var socket: CottageSocket?
    private var myStrokes: [GameDTOs.Stroke] = []
    private var currentSid: String?
    private var lastPoint: (x: Double, y: Double)?
    private var outSegs: [GameDTOs.StrokeSeg] = []
    private var flushTask: Task<Void, Never>?
    private var toastTask: Task<Void, Never>?
    private var lastCursorSentMs: Double = 0

    init(api: LoveAPIClient, selfUid: String?) {
        self.api = api
        self.selfUid = selfUid
    }

    // MARK: Lifecycle

    func start() {
        let socket = CottageSocket {
            ServerSettings.webSocketURL(path: "/cottage/canvas/ws")
        }
        socket.onOpen = { [weak self] in
            guard let self else { return }
            self.connected = true
            // Ask the partner for the current board (late joiner handshake).
            self.socket?.send(type: "SYNC_REQUEST")
        }
        socket.onClose = { [weak self] _ in self?.connected = false }
        socket.onFrame = { [weak self] frame in self?.handleFrame(frame) }
        self.socket = socket
        socket.connect()
    }

    func stop() {
        socket?.close()
        socket = nil
        flushTask?.cancel()
        toastTask?.cancel()
    }

    // MARK: Socket events

    private func handleFrame(_ frame: CottageSocket.Frame) {
        guard let payload = frame.payload else { return }
        switch frame.type {
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
        case "CURSOR":
            if payload["leave"] as? Bool == true {
                remoteCursor = nil
            } else if let x = payload["x"] as? Double, let y = payload["y"] as? Double {
                remoteCursor = CGPoint(x: min(1, max(0, x)), y: min(1, max(0, y)))
            }
        case "SYNC_REQUEST":
            // Hand the partner our whole board so they can restore it.
            if !strokes.isEmpty { sendSync(strokes) }
        case "SYNC":
            if let synced = StrokeIO.decode([GameDTOs.Stroke].self, fromJSON: payload["strokes"] ?? []) {
                mergeSync(synced)
            }
        default:
            break
        }
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

    /// Replaces the board with the partner's snapshot, keeping any local
    /// strokes they have not seen yet (e.g. drawn mid-handshake).
    private func mergeSync(_ synced: [GameDTOs.Stroke]) {
        guard !synced.isEmpty else { return }
        let syncedSids = Set(synced.map(\.sid))
        strokes = synced
        for stroke in myStrokes where !syncedSids.contains(stroke.sid) {
            strokes.append(stroke)
        }
    }

    private func sendSync(_ payload: [GameDTOs.Stroke]) {
        socket?.send(type: "SYNC", payload: ["strokes": StrokeIO.jsonDicts(from: payload)])
    }

    // MARK: Painting

    func beginStroke(x: Double, y: Double) {
        let sid = UUID().uuidString
        currentSid = sid
        lastPoint = (x, y)
        recordSeg(GameDTOs.StrokeSeg(
            sid: sid, x0: x, y0: y, x1: x, y1: y,
            color: brushHex, size: brushSize, eraser: eraserOn ? true : nil
        ))
    }

    func extendStroke(x: Double, y: Double) {
        guard let sid = currentSid, let last = lastPoint else { return }
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
        guard let last = myStrokes.last else { return }
        myStrokes.removeLast()
        strokes.removeAll { $0.sid == last.sid }
        socket?.send(type: "UNDO", payload: ["sid": last.sid])
    }

    func clearBoard() {
        strokes = []
        myStrokes = []
        socket?.send(type: "CLEAR")
    }

    // MARK: Partner cursor

    func cursorMoved(x: Double, y: Double) {
        let now = Date().timeIntervalSince1970 * 1000
        guard now - lastCursorSentMs >= 40 else { return }
        lastCursorSentMs = now
        socket?.send(type: "CURSOR", payload: ["x": x, "y": y])
    }

    func cursorLeft() {
        socket?.send(type: "CURSOR", payload: ["leave": true, "x": -1, "y": -1])
    }

    // MARK: Save to gallery

    /// Rasterizes the board to a 960×600 PNG (1x, white paper, round caps).
    func renderImage() -> UIImage {
        let size = CGSize(width: M5BPalette.logicalWidth, height: M5BPalette.logicalHeight)
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let renderer = UIGraphicsImageRenderer(size: size, format: format)
        return renderer.image { rendererContext in
            let cg = rendererContext.cgContext
            cg.setFillColor(UIColor.white.cgColor)
            cg.fill(CGRect(origin: .zero, size: size))
            cg.setLineCap(.round)
            cg.setLineJoin(.round)
            for stroke in strokes {
                for seg in stroke.segs {
                    let x0 = CGFloat(seg.x0) * size.width
                    let y0 = CGFloat(seg.y0) * size.height
                    let x1 = CGFloat(seg.x1) * size.width
                    let y1 = CGFloat(seg.y1) * size.height
                    let width = max(1.5, CGFloat(seg.size))
                    if abs(x1 - x0) < 0.5, abs(y1 - y0) < 0.5 {
                        cg.setFillColor(UIColor(strokeHex: seg.color).cgColor)
                        cg.fillEllipse(
                            in: CGRect(x: x0 - width / 2, y: y0 - width / 2, width: width, height: width)
                        )
                    } else {
                        cg.setStrokeColor(UIColor(strokeHex: seg.color).cgColor)
                        cg.setLineWidth(width)
                        cg.move(to: CGPoint(x: x0, y: y0))
                        cg.addLine(to: CGPoint(x: x1, y: y1))
                        cg.strokePath()
                    }
                }
            }
        }
    }

    func save() async {
        guard !saving else { return }
        guard !strokes.isEmpty else {
            showToast(String(localized: "m5b.canvas.emptyWarn"))
            return
        }
        saving = true
        defer { saving = false }
        let document = GameDTOs.StrokeDocument(
            width: M5BPalette.logicalWidth,
            height: M5BPalette.logicalHeight,
            strokes: strokes
        )
        guard let jsonData = try? JSONEncoder().encode(document),
              let strokesJson = String(data: jsonData, encoding: .utf8),
              let png = renderImage().pngData()
        else {
            showToast(String(localized: "m5b.canvas.saveFailed"))
            return
        }
        let thumb = "data:image/png;base64," + png.base64EncodedString()
        let body = GameDTOs.CanvasSave(
            title: nil,
            strokesJson: strokesJson,
            thumbDataUrl: thumb,
            width: M5BPalette.logicalWidth,
            height: M5BPalette.logicalHeight,
            idempotencyKey: UUID().uuidString
        )
        do {
            _ = try await api.request(
                GameDTOs.CanvasArtwork.self, "POST", "/cottage/canvas/artworks", body: body
            )
            showToast(String(localized: "m5b.canvas.saved"))
        } catch {
            showToast((error as? APIError)?.message ?? String(localized: "m5b.canvas.saveFailed"))
        }
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

// MARK: - Board view

struct CanvasBoardView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: CanvasBoardViewModel?
    @State private var galleryPresented = false

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("m5b.canvas.title")
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
                let viewModel = CanvasBoardViewModel(api: environment.api, selfUid: uid)
                model = viewModel
                viewModel.start()
            }
        }
        .onDisappear { model?.stop() }
        .sheet(isPresented: $galleryPresented) {
            CanvasGallerySheet()
        }
    }

    private func content(_ model: CanvasBoardViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                statusCard(model)
                StrokeBoard(
                    strokes: model.strokes,
                    drawable: true,
                    remoteCursor: model.remoteCursor,
                    onBegin: { x, y in model.beginStroke(x: x, y: y) },
                    onMove: { x, y in model.extendStroke(x: x, y: y) },
                    onEnd: { model.endStroke() },
                    onCursor: { x, y in model.cursorMoved(x: x, y: y) },
                    onCursorLeave: { model.cursorLeft() }
                )
                toolbarCard(model)
                LoveSecondaryButton(titleKey: "m5b.canvas.gallery") {
                    galleryPresented = true
                }
            }
            .padding(16)
        }
    }

    private func statusCard(_ model: CanvasBoardViewModel) -> some View {
        LoveSoftCard {
            HStack(spacing: 8) {
                Circle()
                    .fill(model.connected ? LoveTheme.mint : LoveTheme.secondaryText)
                    .frame(width: 8, height: 8)
                Text("m5b.canvas.hint")
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
                Spacer(minLength: 0)
                if model.connected, model.remoteCursor != nil {
                    Text("m5b.canvas.partnerDrawing")
                        .font(.caption)
                        .foregroundStyle(LoveTheme.rose)
                }
            }
        }
    }

    private func toolbarCard(_ model: CanvasBoardViewModel) -> some View {
        LoveSoftCard {
            @Bindable var model = model
            PaintToolbar(
                colorIndex: $model.colorIndex,
                sizeIndex: $model.sizeIndex,
                eraserOn: $model.eraserOn,
                onUndo: { model.undoMineStroke() },
                onClear: { model.clearBoard() },
                trailing: AnyView(saveButton(model))
            )
        }
    }

    private func saveButton(_ model: CanvasBoardViewModel) -> some View {
        Button {
            Task { await model.save() }
        } label: {
            HStack(spacing: 6) {
                if model.saving {
                    ProgressView().tint(.white)
                } else {
                    Image(systemName: "square.and.arrow.down")
                }
                Text("m5b.canvas.save")
            }
            .font(.footnote.weight(.semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .background(LoveTheme.gradient, in: Capsule())
        }
        .buttonStyle(.plain)
        .disabled(model.saving)
    }
}

// MARK: - Gallery

@MainActor
@Observable
final class CanvasGalleryModel {
    private(set) var items: [GameDTOs.CanvasArtwork] = []
    private(set) var loading = true
    private(set) var loadingMore = false
    private(set) var error: String?
    var toast: String?

    private var page = 1
    private(set) var hasNext = false
    private let api: LoveAPIClient
    private var toastTask: Task<Void, Never>?

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        if items.isEmpty { loading = true }
        do {
            let result = try await api.request(
                GameDTOs.CanvasPage.self, "GET", "/cottage/canvas/artworks",
                query: [
                    URLQueryItem(name: "page", value: "1"),
                    URLQueryItem(name: "page_size", value: "30"),
                ]
            )
            items = result.items
            hasNext = result.hasNext
            page = 1
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? String(localized: "m5b.gallery.loadFailed")
        }
        loading = false
    }

    func loadMore() async {
        guard hasNext, !loadingMore else { return }
        loadingMore = true
        defer { loadingMore = false }
        do {
            let result = try await api.request(
                GameDTOs.CanvasPage.self, "GET", "/cottage/canvas/artworks",
                query: [
                    URLQueryItem(name: "page", value: String(page + 1)),
                    URLQueryItem(name: "page_size", value: "30"),
                ]
            )
            items += result.items
            hasNext = result.hasNext
            page += 1
        } catch {
            showToast((error as? APIError)?.message ?? String(localized: "m5b.gallery.loadFailed"))
        }
    }

    func delete(_ artwork: GameDTOs.CanvasArtwork) async {
        do {
            try await api.requestVoid("DELETE", "/cottage/canvas/artworks/\(artwork.caid)")
            items.removeAll { $0.caid == artwork.caid }
            showToast(String(localized: "m5b.gallery.deleted"))
        } catch {
            showToast((error as? APIError)?.message ?? String(localized: "m5b.gallery.loadFailed"))
        }
    }

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

struct CanvasGallerySheet: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss

    @State private var model: CanvasGalleryModel?

    private struct Selection: Identifiable {
        let caid: String
        var id: String { caid }
    }
    @State private var selection: Selection?

    var body: some View {
        NavigationStack {
            Group {
                if let model {
                    list(model)
                } else {
                    LoveLoadingView()
                }
            }
            .loveScreenBackground()
            .navigationTitle("m5b.gallery.title")
            .navigationBarTitleDisplayMode(.inline)
            .overlay(alignment: .top) { StrokeToastBanner(toast: model?.toast) }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("common.cancel") { dismiss() }
                }
            }
            .onAppear {
                if model == nil {
                    model = CanvasGalleryModel(api: environment.api)
                    Task { await model?.refresh() }
                }
            }
            .refreshable { await model?.refresh() }
            .sheet(item: $selection) { sel in
                ArtworkPlayerSheet(caid: sel.caid) {
                    selection = nil
                    Task { await model?.refresh() }
                }
            }
        }
    }

    @ViewBuilder
    private func list(_ model: CanvasGalleryModel) -> some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                if let error = model.error, model.items.isEmpty {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                        .frame(height: 200)
                } else if model.items.isEmpty {
                    LoveEmptyState(
                        systemImage: "paintbrush.pointed",
                        titleKey: "m5b.gallery.empty",
                        messageKey: "m5b.gallery.empty.hint"
                    )
                    .padding(.top, 40)
                } else {
                    ForEach(model.items) { artwork in
                        row(model, artwork)
                    }
                    if model.hasNext {
                        Button {
                            Task { await model.loadMore() }
                        } label: {
                            if model.loadingMore {
                                ProgressView().tint(LoveTheme.primaryAccessible)
                            } else {
                                Text("m5b.gallery.more")
                                    .font(.footnote.weight(.medium))
                                    .foregroundStyle(LoveTheme.primaryAccessible)
                            }
                        }
                        .padding(.vertical, 6)
                    }
                }
            }
            .padding(16)
        }
    }

    private func row(_ model: CanvasGalleryModel, _ artwork: GameDTOs.CanvasArtwork) -> some View {
        HStack(spacing: 12) {
            Button {
                selection = Selection(caid: artwork.caid)
            } label: {
                HStack(spacing: 12) {
                    DataURLImageView(dataUrl: artwork.thumbDataUrl)
                        .frame(width: 96, height: 60)
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    VStack(alignment: .leading, spacing: 4) {
                        Text(rowTitle(artwork))
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.text)
                        Text("m5b.gallery.strokes \(artwork.strokeCount)")
                            .font(.caption)
                            .foregroundStyle(LoveTheme.secondaryText)
                        Text("\(artwork.authorNickname) · \(Format.date(artwork.createdAt))")
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    Spacer(minLength: 0)
                }
            }
            .buttonStyle(.plain)
            Button {
                Task { await model.delete(artwork) }
            } label: {
                Image(systemName: "trash")
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.rose)
            }
            .buttonStyle(.plain)
        }
        .padding(12)
        .background(LoveTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func rowTitle(_ artwork: GameDTOs.CanvasArtwork) -> String {
        if let title = artwork.title?.trimmingCharacters(in: .whitespacesAndNewlines), !title.isEmpty {
            return title
        }
        return String(localized: "m5b.gallery.untitled")
    }
}

// MARK: - Artwork detail + stroke playback

private struct ArtworkPlayerSheet: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss

    let caid: String
    let onDeleted: () -> Void

    @State private var artwork: GameDTOs.CanvasArtwork?
    @State private var document: GameDTOs.StrokeDocument?
    @State private var visibleStrokes: [GameDTOs.Stroke] = []
    @State private var playbackTimer: Timer?
    @State private var playing = false
    @State private var errorText: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    if let artwork {
                        board(artwork)
                        metaCard(artwork)
                        controls(artwork)
                    } else if let errorText {
                        LoveErrorView(message: errorText) {
                            Task { await load() }
                        }
                    } else {
                        LoveLoadingView()
                            .frame(height: 240)
                    }
                }
                .padding(16)
            }
            .loveScreenBackground()
            .navigationTitle("m5b.gallery.detail")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("common.cancel") { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button(role: .destructive) {
                        Task { await deleteArtwork() }
                    } label: {
                        Image(systemName: "trash")
                            .foregroundStyle(LoveTheme.rose)
                    }
                }
            }
        }
        .task { await load() }
        .onDisappear { playbackTimer?.invalidate() }
    }

    private func board(_ artwork: GameDTOs.CanvasArtwork) -> some View {
        StrokeBoard(
            strokes: visibleStrokes,
            drawable: false
        )
    }

    private func metaCard(_ artwork: GameDTOs.CanvasArtwork) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    Text("m5b.gallery.strokes \(artwork.strokeCount)")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(LoveTheme.secondaryText)
                    Spacer(minLength: 0)
                    Text("\(artwork.authorNickname) · \(Format.date(artwork.createdAt))")
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
            }
        }
    }

    private func controls(_ artwork: GameDTOs.CanvasArtwork) -> some View {
        HStack(spacing: 12) {
            LoveSecondaryButton(titleKey: "m5b.gallery.playback") {
                startPlayback()
            }
            if playing {
                ProgressView()
                    .tint(LoveTheme.primaryAccessible)
            }
            Spacer(minLength: 0)
            Text("m5b.gallery.progress \(visibleStrokes.count) \(artwork.strokeCount)")
                .font(.caption)
                .foregroundStyle(LoveTheme.secondaryText)
        }
    }

    private func load() async {
        do {
            let detail = try await environment.api.request(
                GameDTOs.CanvasArtwork.self, "GET", "/cottage/canvas/artworks/\(caid)"
            )
            artwork = detail
            if let json = detail.strokesJson,
               let data = json.data(using: .utf8),
               let parsed = try? LoveAPIClient.decode(GameDTOs.StrokeDocument.self, from: data) {
                document = parsed
                startPlayback()
            }
        } catch {
            errorText = (error as? APIError)?.message ?? String(localized: "m5b.gallery.loadFailed")
        }
    }

    /// Plays the recorded strokes back in order, one stroke per tick (the
    /// whole clip is capped around 8 s regardless of stroke count).
    private func startPlayback() {
        playbackTimer?.invalidate()
        guard let strokes = document?.strokes else { return }
        visibleStrokes = []
        playing = true
        var index = 0
        let interval = strokes.isEmpty ? 0.1 : min(0.28, max(0.06, 8.0 / Double(strokes.count)))
        playbackTimer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { timer in
            if index >= strokes.count {
                timer.invalidate()
                playing = false
                return
            }
            visibleStrokes.append(strokes[index])
            index += 1
        }
    }

    private func deleteArtwork() async {
        do {
            try await environment.api.requestVoid("DELETE", "/cottage/canvas/artworks/\(caid)")
            onDeleted()
            dismiss()
        } catch {
            errorText = (error as? APIError)?.message ?? String(localized: "m5b.gallery.loadFailed")
        }
    }
}
