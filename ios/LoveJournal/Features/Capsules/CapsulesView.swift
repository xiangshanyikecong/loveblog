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

// MARK: - M2 shared helpers (write-path screens)

/// M2 write-path lookups. The new keys live in `M2.xcstrings`, whose table
/// name is `"M2"` — every lookup must therefore pass the table explicitly
/// (String Catalogs are per-file tables; the default table stays
/// `Localizable`).
enum M2L10n {
    static func value(_ keyAndValue: String.LocalizationValue) -> String {
        String(localized: keyAndValue, table: "M2")
    }
}

extension LocalizedStringKey {
    /// Resolves an M2 key up front. The default-table lookup then misses and
    /// falls back to the resolved text itself, so shared components that only
    /// take `LocalizedStringKey` (LoveField, LovePrimaryButton, …) render the
    /// translated string.
    init(m2 key: String) {
        self.init(stringLiteral: M2L10n.value(String.LocalizationValue(key)))
    }
}

enum M2Support {
    /// Parses a comma-separated tag field (ASCII and full-width commas).
    static func parseTags(_ raw: String) -> [String] {
        raw.components(separatedBy: CharacterSet(charactersIn: ",，"))
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }
}

/// Bottom comment input bar shared by the article/album detail screens.
struct M2CommentBar: View {
    @Binding var text: String
    var disabled = false
    let onSend: () -> Void

    private var canSend: Bool {
        !disabled && !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        HStack(spacing: 10) {
            TextField(M2L10n.value("comment.placeholder"), text: $text, axis: .vertical)
                .lineLimit(1...4)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(LoveTheme.background.opacity(0.6))
                .clipShape(RoundedRectangle(cornerRadius: 19, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 19, style: .continuous)
                        .stroke(LoveTheme.outline, lineWidth: 1)
                }
            Button(action: onSend) {
                Image(systemName: "paperplane.fill")
                    .font(.subheadline)
                    .foregroundStyle(.white)
                    .frame(width: 38, height: 38)
                    .background(LoveTheme.gradient, in: Circle())
            }
            .disabled(!canSend)
            .opacity(canSend ? 1 : 0.5)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(LoveTheme.surface.ignoresSafeArea())
    }
}

// MARK: - Capsules

@MainActor
@Observable
final class CapsulesViewModel {
    var loading = true
    var error: String?
    var capsules: [WriteDTOs.Capsule] = []
    var message: String?
    var saving = false

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        if capsules.isEmpty { loading = true }
        do {
            capsules = try await api.request([WriteDTOs.Capsule].self, "GET", "/capsules")
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? M2L10n.value("common.error.load")
        }
        loading = false
    }

    /// Returns nil on success, otherwise a user-presentable error message.
    func create(content: String, openAt: Date) async -> String? {
        let text = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return M2L10n.value("capsules.editor.content.required") }
        saving = true
        defer { saving = false }
        do {
            _ = try await api.request(
                WriteDTOs.Capsule.self,
                "POST",
                "/capsules",
                body: CapsuleCreateBody(content: text, openAt: openAt)
            )
            message = M2L10n.value("capsules.created")
            await refresh()
            return nil
        } catch {
            return (error as? APIError)?.message ?? M2L10n.value("common.error.save")
        }
    }

    func delete(_ capsule: WriteDTOs.Capsule) async {
        do {
            try await api.requestVoid("DELETE", "/capsules/\(capsule.uuid)")
            capsules.removeAll { $0.uuid == capsule.uuid }
            message = M2L10n.value("capsules.deleted")
        } catch {
            message = (error as? APIError)?.message ?? M2L10n.value("common.error.delete")
        }
    }
}

