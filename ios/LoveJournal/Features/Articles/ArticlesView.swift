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

/// Route value pushed from the article list to its detail.
struct ArticleRoute: Hashable {
    let aid: String
}

// MARK: - Editor draft

/// Plain-text editor draft shared by the create sheet (list FAB) and the
/// edit sheet (detail toolbar). Body text is flattened to/from a single
/// Paragraph block — the server accepts full-block replacement on PUT.
struct ArticleEditorDraft {
    var title = ""
    var excerpt = ""
    var body = ""
    var tags: [String] = []
    var isPublished = false
    var visibility = "public"

    init() {}

    init(detail: ContentDTOs.ArticleDetail) {
        title = detail.title
        excerpt = detail.excerpt ?? ""
        body = detail.sortedBlocks.map(\.content).joined(separator: "\n\n")
        tags = detail.tags
        isPublished = detail.isPublished
        visibility = detail.visibility
    }

    func payload(existing: ContentDTOs.ArticleDetail?) -> WriteDTOs.ArticleUpsert {
        let trimmedExcerpt = excerpt.trimmingCharacters(in: .whitespacesAndNewlines)
        return WriteDTOs.ArticleUpsert(
            title: title.trimmingCharacters(in: .whitespacesAndNewlines),
            excerpt: trimmedExcerpt.isEmpty ? nil : trimmedExcerpt,
            status: isPublished ? "Published" : "Draft",
            visibility: visibility,
            tags: tags,
            blocks: [
                WriteDTOs.ArticleBlockInput(
                    blockType: "Paragraph",
                    content: body.trimmingCharacters(in: .whitespacesAndNewlines),
                    sortOrder: 0
                )
            ],
            isEncrypted: existing?.isEncrypted ?? false,
            isCoCreated: existing?.isCoCreated ?? false,
            partnerCanEdit: existing?.partnerCanEdit ?? false
        )
    }
}

// MARK: - List

@MainActor
@Observable
final class ArticlesViewModel {
    var loading = true
    var error: String?
    var articles: [ContentDTOs.ArticleSummary] = []
    var message: String?
    var saving = false

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        if articles.isEmpty { loading = true }
        do {
            let page = try await api.request(
                ContentDTOs.Page<ContentDTOs.ArticleSummary>.self,
                "GET",
                "/articles",
                query: [URLQueryItem(name: "only_published", value: "false")]
            )
            articles = page.items
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? "加载失败，请稍后重试"
        }
        loading = false
    }

    /// Returns nil on success, otherwise a user-presentable error message.
    func create(_ draft: ArticleEditorDraft) async -> String? {
        saving = true
        defer { saving = false }
        do {
            _ = try await api.request(
                ContentDTOs.ArticleDetail.self, "POST", "/articles", body: draft.payload(existing: nil)
            )
            message = M2L10n.value("common.saved")
            await refresh()
            return nil
        } catch {
            return (error as? APIError)?.message ?? M2L10n.value("common.error.save")
        }
    }
}

