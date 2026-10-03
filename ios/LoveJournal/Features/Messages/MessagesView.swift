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

@MainActor
@Observable
final class MessagesViewModel {
    var loading = true
    var error: String?
    var messages: [ContentDTOs.Message] = []
    var status: String?
    var sending = false
    var selfUid: String?

    private let api: LoveAPIClient
    private let outbox: OutboxSyncer

    init(api: LoveAPIClient, selfUid: String?, outbox: OutboxSyncer) {
        self.api = api
        self.selfUid = selfUid
        self.outbox = outbox
    }

    /// Newest last (chat-like), tombstones filtered out.
    var visible: [ContentDTOs.Message] {
        messages
            .filter { !$0.isDeleted }
            .sorted { $0.createdAt < $1.createdAt }
    }

    func refresh() async {
        if messages.isEmpty { loading = true }
        do {
            let page = try await api.request(
                ContentDTOs.Page<ContentDTOs.Message>.self,
                "GET",
                "/messages",
                query: [URLQueryItem(name: "include_private", value: "true")]
            )
            messages = page.items
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? "加载失败，请稍后重试"
        }
        loading = false
    }

    func send(content: String, isPublic: Bool) async {
        let text = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        sending = true
        defer { sending = false }
        // One key for the live attempt and any offline replay.
        let idempotencyKey = UUID().uuidString
        do {
            let message = try await api.request(
                ContentDTOs.Message.self,
                "POST",
                "/messages",
                body: ContentDTOs.MessageCreate(content: text, isPublic: isPublic),
                headers: ["Idempotency-Key": idempotencyKey]
            )
            messages.append(message)
            status = "已发送"
        } catch let error as APIError where error.isTransport {
            guard
                let payload = try? LoveAPIClient.encoder.encode(
                    ContentDTOs.MessageCreate(content: text, isPublic: isPublic)
                )
            else {
                status = error.message
                return
            }
            outbox.enqueue(
                action: OutboxActions.messageCreate,
                payload: payload,
                idempotencyKey: idempotencyKey
            )
            status = String(localized: "outbox.queued")
        } catch {
            status = (error as? APIError)?.message ?? "发送失败，请稍后重试"
        }
    }

    func edit(_ message: ContentDTOs.Message, newContent: String, newIsPublic: Bool) async {
        let text = newContent.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        var patch = ContentDTOs.MessagePatch()
        if text != message.content { patch.content = text }
        if newIsPublic != message.isPublic { patch.isPublic = newIsPublic }
        guard patch.content != nil || patch.isPublic != nil else { return }
        do {
            let updated = try await api.request(
                ContentDTOs.Message.self,
                "PATCH",
                "/messages/\(message.msgId)",
                body: patch
            )
            replace(updated)
            status = "保存成功"
        } catch {
            status = (error as? APIError)?.message ?? "保存失败，请稍后重试"
        }
    }

    func delete(_ message: ContentDTOs.Message) async {
        do {
            try await api.requestVoid("DELETE", "/messages/\(message.msgId)")
            messages.removeAll { $0.msgId == message.msgId }
            status = "已删除"
        } catch {
            status = (error as? APIError)?.message ?? "删除失败，请稍后重试"
        }
    }

    private func replace(_ updated: ContentDTOs.Message) {
        if let index = messages.firstIndex(where: { $0.msgId == updated.msgId }) {
            messages[index] = updated
        }
    }
}