struct CapsulesView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: CapsulesViewModel?
    @State private var composerPresented = false
    @State private var capsuleToDelete: WriteDTOs.Capsule?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m2: "capsules.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = CapsulesViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: CapsulesViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error, model.capsules.isEmpty {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else if model.capsules.isEmpty {
                    LoveEmptyState(
                        systemImage: "seal",
                        titleKey: .init(m2: "capsules.empty"),
                        messageKey: .init(m2: "capsules.empty.hint")
                    )
                } else {
                    ForEach(model.capsules) { capsule in
                        capsuleCard(capsule)
                    }
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
        .overlay(alignment: .bottomTrailing) {
            Button {
                composerPresented = true
            } label: {
                Label {
                    Text(.init(m2: "capsules.add"))
                } icon: {
                    Image(systemName: "seal")
                }
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.white)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(LoveTheme.gradient, in: Capsule())
                .shadow(color: LoveTheme.rose.opacity(0.35), radius: 8, y: 3)
            }
            .padding(20)
        }
        .sheet(isPresented: $composerPresented) {
            CapsuleComposerSheet(model: model)
        }
        .confirmationDialog(
            Text(capsuleToDelete == nil ? "" : M2L10n.value("capsules.delete.confirm")),
            isPresented: Binding(
                get: { capsuleToDelete != nil },
                set: { if !$0 { capsuleToDelete = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button(M2L10n.value("common.delete"), role: .destructive) {
                if let capsule = capsuleToDelete {
                    Task { await model.delete(capsule) }
                }
                capsuleToDelete = nil
            }
            Button(M2L10n.value("common.cancel"), role: .cancel) {
                capsuleToDelete = nil
            }
        }
    }

    private func capsuleCard(_ capsule: WriteDTOs.Capsule) -> some View {
        LoveSoftCard {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 8) {
                    if capsule.isOpen {
                        if let content = capsule.content, !content.isEmpty {
                            Text(content)
                                .font(.subheadline)
                                .foregroundStyle(LoveTheme.text)
                        }
                        if capsule.mediaUrl != nil {
                            mediaPlaceholder(capsule)
                        }
                        metaLine(capsule)
                    } else {
                        Label {
                            Text(
                                "capsules.open.at \(Format.dateTime(capsule.openAt))",
                                tableName: "M2"
                            )
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.primaryAccessible)
                        } icon: {
                            Image(systemName: "lock.fill")
                                .font(.footnote)
                                .foregroundStyle(LoveTheme.lavender)
                        }
                        metaLine(capsule)
                        if capsule.hasMedia {
                            LovePill(
                                text: M2L10n.value("capsules.media.attach"),
                                tint: LoveTheme.lavender
                            )
                        }
                    }
                }
                Spacer()
                Button {
                    capsuleToDelete = capsule
                } label: {
                    Image(systemName: "trash")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.rose)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func metaLine(_ capsule: WriteDTOs.Capsule) -> some View {
        HStack(spacing: 6) {
            Text(capsule.authorNickname)
            Text("·")
            Text(Format.dateTime(capsule.createdAt))
        }
        .font(.caption2)
        .foregroundStyle(LoveTheme.secondaryText)
    }

    /// Static audio/video placeholder — playback arrives in a later milestone.
    private func mediaPlaceholder(_ capsule: WriteDTOs.Capsule) -> some View {
        HStack(spacing: 8) {
            Image(systemName: capsule.mediaType == "video" ? "video.fill" : "waveform")
            Text(
                capsule.mediaType == "video"
                    ? M2L10n.value("capsules.media.video")
                    : M2L10n.value("capsules.media.audio \(capsule.mediaDurationSec ?? 0)")
            )
        }
        .font(.footnote)
        .foregroundStyle(LoveTheme.mint)
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14)
        .background(LoveTheme.mint.opacity(0.12), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

struct CapsuleComposerSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: CapsulesViewModel

    @State private var content = ""
    @State private var openAt = Calendar.current.date(byAdding: .month, value: 1, to: Date())
        ?? Date().addingTimeInterval(30 * 24 * 3600)
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: .init(m2: "capsules.editor.content")) {
                        TextField(
                            M2L10n.value("capsules.editor.content.placeholder"),
                            text: $content,
                            axis: .vertical
                        )
                        .lineLimit(4...10)
                    }
                    DatePicker(
                        .init(m2: "capsules.editor.openAt"),
                        selection: $openAt,
                        in: Date()...
                    )
                    .tint(LoveTheme.primaryAccessible)
                    if let error {
                        LoveErrorBanner(message: error)
                    }
                    LovePrimaryButton(
                        titleKey: .init(m2: "capsules.add"),
                        loading: model.saving
                    ) {
                        Task {
                            if let failure = await model.create(content: content, openAt: openAt) {
                                error = failure
                            } else {
                                dismiss()
                            }
                        }
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(.init(m2: "capsules.add"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(M2L10n.value("common.cancel")) { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

/// `WriteDTOs.CapsuleCreate` carries `open_at` as a `Date`, but the shared
/// `LoveAPIClient` encoder emits dates as non-ISO numbers that FastAPI's
/// `datetime` field would misinterpret — the wire body needs a preformatted
/// ISO-8601 string.
private struct CapsuleCreateBody: Encodable {
    var content: String
    var openAt: Date

    private static let isoFormatter = ISO8601DateFormatter()

    enum CodingKeys: String, CodingKey {
        case content
        case openAt = "open_at"
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(content, forKey: .content)
        try container.encode(Self.isoFormatter.string(from: openAt), forKey: .openAt)
    }
}