struct ArticlesView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: ArticlesViewModel?
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
        .navigationTitle("tab.articles")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = ArticlesViewModel(api: environment.api)
            }
            // Also covers returning from a deleted article's detail screen.
            Task { await model?.refresh() }
        }
    }

    private func content(_ model: ArticlesViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error, model.articles.isEmpty {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else if model.articles.isEmpty {
                    LoveEmptyState(
                        systemImage: "doc.text",
                        titleKey: "articles.empty",
                        messageKey: "articles.empty.hint"
                    )
                } else {
                    ForEach(model.articles) { article in
                        NavigationLink(value: ArticleRoute(aid: article.aid)) {
                            articleCard(article)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
        .navigationDestination(for: ArticleRoute.self) { route in
            ArticleDetailView(api: environment.api, aid: route.aid)
        }
        .overlay(alignment: .bottomTrailing) {
            Button {
                editorPresented = true
            } label: {
                Label {
                    Text(.init(m2: "articles.write"))
                } icon: {
                    Image(systemName: "square.and.pencil")
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
            ArticleEditorSheet(editing: nil, saving: model.saving) { draft in
                await model.create(draft)
            }
        }
    }

    private func articleCard(_ article: ContentDTOs.ArticleSummary) -> some View {
        LoveSoftCard {
            HStack(spacing: 12) {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(LoveTheme.gradient)
                    .frame(width: 72, height: 72)
                    .overlay {
                        Image(systemName: "text.book.closed.fill")
                            .foregroundStyle(.white.opacity(0.9))
                    }
                VStack(alignment: .leading, spacing: 5) {
                    HStack(spacing: 6) {
                        Text(article.title)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.text)
                            .lineLimit(1)
                        if !article.isPublished {
                            LovePill(text: String(localized: "article.status.draft"), tint: LoveTheme.secondaryText)
                        }
                        if article.isEncrypted {
                            Image(systemName: "lock.fill")
                                .font(.caption2)
                                .foregroundStyle(LoveTheme.lavender)
                        }
                    }
                    if let excerpt = article.excerpt, !excerpt.isEmpty {
                        Text(excerpt)
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText)
                            .lineLimit(2)
                    }
                    HStack(spacing: 6) {
                        Text(article.authorNickname)
                        Text("·")
                        Text(Format.date(article.publishedAt ?? article.createdAt))
                        ForEach(article.tags.prefix(3), id: \.self) { tag in
                            Text("#\(tag)")
                        }
                    }
                    .font(.caption2)
                    .foregroundStyle(LoveTheme.secondaryText)
                }
            }
        }
    }
}

// MARK: - Editor sheet

struct ArticleEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    /// nil = create a new article.
    let editing: ArticleEditorDraft?
    let saving: Bool
    let onSave: (ArticleEditorDraft) async -> String?

    private enum VisibilityChoice: String, CaseIterable, Identifiable {
        case open = "public"
        case partnersOnly = "partners_only"

        var id: String { rawValue }
    }

    @State private var title = ""
    @State private var excerpt = ""
    @State private var bodyText = ""
    @State private var tagsText = ""
    @State private var isPublished = false
    @State private var visibilityChoice = VisibilityChoice.open
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: .init(m2: "articles.editor.title")) {
                        TextField(M2L10n.value("articles.editor.title"), text: $title)
                    }
                    LoveField(labelKey: .init(m2: "articles.editor.excerpt")) {
                        TextField(M2L10n.value("articles.editor.excerpt"), text: $excerpt)
                    }
                    LoveField(labelKey: .init(m2: "articles.editor.body")) {
                        TextField(
                            M2L10n.value("articles.editor.body.placeholder"),
                            text: $bodyText,
                            axis: .vertical
                        )
                        .lineLimit(6...14)
                    }
                    LoveField(labelKey: .init(m2: "articles.editor.tags")) {
                        TextField(M2L10n.value("articles.editor.tags"), text: $tagsText)
                    }
                    Picker(.init(m2: "articles.editor.visibility"), selection: $visibilityChoice) {
                        Text(.init(m2: "articles.visibility.public")).tag(VisibilityChoice.open)
                        Text(.init(m2: "articles.visibility.partners_only")).tag(VisibilityChoice.partnersOnly)
                    }
                    .pickerStyle(.segmented)
                    Toggle(isOn: $isPublished) {
                        Text(.init(m2: "articles.editor.published"))
                    }
                    .tint(LoveTheme.primaryAccessible)
                    if let error {
                        LoveErrorBanner(message: error)
                    }
                    LovePrimaryButton(
                        titleKey: editing == nil ? .init(m2: "articles.write") : "common.save",
                        loading: saving
                    ) {
                        save()
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(editing == nil ? .init(m2: "articles.write") : .init(m2: "articles.edit"))
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
                excerpt = editing.excerpt
                bodyText = editing.body
                tagsText = editing.tags.joined(separator: ", ")
                isPublished = editing.isPublished
                visibilityChoice = VisibilityChoice(rawValue: editing.visibility) ?? .open
            }
        }
    }

    private func save() {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty else {
            error = M2L10n.value("articles.editor.title.required")
            return
        }
        let trimmedBody = bodyText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedBody.isEmpty else {
            error = M2L10n.value("articles.editor.body.required")
            return
        }
        var draft = editing ?? ArticleEditorDraft()
        draft.title = trimmedTitle
        draft.excerpt = excerpt
        draft.body = trimmedBody
        draft.tags = M2Support.parseTags(tagsText)
        draft.isPublished = isPublished
        draft.visibility = visibilityChoice.rawValue
        Task {
            if let failure = await onSave(draft) {
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
final class ArticleDetailViewModel {
    var loading = true
    var error: String?
    var detail: ContentDTOs.ArticleDetail?
    var message: String?
    var saving = false
    var versions: [WriteDTOs.ContentVersion]?
    var versionsLoading = false

    private let api: LoveAPIClient
    private let aid: String

    init(api: LoveAPIClient, aid: String) {
        self.api = api
        self.aid = aid
    }

    func load() async {
        loading = detail == nil
        do {
            detail = try await api.request(
                ContentDTOs.ArticleDetail.self, "GET", "/articles/\(aid)"
            )
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? "加载失败，请稍后重试"
        }
        loading = false
    }

    /// PUT with `If-Match` optimistic concurrency. A 409 reloads the detail
    /// and surfaces the conflict message. Returns nil on success.
    func update(_ draft: ArticleEditorDraft) async -> String? {
        guard let current = detail else { return nil }
        saving = true
        defer { saving = false }
        do {
            detail = try await api.request(
                ContentDTOs.ArticleDetail.self,
                "PUT",
                "/articles/\(aid)",
                body: draft.payload(existing: current),
                headers: ["If-Match": String(current.version)]
            )
            message = M2L10n.value("common.saved")
            return nil
        } catch {
            if let apiError = error as? APIError, case .http(let status, _) = apiError, status == 409 {
                message = M2L10n.value("articles.conflict")
                await load()
                return message
            }
            return (error as? APIError)?.message ?? M2L10n.value("common.error.save")
        }
    }

    /// Returns true when the detail screen should pop back to the list.
    func delete() async -> Bool {
        do {
            try await api.requestVoid("DELETE", "/articles/\(aid)")
            return true
        } catch {
            message = (error as? APIError)?.message ?? M2L10n.value("common.error.delete")
            return false
        }
    }

    func loadVersions() async {
        versionsLoading = versions == nil
        do {
            let list = try await api.request(
                WriteDTOs.ContentVersionList.self, "GET", "/articles/\(aid)/versions"
            )
            versions = list.items
        } catch {
            message = (error as? APIError)?.message ?? M2L10n.value("common.error.load")
        }
        versionsLoading = false
    }

    func rollback(to version: Int) async -> Bool {
        do {
            detail = try await api.request(
                ContentDTOs.ArticleDetail.self,
                "POST",
                "/articles/\(aid)/versions/\(version)/rollback"
            )
            message = M2L10n.value("articles.history.rollback.done")
            return true
        } catch {
            message = (error as? APIError)?.message ?? M2L10n.value("common.error.save")
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
                "/articles/\(aid)/comments",
                body: WriteDTOs.CommentCreate(content: trimmed)
            )
            message = M2L10n.value("comment.sent")
            await load()
        } catch {
            message = (error as? APIError)?.message ?? M2L10n.value("common.error.save")
        }
    }
}

struct ArticleDetailView: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss
    @State private var model: ArticleDetailViewModel?
    @State private var editorPresented = false
    @State private var historyPresented = false
    @State private var deleteDialogPresented = false
    @State private var commentText = ""
    let api: LoveAPIClient
    let aid: String

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("articles.detail")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = ArticleDetailViewModel(api: api, aid: aid)
                Task { await model?.load() }
            }
        }
    }

    private func content(_ model: ArticleDetailViewModel) -> some View {
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
                            Text(detail.authorNickname)
                            Text("·")
                            Text(Format.date(detail.publishedAt ?? detail.createdAt))
                            if !detail.isPublished {
                                LovePill(text: String(localized: "article.status.draft"), tint: LoveTheme.secondaryText)
                            }
                            ForEach(detail.tags, id: \.self) { tag in
                                Text("#\(tag)")
                            }
                        }
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                    }
                    if let excerpt = detail.excerpt, !excerpt.isEmpty {
                        Text(excerpt)
                            .font(.subheadline)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    ForEach(model.detail?.sortedBlocks ?? []) { block in
                        blockView(block)
                    }
                    if !detail.comments.isEmpty {
                        commentSection(detail.comments)
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
                    historyPresented = true
                } label: {
                    Image(systemName: "clock.arrow.circlepath")
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
            ArticleEditorSheet(
                editing: model.detail.map(ArticleEditorDraft.init(detail:)),
                saving: model.saving
            ) { draft in
                await model.update(draft)
            }
        }
        .sheet(isPresented: $historyPresented) {
            ArticleHistorySheet(model: model)
        }
        .confirmationDialog(
            Text(M2L10n.value("articles.delete.confirm")),
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
    private func blockView(_ block: ContentDTOs.ArticleBlock) -> some View {
        switch true {
        case block.isHeading:
            Text(block.content)
                .font(.headline)
                .foregroundStyle(LoveTheme.text)
                .padding(.top, 6)
        case block.isQuote:
            HStack(spacing: 8) {
                Rectangle()
                    .fill(LoveTheme.gradient)
                    .frame(width: 3)
                Text(block.content)
                    .font(.subheadline.italic())
                    .foregroundStyle(LoveTheme.secondaryText)
            }
        default:
            Text(block.content)
                .font(.body)
                .foregroundStyle(LoveTheme.text)
        }
    }

    private func commentSection(_ comments: [ContentDTOs.CommentNode]) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: "article.comments.title")
            ForEach(comments) { comment in
                CommentRowView(comment: comment, depth: 0)
            }
        }
    }
}

