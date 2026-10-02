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

/// Server-side cap on moment media (`MomentCreateRequest._MAX_MEDIA_URLS`).
private let momentImageLimit = 9

@MainActor
@Observable
final class TimelineViewModel {
    enum Tab: Hashable {
        case moments
        case memories
    }

    var loading = true
    var error: String?
    var moments: [ContentDTOs.Moment] = []
    var selectedTab: Tab = .moments
    var memories: [ContentDTOs.Moment]?
    var memoriesLoading = false
    var memoriesError: String?
    var message: String?
    var posting = false
    var commenting = false
    var selfUid: String?

    private let api: LoveAPIClient

    init(api: LoveAPIClient, selfUid: String?) {
        self.api = api
        self.selfUid = selfUid
    }

    func refresh() async {
        if moments.isEmpty { loading = true }
        do {
            let list = try await api.request(
                ContentDTOs.TimelineList.self,
                "GET",
                "/timeline",
                query: [
                    URLQueryItem(name: "page", value: "1"),
                    URLQueryItem(name: "page_size", value: "20"),
                    URLQueryItem(name: "sort", value: "desc"),
                ]
            )
            moments = list.items
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? "加载失败，请稍后重试"
        }
        loading = false
    }

    func selectTab(_ tab: Tab) async {
        selectedTab = tab
        if tab == .memories, memories == nil, !memoriesLoading {
            memoriesLoading = true
            defer { memoriesLoading = false }
            do {
                memories = try await api.request(
                    [ContentDTOs.Moment].self, "GET", "/timeline/memories"
                )
                memoriesError = nil
            } catch {
                memoriesError = (error as? APIError)?.message ?? "加载失败，请稍后重试"
            }
        }
    }

    /// Uploads every image first — any failure aborts the post — then creates
    /// the moment with the collected media URLs. Returns nil on success.
    func post(content: String, images: [Data], visibility: String) async -> String? {
        let text = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty || !images.isEmpty else { return nil }
        posting = true
        defer { posting = false }
        var mediaUrls: [String] = []
        for image in images {
            do {
                let upload = try await MediaUploadService.uploadImage(
                    image, path: MediaUploadService.timelinePath, api: api
                )
                mediaUrls.append(upload.url)
            } catch {
                return (error as? APIError)?.message ?? M2L10n.value("timeline.upload.failed")
            }
        }
        do {
            let key = UUID().uuidString
            let moment = try await api.request(
                ContentDTOs.Moment.self,
                "POST",
                "/timeline",
                body: ContentDTOs.MomentCreate(
                    content: text,
                    mediaUrls: mediaUrls,
                    visibility: visibility
                ),
                headers: ["Idempotency-Key": key]
            )
            moments.insert(moment, at: 0)
            message = M2L10n.value("timeline.composer.posted")
            return nil
        } catch {
            return (error as? APIError)?.message ?? M2L10n.value("common.error.save")
        }
    }

    /// Comments on a moment, then refreshes the timeline. Returns nil on
    /// success, otherwise a user-presentable error message.
    func comment(_ moment: ContentDTOs.Moment, content: String) async -> String? {
        let trimmed = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        commenting = true
        defer { commenting = false }
        do {
            _ = try await api.request(
                ContentDTOs.CommentNode.self,
                "POST",
                "/timeline/\(moment.mid)/comments",
                body: WriteDTOs.CommentCreate(content: trimmed)
            )
            message = M2L10n.value("comment.sent")
            await refresh()
            return nil
        } catch {
            return (error as? APIError)?.message ?? M2L10n.value("common.error.save")
        }
    }

    func delete(_ moment: ContentDTOs.Moment) async {
        do {
            try await api.requestVoid("DELETE", "/timeline/\(moment.mid)")
            moments.removeAll { $0.mid == moment.mid }
            message = "已删除"
        } catch {
            message = (error as? APIError)?.message ?? "删除失败，请稍后重试"
        }
    }
}

