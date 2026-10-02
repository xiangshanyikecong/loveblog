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

/// Route value pushed from the album list to its detail.
struct AlbumRoute: Hashable {
    let albId: String
}

// MARK: - Editor draft

/// Album text fields for the create/edit sheet. Photos picked in the sheet
/// are uploaded immediately (via `MediaUploadService`) and carried alongside
/// the draft as `UploadResult`s.
struct AlbumEditorDraft {
    var title = ""
    var description = ""
    var tags: [String] = []

    init() {}

    init(detail: ContentDTOs.AlbumDetail) {
        title = detail.title
        description = detail.description ?? ""
        tags = detail.tags
    }
}

// MARK: - List

@MainActor
@Observable
final class AlbumsViewModel {
    var loading = true
    var error: String?
    var albums: [ContentDTOs.AlbumSummary] = []
    var message: String?
    var saving = false

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        if albums.isEmpty { loading = true }
        do {
            let page = try await api.request(
                ContentDTOs.Page<ContentDTOs.AlbumSummary>.self, "GET", "/albums"
            )
            albums = page.items
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? "加载失败，请稍后重试"
        }
        loading = false
    }

    /// Returns nil on success, otherwise a user-presentable error message.
    func create(_ draft: AlbumEditorDraft, uploads: [WriteDTOs.UploadResult]) async -> String? {
        saving = true
        defer { saving = false }
        let payload = Self.upsert(draft, existingItems: [], existingCover: nil, newUploads: uploads)
        do {
            _ = try await api.request(
                ContentDTOs.AlbumDetail.self, "POST", "/albums", body: payload
            )
            message = M2L10n.value("common.saved")
            await refresh()
            return nil
        } catch {
            return (error as? APIError)?.message ?? M2L10n.value("common.error.save")
        }
    }

    /// Assembles the full-replacement payload: existing media mapped back to
    /// inputs, new uploads appended, cover taken from the newest photo.
    static func upsert(
        _ draft: AlbumEditorDraft,
        existingItems: [WriteDTOs.AlbumMediaInput],
        existingCover: String?,
        newUploads: [WriteDTOs.UploadResult]
    ) -> WriteDTOs.AlbumUpsert {
        let newItems = newUploads.map { upload in
            WriteDTOs.AlbumMediaInput(
                fileUrl: upload.url,
                thumbnailUrl: upload.thumbnailUrl,
                fileSize: upload.size,
                mimeType: upload.contentType
            )
        }
        let trimmedDescription = draft.description.trimmingCharacters(in: .whitespacesAndNewlines)
        return WriteDTOs.AlbumUpsert(
            title: draft.title.trimmingCharacters(in: .whitespacesAndNewlines),
            description: trimmedDescription.isEmpty ? nil : trimmedDescription,
            coverUrl: newUploads.first?.url ?? existingCover,
            tags: draft.tags,
            mediaItems: existingItems + newItems
        )
    }
}