// MARK: - Version history sheet

struct ArticleHistorySheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: ArticleDetailViewModel
    @State private var rollbackVersion: Int?

    var body: some View {
        NavigationStack {
            Group {
                if model.versionsLoading {
                    LoveLoadingView()
                } else if let versions = model.versions, !versions.isEmpty {
                    ScrollView {
                        VStack(spacing: 10) {
                            ForEach(versions) { version in
                                versionRow(version)
                            }
                        }
                        .padding(16)
                    }
                } else {
                    LoveEmptyState(
                        systemImage: "clock.arrow.circlepath",
                        titleKey: .init(m2: "articles.history.empty")
                    )
                }
            }
            .loveScreenBackground()
            .navigationTitle(.init(m2: "articles.history"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(M2L10n.value("common.cancel")) { dismiss() }
                }
            }
        }
        .onAppear {
            Task { await model.loadVersions() }
        }
        .confirmationDialog(
            Text(M2L10n.value("articles.history.rollback.confirm")),
            isPresented: Binding(
                get: { rollbackVersion != nil },
                set: { if !$0 { rollbackVersion = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button(M2L10n.value("articles.history.rollback"), role: .destructive) {
                if let version = rollbackVersion {
                    Task {
                        if await model.rollback(to: version) { dismiss() }
                    }
                }
                rollbackVersion = nil
            }
            Button(M2L10n.value("common.cancel"), role: .cancel) {
                rollbackVersion = nil
            }
        }
    }

    private func versionRow(_ version: WriteDTOs.ContentVersion) -> some View {
        Button {
            rollbackVersion = version.version
        } label: {
            LoveSoftCard {
                HStack(alignment: .top, spacing: 12) {
                    LovePill(text: "v\(version.version)")
                    VStack(alignment: .leading, spacing: 4) {
                        if let title = version.title, !title.isEmpty {
                            Text(title)
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(LoveTheme.text)
                                .lineLimit(1)
                        }
                        if let note = version.note, !note.isEmpty {
                            Text(note)
                                .font(.footnote)
                                .foregroundStyle(LoveTheme.secondaryText)
                        }
                        HStack(spacing: 6) {
                            Text(version.actorNickname ?? version.actorUid ?? "")
                            Text("·")
                            Text(Format.dateTime(version.createdAt))
                        }
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                    }
                    Spacer()
                    Image(systemName: "arrow.uturn.backward")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.primaryAccessible.opacity(0.7))
                }
            }
        }
        .buttonStyle(.plain)
    }
}

/// Recursive comment tree renderer (article/album detail, moment cards).
struct CommentRowView: View {
    let comment: ContentDTOs.CommentNode
    let depth: Int

    private var indent: CGFloat { CGFloat(depth) * 14 }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Text(comment.authorNickname)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(LoveTheme.primaryAccessible)
                Text(Format.dateTime(comment.createdAt))
                    .font(.caption2)
                    .foregroundStyle(LoveTheme.secondaryText)
            }
            Text(comment.content)
                .font(.footnote)
                .foregroundStyle(LoveTheme.text)
            ForEach(comment.replies) { reply in
                CommentRowView(comment: reply, depth: depth + 1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.leading, indent)
        .padding(.vertical, 2)
    }
}