/// Named `TimelineScreenView` to avoid clashing with SwiftUI's `TimelineView`.
struct TimelineScreenView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: TimelineViewModel?
    @State private var composerPresented = false
    @State private var commentingMoment: ContentDTOs.Moment?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("timeline.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                let uid: String?
                if case .loggedIn(let profile) = environment.session.state {
                    uid = profile.uid
                } else {
                    uid = nil
                }
                model = TimelineViewModel(api: environment.api, selfUid: uid)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: TimelineViewModel) -> some View {
        VStack(spacing: 0) {
            if let message = model.message {
                LoveSuccessBanner(message: message)
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
            }
            Picker("timeline.tab", selection: Binding(
                get: { model.selectedTab },
                set: { tab in Task { await model.selectTab(tab) } }
            )) {
                Text("timeline.tab.moments").tag(TimelineViewModel.Tab.moments)
                Text("timeline.tab.memories").tag(TimelineViewModel.Tab.memories)
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            switch model.selectedTab {
            case .moments:
                momentsTab(model)
            case .memories:
                memoriesTab(model)
            }
        }
        .refreshable {
            if model.selectedTab == .moments {
                await model.refresh()
            } else {
                model.memories = nil
                await model.selectTab(.memories)
            }
        }
        .sheet(isPresented: $composerPresented) {
            MomentComposerSheet(model: model)
                .presentationDetents([.medium, .large])
        }
        .sheet(item: $commentingMoment) { moment in
            MomentCommentSheet(model: model, moment: moment)
                .presentationDetents([.medium])
        }
    }

    private func momentsTab(_ model: TimelineViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let error = model.error, model.moments.isEmpty {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else if model.moments.isEmpty {
                    LoveEmptyState(
                        systemImage: "sparkles",
                        titleKey: "timeline.empty",
                        messageKey: "timeline.empty.hint"
                    )
                } else {
                    ForEach(model.moments) { moment in
                        MomentCard(
                            moment: moment,
                            showDelete: true,
                            selfUid: model.selfUid,
                            onDelete: {
                                Task { await model.delete(moment) }
                            },
                            onComment: { _ in
                                commentingMoment = moment
                            }
                        )
                    }
                }
            }
            .padding(16)
        }
        .overlay(alignment: .bottomTrailing) {
            Button {
                composerPresented = true
            } label: {
                Image(systemName: "plus")
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(.white)
                    .frame(width: 46, height: 46)
                    .background(LoveTheme.gradient, in: Circle())
                    .shadow(color: LoveTheme.rose.opacity(0.35), radius: 8, y: 3)
            }
            .padding(20)
        }
    }

    private func memoriesTab(_ model: TimelineViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let memories = model.memories {
                    if memories.isEmpty {
                        LoveEmptyState(
                            systemImage: "clock.arrow.circlepath",
                            titleKey: "timeline.memories.empty",
                            messageKey: "timeline.memories.empty.hint"
                        )
                    } else {
                        ForEach(memories) { moment in
                            MomentCard(moment: moment, showDelete: false, selfUid: nil, onDelete: nil)
                        }
                    }
                } else if model.memoriesLoading {
                    LoveLoadingView()
                } else if let error = model.memoriesError {
                    LoveErrorView(message: error) {
                        Task { await model.selectTab(.memories) }
                    }
                }
            }
            .padding(16)
        }
    }
}

/// Shared moment card (moments + memories tabs).
struct MomentCard: View {
    let moment: ContentDTOs.Moment
    let showDelete: Bool
    let selfUid: String?
    let onDelete: (() -> Void)?
    var onComment: ((ContentDTOs.Moment) -> Void)?

    private var visibilityLabel: String {
        switch moment.visibility {
        case "Public": return String(localized: "moment.visibility.public")
        case "Encrypted": return String(localized: "moment.visibility.encrypted")
        default: return String(localized: "moment.visibility.partners")
        }
    }

