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

import CryptoKit
import Observation
import SwiftUI

import LoveCore

// MARK: - Wire bodies (app-local, ISO-8601 dates)

/// `POST /cottage/chat/keys/setup` — `CottageDTOs.ChatKeySetup` has no public
/// initializer, so the body is redeclared here instead of touching LoveCore.
private struct ChatKeySetupBody: Encodable {
    var salt: String
    var kdf = "PBKDF2"
    var kdfHash = "SHA-256"
    var iterations: Int
    var algo = "AES-GCM"
    var verifierIv: String
    var verifierCipher: String
    var verifierHash: String

    enum CodingKeys: String, CodingKey {
        case salt, kdf, iterations, algo
        case kdfHash = "kdf_hash"
        case verifierIv = "verifier_iv"
        case verifierCipher = "verifier_cipher"
        case verifierHash = "verifier_hash"
    }
}

/// `POST /cottage/chat/keys/verify` — unlock proof report.
private struct ChatKeyVerifyBody: Encodable {
    var proofIv: String
    var proofCipher: String

    enum CodingKeys: String, CodingKey {
        case proofIv = "proof_iv"
        case proofCipher = "proof_cipher"
    }
}

/// `POST /cottage/chat/messages` — dates are pre-formatted ISO-8601 strings so
/// the shared JSONEncoder's reference-date encoding can never reach the wire.
private struct ChatMessageBody: Encodable {
    var type = "text"
    var content: String?
    var mediaUrl: String?
    var audioDurationSec: Int?
    var visibleAt: String?
    var replyToMid: String?
    var isEncrypted = false
    var iv: String?
    var ciphertext: String?
    var algo: String?

    enum CodingKeys: String, CodingKey {
        case type, content, iv, ciphertext, algo
        case mediaUrl = "media_url"
        case audioDurationSec = "audio_duration_sec"
        case visibleAt = "visible_at"
        case replyToMid = "reply_to_mid"
        case isEncrypted = "is_encrypted"
    }
}

private struct PinnedQuoteBody: Encodable {
    var mid: String
}

private struct PokeBody: Encodable {
    var kind: String
}

// MARK: - View model

/// E2EE chat: REST history/pagination + realtime socket + shared-passphrase
/// crypto session (the key lives in memory only; cold starts re-unlock,
/// mirroring the Android client).
@MainActor
@Observable
final class ChatViewModel {
    enum E2eeStatus {
        /// Key state not fetched yet — sending is blocked.
        case unknown
        /// No shared passphrase configured (plaintext mode).
        case off
        /// Configured but the local key session is closed.
        case locked
        /// Key derived and held in memory.
        case unlocked
    }

    private(set) var messages: [CottageDTOs.ChatMessage] = []
    private(set) var loading = true
    private(set) var hasMore = false
    private(set) var loadingEarlier = false
    private(set) var sending = false
    private(set) var connected = false
    private(set) var partnerNickname = ""
    private(set) var partnerOnline = false
    private(set) var partnerTyping = false
    private(set) var e2eeStatus: E2eeStatus = .unknown
    private(set) var keyWorking = false

    var error: String?
    var toast: String?

    let selfUid: String?

    /// mid → decrypted plaintext for encrypted messages (memory only).
    private var decrypted: [String: String] = [:]
    private var messageIndex: [String: CottageDTOs.ChatMessage] = [:]
    private var meta: CottageDTOs.ChatKeyMeta?
    private var chatKey: SymmetricKey?
    private var partnerUid: String?
    private var nextBeforeId: Int?
    private var typingActive = false
    private var typingResetTask: Task<Void, Never>?
    private var toastTask: Task<Void, Never>?
    private let api: LoveAPIClient
    private let outbox: OutboxSyncer
    private var socket: CottageSocket?

    private static let iso8601: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    init(api: LoveAPIClient, selfUid: String?, outbox: OutboxSyncer) {
        self.api = api
        self.selfUid = selfUid
        self.outbox = outbox
    }

    // MARK: Lifecycle

    func start() {
        connectSocket()
        Task { await bootstrap() }
    }