struct AlbumsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: AlbumsViewModel?
    @State private var editorPresented = false

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("tab.albums")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = AlbumsViewModel(api: environment.api)
            }
            // Also covers returning from a deleted album's detail screen.
            Task { await model?.refresh() }
        }
    }

    private func content(_ model: AlbumsViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error, model.albums.isEmpty {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else if model.albums.isEmpty {
                    LoveEmptyState(
                        systemImage: "photo.on.rectangle",
                        titleKey: "albums.empty",
                        messageKey: "albums.empty.hint"
                    )
                } else {
                    ForEach(model.albums) { album in
                        NavigationLink(value: AlbumRoute(albId: album.albId)) {
                            albumCard(album)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
        .navigationDestination(for: AlbumRoute.self) { route in
            AlbumDetailView(api: environment.api, albId: route.albId)
        }
        .overlay(alignment: .bottomTrailing) {
            Button {
                editorPresented = true
            } label: {
                Label {
                    Text(.init(m2: "albums.create"))
                } icon: {
                    Image(systemName: "plus")
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
        .sheet(isPresented: $editorPresented) {
            AlbumEditorSheet(editing: nil, api: environment.api, saving: model.saving) { draft, uploads in
                await model.create(draft, uploads: uploads)
            }
        }
    }

    private func albumCard(_ album: ContentDTOs.AlbumSummary) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 8) {
                LoveAsyncImage(url: ServerSettings.mediaURL(album.coverUrl))
                    .frame(height: 170)
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                HStack(spacing: 6) {
                    Text(album.title)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.text)
                    if album.isEncrypted {
                        Image(systemName: "lock.fill")
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.lavender)
                    }
                }
                if let description = album.description, !description.isEmpty {
                    Text(description)
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                        .lineLimit(2)
                }
                HStack(spacing: 6) {
                    Text("albums.count \(album.mediaCount)")
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.primaryAccessible)
                    ForEach(album.tags.prefix(2), id: \.self) { tag in
                        Text("#\(tag)")
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                }
            }
        }
    }
}

// MARK: - Editor sheet

struct AlbumEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    /// nil = create a new album.
    let editing: AlbumEditorDraft?
    let api: LoveAPIClient
    let saving: Bool
    let onSave: (AlbumEditorDraft, [WriteDTOs.UploadResult]) async -> String?

    @State private var title = ""
    @State private var descriptionText = ""
    @State private var tagsText = ""
    @State private var uploads: [WriteDTOs.UploadResult] = []
    @State private var uploading = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: .init(m2: "albums.editor.title")) {
                        TextField(M2L10n.value("albums.editor.title"), text: $title)
                    }
                    LoveField(labelKey: .init(m2: "albums.editor.description")) {
                        TextField(M2L10n.value("albums.editor.description"), text: $descriptionText)
                    }
                    LoveField(labelKey: .init(m2: "albums.editor.tags")) {
                        TextField(M2L10n.value("albums.editor.tags"), text: $tagsText)
                    }
                    photoSection
                    if let error {
                        LoveErrorBanner(message: error)
                    }
                    LovePrimaryButton(
                        titleKey: editing == nil ? .init(m2: "albums.create") : "common.save",
                        loading: saving || uploading
                    ) {
                        save()
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(editing == nil ? .init(m2: "albums.create") : .init(m2: "albums.edit"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(M2L10n.value("common.cancel")) { dismiss() }
                }
            }
        }
        .presentationDetents([.large])
        .onAppear {
            if let editing {
                title = editing.title
                descriptionText = editing.description
                tagsText = editing.tags.joined(separator: ", ")
            }
        }
    }

    private var photoSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 12) {
                LoveImagePicker { data in
                    addImage(data)
                }
                if uploading {
                    ProgressView().tint(LoveTheme.primaryAccessible)
                }
                Spacer()
                if !uploads.isEmpty {
                    Text("albums.editor.images.count \(uploads.count)", tableName: "M2")
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
            }
            if !uploads.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(Array(uploads.enumerated()), id: \.element.url) { index, upload in
                            uploadedThumb(upload) {
                                uploads.remove(at: index)
                            }
                        }
                    }
                }
            }
        }
    }

    private func uploadedThumb(
        _ upload: WriteDTOs.UploadResult,
        onRemove: @escaping () -> Void
    ) -> some View {
        LoveAsyncImage(url: ServerSettings.mediaURL(upload.url), contentMode: .fill)
            .frame(width: 84, height: 84)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay(alignment: .topTrailing) {
                Button(action: onRemove) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.footnote)
                        .foregroundStyle(.white)
                        .shadow(radius: 2)
                }
                .padding(4)
            }
    }

    /// Uploads on pick so save only assembles the payload.
    private func addImage(_ data: Data) {
        Task {
            uploading = true
            defer { uploading = false }
            do {
                uploads.append(
                    try await MediaUploadService.uploadImage(
                        data, path: MediaUploadService.albumsPath, api: api
                    )
                )
            } catch {
                self.error = (error as? APIError)?.message ?? M2L10n.value("albums.upload.failed")
            }
        }
    }

    private func save() {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty else {
            error = M2L10n.value("albums.editor.title.required")
            return
        }
        var draft = editing ?? AlbumEditorDraft()
        draft.title = trimmedTitle
        draft.description = descriptionText
        draft.tags = M2Support.parseTags(tagsText)
        Task {
            if let failure = await onSave(draft, uploads) {
                error = failure
            } else {
                dismiss()
            }
        }
    }
}

// MARK: - Detail

@MainActor
@Observable
final class AlbumDetailViewModel {
    var loading = true
    var error: String?
    var detail: ContentDTOs.AlbumDetail?
    var message: String?
    var saving = false

    private let api: LoveAPIClient
    private let albId: String

    init(api: LoveAPIClient, albId: String) {
        self.api = api
        self.albId = albId
    }

    func load() async {
        loading = detail == nil
        do {
            detail = try await api.request(
                ContentDTOs.AlbumDetail.self, "GET", "/albums/\(albId)"
            )
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? "加载失败，请稍后重试"
        }
        loading = false
    }