    var body: some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Text(moment.authorNickname)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(LoveTheme.primaryAccessible)
                    Text("\(Format.dateTime(moment.timestamp)) · \(visibilityLabel)")
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                    Spacer()
                    if showDelete {
                        Button {
                            onDelete?()
                        } label: {
                            Image(systemName: "trash")
                                .font(.caption)
                                .foregroundStyle(LoveTheme.rose.opacity(0.8))
                        }
                        .buttonStyle(.plain)
                    }
                }
                if !moment.content.isEmpty {
                    Text(moment.content)
                        .font(.subheadline)
                        .foregroundStyle(LoveTheme.text)
                }
                if !moment.mediaUrls.isEmpty {
                    if moment.mediaUrls.count == 1 {
                        LoveThumbImage(path: moment.mediaUrls[0])
                            .frame(height: 200)
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    } else {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(moment.mediaUrls, id: \.self) { path in
                                    LoveThumbImage(path: path)
                                        .frame(width: 130, height: 170)
                                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                                }
                            }
                        }
                    }
                }
                if moment.audioUrl != nil, let duration = moment.audioDurationSec {
                    Label("moment.audio \(duration)", systemImage: "waveform")
                        .font(.caption)
                        .foregroundStyle(LoveTheme.mint)
                }
                if let location = moment.location, !location.isEmpty {
                    Label(location, systemImage: "mappin.and.ellipse")
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                if !moment.tags.isEmpty {
                    Text(moment.tags.map { "#\($0)" }.joined(separator: " "))
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.primaryAccessible.opacity(0.8))
                }
                if moment.commentCount > 0 || onComment != nil {
                    HStack(spacing: 10) {
                        if moment.commentCount > 0 {
                            Text("moment.comments.count \(moment.commentCount)")
                                .font(.caption2)
                                .foregroundStyle(LoveTheme.secondaryText)
                        }
                        Spacer()
                        if let onComment {
                            Button {
                                onComment(moment)
                            } label: {
                                Label {
                                    Text(.init(m2: "comment.title"))
                                } icon: {
                                    Image(systemName: "bubble.right")
                                }
                                .font(.caption)
                                .foregroundStyle(LoveTheme.primaryAccessible)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }
}

struct MomentComposerSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: TimelineViewModel

    @State private var content = ""
    @State private var isPublic = false
    @State private var images: [Data] = []
    @State private var error: String?

    private var canPost: Bool {
        !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !images.isEmpty
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: "timeline.composer.content") {
                        TextField("timeline.composer.placeholder", text: $content, axis: .vertical)
                            .lineLimit(4...10)
                    }
                    Picker("timeline.composer.visibility", selection: $isPublic) {
                        Text("moment.visibility.partners").tag(false)
                        Text("moment.visibility.public").tag(true)
                    }
                    .pickerStyle(.segmented)
                    imageSection
                    if let error {
                        LoveErrorBanner(message: error)
                    }
                    LovePrimaryButton(
                        titleKey: "timeline.composer.post",
                        loading: model.posting,
                        enabled: canPost
                    ) {
                        let text = content
                        let visibility = isPublic ? "Public" : "PartnersOnly"
                        let picked = images
                        Task {
                            if let failure = await model.post(
                                content: text, images: picked, visibility: visibility
                            ) {
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
            .navigationTitle("timeline.composer.title")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("common.cancel") { dismiss() }
                }
            }
        }
    }

    private var imageSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                LoveImagePicker { data in
                    if images.count < momentImageLimit {
                        images.append(data)
                    }
                }
                Text("timeline.composer.images.max \(momentImageLimit)", tableName: "M2")
                    .font(.caption2)
                    .foregroundStyle(LoveTheme.secondaryText)
                Spacer()
                if !images.isEmpty {
                    Text("timeline.composer.images.count \(images.count)", tableName: "M2")
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
            }
            if !images.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(Array(images.enumerated()), id: \.offset) { index, data in
                            pickedThumb(data) {
                                images.remove(at: index)
                            }
                        }
                    }
                }
            }
        }
    }

    private func pickedThumb(_ data: Data, onRemove: @escaping () -> Void) -> some View {
        Group {
            if let image = UIImage(data: data) {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
            } else {
                Color.clear
            }
        }
        .frame(width: 76, height: 76)
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
}

struct MomentCommentSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: TimelineViewModel
    let moment: ContentDTOs.Moment

    @State private var text = ""
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: .init(m2: "comment.title")) {
                        TextField(M2L10n.value("comment.placeholder"), text: $text, axis: .vertical)
                            .lineLimit(3...8)
                    }
                    if let error {
                        LoveErrorBanner(message: error)
                    }
                    LovePrimaryButton(
                        titleKey: .init(m2: "comment.send"),
                        loading: model.commenting
                    ) {
                        let content = text
                        Task {
                            if let failure = await model.comment(moment, content: content) {
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
            .navigationTitle(.init(m2: "moment.comment.title"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(M2L10n.value("common.cancel")) { dismiss() }
                }
            }
        }
    }
}