    func stop() {
        socket?.close()
        socket = nil
        typingResetTask?.cancel()
        toastTask?.cancel()
    }

    private func connectSocket() {
        let socket = CottageSocket {
            ServerSettings.webSocketURL(path: "/cottage/chat/ws")
        }
        socket.onOpen = { [weak self] in self?.connected = true }
        socket.onClose = { [weak self] _ in self?.connected = false }
        socket.onFrame = { [weak self] frame in self?.handleFrame(frame) }
        self.socket = socket
        socket.connect()
    }

    private func bootstrap() async {
        await loadKeyMeta()
        do {
            let state = try await api.request(
                CottageDTOs.ChatState.self, "GET", "/cottage/chat/state"
            )
            partnerUid = state.partnerUid
            partnerNickname = state.partnerNickname
            partnerOnline = state.partnerOnline
        } catch {
            self.error = Self.describe(error)
        }
        await loadHistory()
        // Mark everything the partner sent before we opened as read.
        try? await api.requestVoid("POST", "/cottage/chat/read")
        loading = false
    }

    // MARK: E2EE key session

    private func loadKeyMeta() async {
        do {
            let meta = try await api.request(
                CottageDTOs.ChatKeyMeta.self, "GET", "/cottage/chat/keys/meta"
            )
            self.meta = meta
            if meta.initialized {
                e2eeStatus = chatKey == nil ? .locked : .unlocked
            } else {
                e2eeStatus = .off
            }
        } catch {
            // Leave `.unknown`: until the state is proven, sending stays
            // blocked — a plaintext message sent right after the partner
            // enables encryption would be rejected by the server forever.
        }
    }

    /// First-time setup: derive a key from the shared passphrase with a fresh
    /// random salt, publish the verifier, keep the key in memory.
    /// Returns nil on success, otherwise a user-facing message.
    func setupEncryption(passphrase: String) async -> String? {
        keyWorking = true
        defer { keyWorking = false }
        let salt = ChatCrypto.randomSaltBase64()
        do {
            let key = try await deriveKeyInBackground(passphrase: passphrase, salt: salt, iterations: ChatCrypto.defaultIterations)
            let verifier = try ChatCrypto.makeVerifier(key: key)
            let body = ChatKeySetupBody(
                salt: salt,
                iterations: ChatCrypto.defaultIterations,
                verifierIv: verifier.ivBase64,
                verifierCipher: verifier.cipherBase64,
                verifierHash: verifier.hashHex
            )
            let meta = try await api.request(
                CottageDTOs.ChatKeyMeta.self, "POST", "/cottage/chat/keys/setup", body: body
            )
            self.meta = meta
            chatKey = key
            e2eeStatus = .unlocked
            emitMessages()
            showToast(String(localized: "cottage.chat.e2ee.setup.done"))
            return nil
        } catch {
            return Self.describe(error)
        }
    }

    /// Unlock: derive from the stored salt/iterations, validate against the
    /// verifier locally, then report a proof to the server (no-op there).
    /// Returns nil on success, otherwise a user-facing message.
    func unlock(passphrase: String) async -> String? {
        guard let meta, meta.initialized,
              let salt = meta.salt, let iterations = meta.iterations,
              let verifierIv = meta.verifierIv, let verifierCipher = meta.verifierCipher
        else {
            return String(localized: "cottage.chat.e2ee.unavailable")
        }
        keyWorking = true
        defer { keyWorking = false }
        do {
            let key = try await deriveKeyInBackground(passphrase: passphrase, salt: salt, iterations: iterations)
            guard ChatCrypto.verifierMatches(
                key: key, verifierIvBase64: verifierIv, verifierCipherBase64: verifierCipher
            ) else {
                return String(localized: "cottage.chat.e2ee.wrong")
            }
            chatKey = key
            e2eeStatus = .unlocked
            emitMessages()
            if let proof = try? ChatCrypto.makeProof(key: key) {
                try? await api.requestVoid(
                    "POST", "/cottage/chat/keys/verify",
                    body: ChatKeyVerifyBody(proofIv: proof.ivBase64, proofCipher: proof.cipherBase64)
                )
            }
            return nil
        } catch {
            return Self.describe(error)
        }
    }