    /// Full-replacement PUT: existing media mapped back to inputs, new
    /// uploads appended, cover from the newest photo when present.
    func update(_ draft: AlbumEditorDraft, newUploads: [WriteDTOs.UploadResult]) async -> String? {
        guard let current = detail else { return nil }
        saving = true
        defer { saving = false }
        let existingItems = current.mediaItems.map { media in
            WriteDTOs.AlbumMediaInput(
                mediaType: media.mediaType,
                fileUrl: media.fileUrl,
                thumbnailUrl: media.thumbnailUrl,
                fileSize: media.fileSize,
                mimeType: media.mimeType,
                isEncrypted: media.isEncrypted
            )
        }
        let payload = AlbumsViewModel.upsert(
            draft,
            existingItems: existingItems,
            existingCover: current.coverUrl,
            newUploads: newUploads
        )
        // Preserve flags the editor does not expose.
        var withFlags = payload
        withFlags.isEncrypted = current.isEncrypted
        withFlags.isPublic = current.isPublic
        withFlags.visibility = current.visibility
        do {
            detail = try await api.request(
                ContentDTOs.AlbumDetail.self, "PUT", "/albums/\(albId)", body: withFlags
            )
            message = M2L10n.value("common.saved")
            return nil
        } catch {
            return (error as? APIError)?.message ?? M2L10n.value("common.error.save")
        }
    }

    /// Returns true when the detail screen should pop back to the list.
    func delete() async -> Bool {
        do {
            try await api.requestVoid("DELETE", "/albums/\(albId)")
            return true
        } catch {
            message = (error as? APIError)?.message ?? M2L10n.value("common.error.delete")
            return false
        }
    }

    func postComment(_ text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        do {
            _ = try await api.request(
                ContentDTOs.CommentNode.self,
                "POST",
                "/albums/\(albId)/comments",
                body: WriteDTOs.CommentCreate(content: trimmed)
            )
            message = M2L10n.value("comment.sent")
            await load()
        } catch {
            message = (error as? APIError)?.message ?? M2L10n.value("common.error.save")
        }
    }
}

struct AlbumDetailView: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss
    @State private var model: AlbumDetailViewModel?
    @State private var editorPresented = false
    @State private var deleteDialogPresented = false
    @State private var commentText = ""
    let api: LoveAPIClient
    let albId: String

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("albums.detail")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = AlbumDetailViewModel(api: api, albId: albId)
                Task { await model?.load() }
            }
        }
    }

    private func content(_ model: AlbumDetailViewModel) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error, model.detail == nil {
                    LoveErrorView(message: error) {
                        Task { await model.load() }
                    }
                } else if let detail = model.detail {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(detail.title)
                            .font(.title2.bold())
                            .foregroundStyle(LoveTheme.text)
                        HStack(spacing: 8) {
                            Text("albums.count \(detail.mediaCount)")
                            Text("·")
                            Text(Format.date(detail.createdAt))
                        }
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                    }
                    if let description = detail.description, !description.isEmpty {
                        Text(description)
                            .font(.subheadline)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    ForEach(detail.mediaItems) { media in
                        mediaView(media)
                    }
                    if !detail.comments.isEmpty {
                        LoveSoftCard {
                            LoveSectionTitle(textKey: "article.comments.title")
                            ForEach(detail.comments) { comment in
                                CommentRowView(comment: comment, depth: 0)
                            }
                        }
                    }
                } else if model.loading {
                    LoveLoadingView()
                }
            }
            .padding(16)
        }
        .safeAreaInset(edge: .bottom) {
            if model.detail != nil {
                M2CommentBar(text: $commentText) {
                    let text = commentText
                    commentText = ""
                    Task { await model.postComment(text) }
                }
            }
        }
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button {
                    editorPresented = true
                } label: {
                    Image(systemName: "square.and.pencil")
                }
                Button {
                    deleteDialogPresented = true
                } label: {
                    Image(systemName: "trash")
                        .foregroundStyle(LoveTheme.rose)
                }
            }
        }
        .sheet(isPresented: $editorPresented) {
            AlbumEditorSheet(
                editing: model.detail.map(AlbumEditorDraft.init(detail:)),
                api: api,
                saving: model.saving
            ) { draft, uploads in
                await model.update(draft, newUploads: uploads)
            }
        }
        .confirmationDialog(
            Text(M2L10n.value("albums.delete.confirm")),
            isPresented: $deleteDialogPresented,
            titleVisibility: .visible
        ) {
            Button(M2L10n.value("common.delete"), role: .destructive) {
                Task {
                    if await model.delete() { dismiss() }
                }
            }
            Button(M2L10n.value("common.cancel"), role: .cancel) {}
        }
    }

    @ViewBuilder
    private func mediaView(_ media: ContentDTOs.AlbumMedia) -> some View {
        if media.isLocked {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(LoveTheme.outline.opacity(0.35))
                .frame(height: 220)
                .overlay {
                    Label("albums.media.locked", systemImage: "lock.fill")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
        } else if media.isVideo {
            LoveAsyncImage(url: ServerSettings.mediaURL(media.thumbnailUrl ?? media.fileUrl))
                .frame(height: 220)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay {
                    Image(systemName: "play.circle.fill")
                        .font(.largeTitle)
                        .foregroundStyle(.white.opacity(0.9))
                }
        } else {
            LoveAsyncImage(url: ServerSettings.mediaURL(media.fileUrl))
                .frame(height: 240)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
    }
}