struct MessagesView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: MessagesViewModel?
    @State private var draft = ""
    @State private var draftIsPublic = true
    @State private var editingMessage: ContentDTOs.Message?
    @State private var editDraft = ""
    @State private var editIsPublic = true
    @State private var deletingMessage: ContentDTOs.Message?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("messages.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                let uid: String?
                if case .loggedIn(let profile) = environment.session.state {
                    uid = profile.uid
                } else {
                    uid = nil
                }
                model = MessagesViewModel(api: environment.api, selfUid: uid, outbox: environment.outbox)
                Task { await model?.refresh() }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .outboxDidFlush)) { note in
            let actions = note.userInfo?["actions"] as? [String] ?? []
            if actions.contains(OutboxActions.messageCreate) {
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: MessagesViewModel) -> some View {
        VStack(spacing: 0) {
            if let status = model.status {
                LoveSuccessBanner(message: status)
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
            }
            if let error = model.error, model.messages.isEmpty {
                LoveErrorView(message: error) {
                    Task { await model.refresh() }
                }
            } else if model.loading {
                LoveLoadingView()
            } else if model.visible.isEmpty {
                LoveEmptyState(
                    systemImage: "bubble.left.and.bubble.right",
                    titleKey: "messages.empty",
                    messageKey: "messages.empty.hint"
                )
            } else {
                messageList(model)
            }
            inputBar(model)
        }
        .refreshable { await model.refresh() }
        .sheet(item: $editingMessage) { message in
            MessageEditSheet(message: message) { newContent, newIsPublic in
                Task { await model.edit(message, newContent: newContent, newIsPublic: newIsPublic) }
            }
            .presentationDetents([.medium])
        }
        .confirmationDialog(
            "messages.delete.confirm",
            isPresented: Binding(
                get: { deletingMessage != nil },
                set: { if !$0 { deletingMessage = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("common.delete", role: .destructive) {
                if let message = deletingMessage {
                    Task { await model.delete(message) }
                }
                deletingMessage = nil
            }
        } message: {
            Text("messages.delete.hint")
        }
    }

    private func messageList(_ model: MessagesViewModel) -> some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 10) {
                    ForEach(model.visible) { message in
                        messageRow(model, message)
                            .id(message.msgId)
                    }
                }
                .padding(16)
            }
            .onChange(of: model.visible.last?.msgId) { _, last in
                if let last {
                    withAnimation { proxy.scrollTo(last, anchor: .bottom) }
                }
            }
        }
    }

    private func messageRow(_ model: MessagesViewModel, _ message: ContentDTOs.Message) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 6) {
                    Text(message.displayAuthor.isEmpty ? String(localized: "messages.anonymous") : message.displayAuthor)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(LoveTheme.primaryAccessible)
                    if !message.isPublic {
                        LovePill(text: String(localized: "messages.private"), tint: LoveTheme.lavender)
                    }
                    Spacer()
                    Text(Format.dateTime(message.createdAt))
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                Text(message.content)
                    .font(.subheadline)
                    .foregroundStyle(LoveTheme.text)
            }
            .contextMenu {
                if message.authorUid != nil && message.authorUid == model.selfUid {
                    Button {
                        editDraft = message.content
                        editIsPublic = message.isPublic
                        editingMessage = message
                    } label: {
                        Label("common.edit", systemImage: "pencil")
                    }
                    Button(role: .destructive) {
                        deletingMessage = message
                    } label: {
                        Label("common.delete", systemImage: "trash")
                    }
                }
            }
        }
    }

    private func inputBar(_ model: MessagesViewModel) -> some View {
        VStack(spacing: 8) {
            Picker("messages.visibility", selection: $draftIsPublic) {
                Text("messages.public").tag(true)
                Text("messages.private").tag(false)
            }
            .pickerStyle(.segmented)
            HStack(spacing: 10) {
                TextField(
                    draftIsPublic
                        ? String(localized: "messages.input.placeholder")
                        : String(localized: "messages.input.placeholder.private"),
                    text: $draft,
                    axis: .vertical
                )
                .font(.subheadline)
                .lineLimit(1...4)
                .padding(.horizontal, 12)
                .padding(.vertical, 9)
                .background(LoveTheme.surface, in: RoundedRectangle(cornerRadius: 14))
                .overlay {
                    RoundedRectangle(cornerRadius: 14)
                        .stroke(LoveTheme.outline, lineWidth: 1)
                }
                Button {
                    let text = draft
                    draft = ""
                    Task {
                        await model.send(content: text, isPublic: draftIsPublic)
                    }
                } label: {
                    Image(systemName: "paperplane.fill")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                        .frame(width: 38, height: 38)
                        .background(
                            draft.trimmingCharacters(in: .whitespaces).isEmpty || model.sending
                                ? AnyShapeStyle(LoveTheme.outline)
                                : AnyShapeStyle(LoveTheme.gradient),
                            in: Circle()
                        )
                }
                .disabled(draft.trimmingCharacters(in: .whitespaces).isEmpty || model.sending)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(LoveTheme.surface.opacity(0.95))
    }
}

private struct MessageEditSheet: View {
    @Environment(\.dismiss) private var dismiss
    let message: ContentDTOs.Message
    let onSave: (String, Bool) -> Void

    @State private var content: String = ""
    @State private var isPublic = true

    var body: some View {
        NavigationStack {
            LoveSoftCard {
                LoveField(labelKey: "messages.edit.content") {
                    TextField("messages.edit.content", text: $content, axis: .vertical)
                        .lineLimit(3...8)
                }
                Toggle(isOn: $isPublic) {
                    Text("messages.public")
                }
                .tint(LoveTheme.primaryAccessible)
                LovePrimaryButton(titleKey: "common.save") {
                    onSave(content, isPublic)
                    dismiss()
                }
            }
            .padding(20)
            .loveScreenBackground()
            .navigationTitle("messages.edit.title")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("common.cancel") { dismiss() }
                }
            }
        }
        .onAppear {
            content = message.content
            isPublic = message.isPublic
        }
    }
}