    /// Drop the in-memory key (messages fall back to 🔒 placeholders).
    func lock() {
        chatKey = nil
        decrypted.removeAll()
        if e2eeStatus == .unlocked { e2eeStatus = .locked }
        emitMessages()
    }

    /// PBKDF2 (~210k iterations) runs off the main thread.
    private func deriveKeyInBackground(
        passphrase: String, salt: String, iterations: Int
    ) async throws -> SymmetricKey {
        try await Task.detached(priority: .userInitiated) {
            try ChatCrypto.deriveKey(passphrase: passphrase, saltBase64: salt, iterations: iterations)
        }.value
    }

    // MARK: History

    private func loadHistory() async {
        do {
            let page = try await api.request(
                CottageDTOs.ChatHistory.self, "GET", "/cottage/chat/messages",
                query: [URLQueryItem(name: "limit", value: "30")]
            )
            page.items.forEach { messageIndex[$0.mid] = $0 }
            nextBeforeId = page.nextBeforeId
            hasMore = page.hasMore
            emitMessages()
            error = nil
        } catch {
            self.error = Self.describe(error)
        }
    }

    /// Retry after a first-screen failure (history + state).
    func retryInitial() async {
        await loadHistory()
        if error == nil { loading = false }
    }

    func loadEarlier() async {
        guard !loadingEarlier, hasMore, let before = nextBeforeId else { return }
        loadingEarlier = true
        defer { loadingEarlier = false }
        do {
            let page = try await api.request(
                CottageDTOs.ChatHistory.self, "GET", "/cottage/chat/messages",
                query: [
                    URLQueryItem(name: "before_id", value: String(before)),
                    URLQueryItem(name: "limit", value: "30"),
                ]
            )
            page.items.forEach { messageIndex[$0.mid] = $0 }
            nextBeforeId = page.nextBeforeId
            hasMore = page.hasMore
            emitMessages()
        } catch {
            showToast(Self.describe(error))
        }
    }

    // MARK: Rendering helpers

    /// Plaintext for a bubble: recalled / future / locked-encrypted states
    /// degrade to localized placeholders.
    func displayText(_ message: CottageDTOs.ChatMessage) -> String {
        if message.isRecalled { return String(localized: "cottage.chat.recalled") }
        if message.isEncrypted {
            if let text = decrypted[message.mid] { return text }
            return chatKey == nil
                ? String(localized: "cottage.chat.encrypted.locked")
                : String(localized: "cottage.chat.decrypt.failed")
        }
        return message.content ?? ""
    }

    /// Recall window is enforced server-side; the local check only decides
    /// whether to offer the action (WS echoes drop `can_recall`).
    func canRecall(_ message: CottageDTOs.ChatMessage) -> Bool {
        guard let selfUid, message.senderUid == selfUid, !message.isRecalled else {
            return false
        }
        return message.canRecall || Date().timeIntervalSince(message.createdAt) < 110
    }

    // MARK: Sending

    func send(_ text: String, visibleAt: Date?) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        stopTypingSignalIfNeeded()
        switch e2eeStatus {
        case .unknown:
            // Never enqueue plaintext while the E2EE state is unproven.
            showToast(String(localized: "cottage.chat.e2ee.syncing"))
            Task { await loadKeyMeta() }
            return
        case .locked:
            showToast(String(localized: "cottage.chat.e2ee.locked.hint"))
            return
        case .off, .unlocked:
            break
        }

        var body = ChatMessageBody()
        body.content = trimmed
        if let visibleAt {
            body.visibleAt = Self.iso8601.string(from: visibleAt)
        }
        if case .unlocked = e2eeStatus, let chatKey {
            do {
                let envelope = try ChatCrypto.encryptString(key: chatKey, plaintext: trimmed)
                body.content = nil
                body.isEncrypted = true
                body.iv = envelope.ivBase64
                body.ciphertext = envelope.ciphertextBase64
                body.algo = "AES-GCM"
            } catch {
                showToast(String(localized: "cottage.chat.send.failed"))
                return
            }
        }
        sending = true
        defer { sending = false }
        // One key for the live attempt and any offline replay: replays forward
        // the fully built (possibly E2EE-sealed) envelope verbatim and need no
        // key-unlock state — same contract as the Android offline queue.
        let idempotencyKey = UUID().uuidString
        do {
            let message = try await api.request(
                CottageDTOs.ChatMessage.self, "POST", "/cottage/chat/messages",
                body: body, headers: ["Idempotency-Key": idempotencyKey]
            )
            // Encrypted round-trips come back with content=null: backfill the
            // local plaintext so the sender sees their own words immediately.
            if message.isEncrypted { decrypted[message.mid] = trimmed }
            merge(message)
        } catch let error as APIError where error.isTransport {
            guard let payload = try? LoveAPIClient.encoder.encode(body) else {
                showToast(Self.describe(error))
                return
            }
            outbox.enqueue(
                action: OutboxActions.chatSend,
                payload: payload,
                idempotencyKey: idempotencyKey
            )
            showToast(String(localized: "outbox.queued"))
        } catch {
            showToast(Self.describe(error))
        }
    }

    /// Drives the TYPING edge signal: notify once on empty↔non-empty.
    func inputChanged(_ text: String) {
        let active = !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        guard active != typingActive else { return }
        typingActive = active
        socket?.send(type: "TYPING", payload: ["is_typing": active])
    }

    private func stopTypingSignalIfNeeded() {
        guard typingActive else { return }
        typingActive = false
        socket?.send(type: "TYPING", payload: ["is_typing": false])
    }

    func poke() async {
        do {
            _ = try await api.requestVoid("POST", "/cottage/poke", body: PokeBody(kind: "poke"))
            showToast(String(localized: "cottage.chat.poke.sent"))
        } catch {
            showToast(Self.describe(error))
        }
    }

    // MARK: Message actions

    func toggleFavorite(_ message: CottageDTOs.ChatMessage) async {
        do {
            let updated = try await api.request(
                CottageDTOs.ChatMessage.self,
                message.isFavorite ? "DELETE" : "POST",
                "/cottage/chat/messages/\(message.mid)/favorite"
            )
            merge(updated)
        } catch {
            showToast(Self.describe(error))
        }
    }

    func recall(_ message: CottageDTOs.ChatMessage) async {
        do {
            let updated = try await api.request(
                CottageDTOs.ChatMessage.self, "POST",
                "/cottage/chat/messages/\(message.mid)/recall"
            )
            merge(updated)
        } catch {
            showToast(Self.describe(error))
        }
    }

    func pin(_ message: CottageDTOs.ChatMessage) async {
        do {
            _ = try await api.request(
                CottageDTOs.PinnedQuote.self, "PUT", "/cottage/chat/pinned-quote",
                body: PinnedQuoteBody(mid: message.mid)
            )
            showToast(String(localized: "cottage.chat.pin.done"))
        } catch {
            showToast(Self.describe(error))
        }
    }

    // MARK: Socket events

    private func handleFrame(_ frame: CottageSocket.Frame) {
        guard let payload = frame.payload else { return }
        switch frame.type {
        case "CHAT_MESSAGE":
            guard let data = try? JSONSerialization.data(withJSONObject: payload),
                  let message = try? LoveAPIClient.decode(
                      CottageDTOs.ChatMessage.self, from: data
                  )
            else { return }
            merge(message)
            if let selfUid, message.senderUid != selfUid, !message.senderUid.isEmpty {
                Task { try? await api.requestVoid("POST", "/cottage/chat/read") }
            }
        case "PRESENCE":
            guard let uid = payload["uid"] as? String,
                  partnerUid == nil || uid == partnerUid
            else { return }
            partnerOnline = payload["online"] as? Bool ?? false
        case "PRESENCE_SNAPSHOT":
            guard let partnerUid,
                  let online = payload["online"] as? [Any]
            else { return }
            let uids = online.compactMap { $0 as? String }
            partnerOnline = uids.contains(partnerUid)
        case "TYPING":
            let uid = payload["uid"] as? String
            guard uid == nil || uid == partnerUid || partnerUid == nil else { return }
            let typing = payload["is_typing"] as? Bool ?? false
            partnerTyping = typing
            if typing {
                typingResetTask?.cancel()
                typingResetTask = Task { [weak self] in
                    try? await Task.sleep(for: .seconds(6))
                    guard !Task.isCancelled else { return }
                    self?.partnerTyping = false
                }
            } else {
                typingResetTask?.cancel()
            }
        case "CHAT_READ":
            // The partner read our messages — flip local read markers.
            guard let reader = payload["reader_uid"] as? String,
                  let selfUid, reader != selfUid
            else { return }
            markSelfMessagesRead()
        case "POKE":
            let from = payload["from_nickname"] as? String ?? ""
            let label = payload["label"] as? String ?? ""
            showToast("\(from) \(label)")
        default:
            break
        }
    }

    private func markSelfMessagesRead() {
        guard let selfUid else { return }
        var changed = false
        for (mid, message) in messageIndex
        where message.senderUid == selfUid && message.readAt == nil {
            messageIndex[mid]?.readAt = Date()
            changed = true
        }
        if changed { emitMessages() }
    }

    // MARK: Merging

    private func merge(_ message: CottageDTOs.ChatMessage) {
        if let existing = messageIndex[message.mid] {
            // WS echoes omit flags only the REST superset carries — keep the
            // richer local values when the fresh frame defaulted them.
            var merged = message
            merged.isFavorite = message.isFavorite || existing.isFavorite
            merged.isFuture = message.isFuture || existing.isFuture
            merged.canRecall = message.canRecall || existing.canRecall
            merged.isSelf = message.isSelf || existing.isSelf
            if message.readAt == nil { merged.readAt = existing.readAt }
            if message.content == nil { merged.content = existing.content }
            messageIndex[message.mid] = merged
        } else {
            messageIndex[message.mid] = message
        }
        emitMessages()
    }

    private func emitMessages() {
        predecrypt()
        messages = messageIndex.values.sorted { $0.id < $1.id }
    }

    /// Best-effort decryption of every encrypted message while unlocked.
    private func predecrypt() {
        guard let chatKey else { return }
        for message in messageIndex.values
        where message.isEncrypted && !message.isRecalled {
            guard let iv = message.iv, let cipher = message.ciphertext else { continue }
            if let text = try? ChatCrypto.decryptString(
                key: chatKey, ivBase64: iv, ciphertextBase64: cipher
            ) {
                decrypted[message.mid] = text
            }
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

    private static func describe(_ error: Error) -> String {
        (error as? APIError)?.message ?? String(localized: "cottage.error.generic")
    }
}

// MARK: - View

struct CottageChatView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: ChatViewModel?

    @State private var keySheet: ChatKeySheet.Mode?
    @State private var scheduleSheet = false
    @State private var draft = ""
    @State private var futureDate: Date?

    var body: some View {
        Group {
            if let model {
                VStack(spacing: 0) {
                    statusBar(model)
                    messageList(model)
                    inputBar(model)
                }
                .overlay(alignment: .top) { toastBanner(model) }
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("cottage.chat.title")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let model { ToolbarItem(placement: .topBarTrailing) { e2eeButton(model) } }
        }
        .onAppear {
            if model == nil {
                let uid: String?
                if case .loggedIn(let profile) = environment.session.state {
                    uid = profile.uid
                } else {
                    uid = nil
                }
                let viewModel = ChatViewModel(api: environment.api, selfUid: uid, outbox: environment.outbox)
                model = viewModel
                viewModel.start()
            }
        }
        .onDisappear { model?.stop() }
        .sheet(item: $keySheet) { mode in
            if let model {
                ChatKeySheet(mode: mode, model: model)
            }
        }
        .sheet(isPresented: $scheduleSheet) {
            ScheduleMessageSheet { date in
                futureDate = date
            }
        }
    }

    // MARK: E2EE toolbar button

    @ViewBuilder
    private func e2eeButton(_ model: ChatViewModel) -> some View {
        switch model.e2eeStatus {
        case .unknown:
            ProgressView()
        case .off:
            Button {
                keySheet = .setup
            } label: {
                Image(systemName: "lock.badge.plus")
            }
        case .locked:
            Button {
                keySheet = .unlock
            } label: {
                Image(systemName: "lock.fill")
            }
        case .unlocked:
            Button {
                model.lock()
            } label: {
                Image(systemName: "lock.open.fill")
            }
        }
    }

    // MARK: Status bar

    private func statusBar(_ model: ChatViewModel) -> some View {
        HStack(spacing: 8) {
            Circle()
                .fill(model.connected ? LoveTheme.mint : LoveTheme.secondaryText)
                .frame(width: 8, height: 8)
            Text(
                model.partnerNickname.isEmpty
                    ? String(localized: "cottage.chat.partner")
                    : model.partnerNickname
            )
            .font(.footnote.weight(.semibold))
            .foregroundStyle(LoveTheme.text)
            Text(model.partnerOnline ? "cottage.chat.online" : "cottage.chat.offline")
                .font(.caption)
                .foregroundStyle(model.partnerOnline ? LoveTheme.mint : LoveTheme.secondaryText)
            Spacer()
            if model.partnerTyping {
                Text("cottage.chat.typing")
                    .font(.caption)
                    .foregroundStyle(LoveTheme.primaryAccessible)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(LoveTheme.surface)
    }

    private func toastBanner(_ model: ChatViewModel) -> some View {
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

    // MARK: Message list

    private func messageList(_ model: ChatViewModel) -> some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 10) {
                    if model.hasMore {
                        Button {
                            Task { await model.loadEarlier() }
                        } label: {
                            if model.loadingEarlier {
                                ProgressView().tint(LoveTheme.primaryAccessible)
                            } else {
                                Text("cottage.chat.load.earlier")
                                    .font(.footnote.weight(.medium))
                                    .foregroundStyle(LoveTheme.primaryAccessible)
                            }
                        }
                        .padding(.vertical, 6)
                    }
                    if model.loading {
                        LoveLoadingView().frame(height: 200)
                    } else if let error = model.error, model.messages.isEmpty {
                        LoveErrorView(message: error) {
                            Task { await model.retryInitial() }
                        }
                    } else if model.messages.isEmpty {
                        LoveEmptyState(
                            systemImage: "bubble.left.and.bubble.right",
                            titleKey: "cottage.chat.empty",
                            messageKey: "cottage.chat.empty.hint"
                        )
                        .padding(.top, 60)
                    }
                    ForEach(model.messages) { message in
                        ChatMessageBubble(message: message, model: model)
                            .id(message.mid)
                    }
                }
                .padding(16)
            }
            .defaultScrollAnchor(.bottom)
            .onChange(of: model.messages.last?.mid) { _, _ in
                guard let last = model.messages.last else { return }
                withAnimation(.easeOut(duration: 0.2)) {
                    proxy.scrollTo(last.mid, anchor: .bottom)
                }
            }
        }
    }

    // MARK: Input bar

    private func inputBar(_ model: ChatViewModel) -> some View {
        VStack(spacing: 8) {
            if let futureDate {
                HStack(spacing: 6) {
                    Image(systemName: "clock.badge.ellipsis")
                        .font(.caption)
                    Text("cottage.chat.schedule.at \(Format.dateTime(futureDate))")
                    Spacer()
                    Button {
                        self.futureDate = nil
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.footnote)
                    }
                }
                .font(.caption)
                .foregroundStyle(LoveTheme.primaryAccessible)
                .padding(.horizontal, 16)
            }
            HStack(spacing: 8) {
                TextField(
                    "cottage.chat.input.placeholder",
                    text: $draft,
                    axis: .vertical
                )
                .lineLimit(1...4)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(LoveTheme.surface)
                .clipShape(Capsule())
                .onChange(of: draft) { _, newValue in
                    model.inputChanged(newValue)
                }
                .onSubmit { sendDraft(model) }

                Button {
                    Task { await model.poke() }
                } label: {
                    Image(systemName: "heart.circle.fill")
                        .font(.title2)
                        .foregroundStyle(LoveTheme.rose)
                }
                .buttonStyle(.plain)

                Button {
                    scheduleSheet = true
                } label: {
                    Image(systemName: "clock.badge")
                        .font(.title3)
                        .foregroundStyle(futureDate == nil ? LoveTheme.primaryAccessible : LoveTheme.rose)
                }
                .buttonStyle(.plain)

                sendButton(model)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(LoveTheme.surface.opacity(0.9))
    }

    private func sendButton(_ model: ChatViewModel) -> some View {
        Button {
            sendDraft(model)
        } label: {
            if model.sending {
                ProgressView()
                    .tint(.white)
                    .frame(width: 38, height: 38)
            } else {
                Image(systemName: "paperplane.fill")
                    .font(.title3)
                    .foregroundStyle(.white)
                    .frame(width: 38, height: 38)
            }
        }
        .background(sendAllowed(model) ? AnyShapeStyle(LoveTheme.gradient) : AnyShapeStyle(LoveTheme.outline), in: Circle())
        .disabled(!sendAllowed(model))
    }

    /// Blocked while the E2EE state is unproven; `.locked` stays tappable so
    /// the tap can explain that the passphrase must be entered first.
    private func sendAllowed(_ model: ChatViewModel) -> Bool {
        if case .unknown = model.e2eeStatus { return false }
        if model.sending { return false }
        return !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private func sendDraft(_ model: ChatViewModel) {
        let text = draft
        let visibleAt = futureDate
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        draft = ""
        futureDate = nil
        Task { await model.send(text, visibleAt: visibleAt) }
    }
}

// MARK: - Message bubble

private struct ChatMessageBubble: View {
    let message: CottageDTOs.ChatMessage
    let model: ChatViewModel

    private var isSelf: Bool {
        guard let selfUid = model.selfUid else { return message.isSelf }
        return message.senderUid == selfUid
    }

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if isSelf { Spacer(minLength: 48) }
            VStack(alignment: isSelf ? .trailing : .leading, spacing: 4) {
                if let reply = message.replyTo {
                    replyBar(reply)
                }
                bodyContent
                HStack(spacing: 4) {
                    if message.isFavorite {
                        Image(systemName: "star.fill")
                            .font(.caption2)
                    }
                    Text(Format.dateTime(message.createdAt))
                    if isSelf {
                        Text(message.readAt == nil ? "cottage.chat.delivered" : "cottage.chat.read")
                    }
                }
                .font(.caption2)
                .foregroundStyle(isSelf ? .white.opacity(0.85) : LoveTheme.secondaryText)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(
                isSelf
                    ? AnyShapeStyle(LoveTheme.gradient)
                    : AnyShapeStyle(LoveTheme.surface)
            )
            .foregroundStyle(isSelf ? Color.white : LoveTheme.text)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .frame(maxWidth: 264, alignment: isSelf ? .trailing : .leading)
            .contextMenu { contextActions }
            if !isSelf { Spacer(minLength: 48) }
        }
    }

    @ViewBuilder
    private var bodyContent: some View {
        if message.isRecalled {
            Text("cottage.chat.recalled")
                .font(.footnote)
                .italic()
        } else {
            VStack(alignment: .leading, spacing: 6) {
                if message.isFuture, let visibleAt = message.visibleAt, visibleAt > Date() {
                    Text("cottage.chat.future.at \(Format.dateTime(visibleAt))")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(isSelf ? Color.white.opacity(0.9) : LoveTheme.primaryAccessible)
                }
                switch message.type {
                case "image":
                    VStack(alignment: .leading, spacing: 6) {
                        LoveAsyncImage(url: ServerSettings.mediaURL(message.mediaUrl), contentMode: .fill)
                            .frame(width: 200, height: 150)
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        if let caption = model.displayText(message) as String?, !caption.isEmpty, !message.isEncrypted {
                            Text(caption)
                        }
                    }
                case "voice":
                    Label {
                        Text("cottage.chat.voice \(message.audioDurationSec ?? 0)")
                    } icon: {
                        Image(systemName: "waveform")
                    }
                    .font(.footnote.weight(.medium))
                default:
                    Text(model.displayText(message))
                        .textSelection(.enabled)
                }
            }
        }
    }

    private func replyBar(_ reply: CottageDTOs.ChatMessage.ReplyPreview) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(reply.senderNickname)
                .font(.caption.weight(.semibold))
            Text(reply.content ?? String(localized: "cottage.chat.reply.original"))
                .font(.caption)
                .lineLimit(2)
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            isSelf ? Color.white.opacity(0.18) : LoveTheme.background.opacity(0.6)
        )
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }

    @ViewBuilder
    private var contextActions: some View {
        Button {
            Task { await model.toggleFavorite(message) }
        } label: {
            Label(
                message.isFavorite ? "cottage.chat.action.unfavorite" : "cottage.chat.action.favorite",
                systemImage: message.isFavorite ? "star.slash" : "star"
            )
        }
        if message.type == "text", !message.isRecalled {
            Button {
                Task { await model.pin(message) }
            } label: {
                Label("cottage.chat.action.pin", systemImage: "quote.opening")
            }
        }
        if model.canRecall(message) {
            Button(role: .destructive) {
                Task { await model.recall(message) }
            } label: {
                Label("cottage.chat.action.recall", systemImage: "arrow.uturn.backward")
            }
        }
    }
}

// MARK: - E2EE key sheet

private struct ChatKeySheet: View {
    enum Mode: Identifiable {
        case setup
        case unlock
        var id: Self { self }
    }

    let mode: Mode
    let model: ChatViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var passphrase = ""
    @State private var confirmation = ""
    @State private var errorText: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    if case .setup = mode {
                        Text("cottage.chat.e2ee.setup.intro")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    LoveField(labelKey: "cottage.chat.e2ee.passphrase") {
                        SecureField("cottage.chat.e2ee.passphrase", text: $passphrase)
                    }
                    if case .setup = mode {
                        LoveField(labelKey: "cottage.chat.e2ee.confirm") {
                            SecureField("cottage.chat.e2ee.confirm", text: $confirmation)
                        }
                        Text("cottage.chat.e2ee.hint")
                            .font(.caption)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    if let errorText {
                        LoveErrorBanner(message: errorText)
                    }
                    LovePrimaryButton(
                        titleKey: submitTitle,
                        loading: model.keyWorking,
                        action: { submit() }
                    )
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(sheetTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("common.cancel") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium])
    }

    private var sheetTitle: LocalizedStringKey {
        mode == .setup ? "cottage.chat.e2ee.setup.title" : "cottage.chat.e2ee.unlock.title"
    }

    private var submitTitle: LocalizedStringKey {
        mode == .setup ? "cottage.chat.e2ee.setup" : "cottage.chat.e2ee.unlock"
    }

    private func submit() {
        if case .setup = mode {
            guard passphrase.count >= 6 else {
                errorText = String(localized: "cottage.chat.e2ee.too.short")
                return
            }
            guard passphrase == confirmation else {
                errorText = String(localized: "cottage.chat.e2ee.mismatch")
                return
            }
        }
        Task {
            let result: String?
            if case .setup = mode {
                result = await model.setupEncryption(passphrase: passphrase)
            } else {
                result = await model.unlock(passphrase: passphrase)
            }
            if let result {
                errorText = result
            } else {
                dismiss()
            }
        }
    }
}

// MARK: - "Send to the future" sheet

private struct ScheduleMessageSheet: View {
    @Environment(\.dismiss) private var dismiss
    let onSchedule: (Date) -> Void
    @State private var date = Date().addingTimeInterval(60 * 60)

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                LoveSoftCard {
                    Text("cottage.chat.schedule.hint")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                    DatePicker(
                        "cottage.chat.schedule.pick",
                        selection: $date,
                        in: Date()...
                    )
                    .tint(LoveTheme.primaryAccessible)
                    LovePrimaryButton(titleKey: "cottage.chat.schedule.send") {
                        onSchedule(date)
                        dismiss()
                    }
                }
                Spacer()
            }
            .padding(20)
            .loveScreenBackground()
            .navigationTitle("cottage.chat.schedule.title")
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
