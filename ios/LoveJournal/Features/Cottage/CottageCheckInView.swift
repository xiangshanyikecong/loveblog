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
final class CheckInViewModel {
    private(set) var loading = true
    private(set) var items: [CottageDTOs.CheckIn] = []
    private(set) var total = 0
    private(set) var hasNext = false
    private(set) var loadingMore = false
    var message: String?
    var error: String?

    // Editor draft state (photos upload immediately; the paths wait for submit).
    private(set) var draftMediaUrls: [String] = []
    private(set) var uploading = false
    private(set) var submitting = false

    private var page = 1
    private let pageSize = 20
    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        do {
            let list = try await api.request(
                CottageDTOs.CheckInList.self, "GET", "/checkins",
                query: [
                    URLQueryItem(name: "page", value: "1"),
                    URLQueryItem(name: "page_size", value: String(pageSize)),
                ]
            )
            items = list.items
            total = list.total
            hasNext = list.hasNext
            page = 1
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? String(localized: "cottage.error.generic")
        }
        loading = false
    }

    func loadMore() async {
        guard hasNext, !loadingMore else { return }
        loadingMore = true
        defer { loadingMore = false }
        do {
            let list = try await api.request(
                CottageDTOs.CheckInList.self, "GET", "/checkins",
                query: [
                    URLQueryItem(name: "page", value: String(page + 1)),
                    URLQueryItem(name: "page_size", value: String(pageSize)),
                ]
            )
            let known = Set(items.map(\.cid))
            items.append(contentsOf: list.items.filter { !known.contains($0.cid) })
            page = list.page
            hasNext = list.hasNext
        } catch {
            message = (error as? APIError)?.message ?? String(localized: "cottage.error.generic")
        }
    }

    // MARK: Editor draft

    func resetDraft() {
        draftMediaUrls = []
    }

    func uploadPhoto(_ data: Data) async {
        guard !uploading else { return }
        uploading = true
        defer { uploading = false }
        do {
            let uploaded = try await MediaUploadService.uploadImage(
                data, path: MediaUploadService.checkinPath, api: api
            )
            draftMediaUrls.append(uploaded.url)
        } catch {
            message = (error as? APIError)?.message ?? String(localized: "cottage.checkin.upload.failed")
        }
    }

    func removeDraftPhoto(at index: Int) {
        guard draftMediaUrls.indices.contains(index) else { return }
        draftMediaUrls.remove(at: index)
    }

    /// Returns true when the sheet should close.
    func submit(content: String) async -> Bool {
        let trimmed = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty || !draftMediaUrls.isEmpty else {
            message = String(localized: "cottage.checkin.need.content")
            return false
        }
        submitting = true
        defer { submitting = false }
        let body = CottageDTOs.CheckInCreate(
            content: trimmed.isEmpty ? nil : trimmed,
            mediaUrls: draftMediaUrls
        )
        do {
            _ = try await api.requestVoid(
                "POST", "/checkins",
                body: body, headers: ["Idempotency-Key": UUID().uuidString]
            )
            message = String(localized: "cottage.checkin.sent")
            resetDraft()
            await refresh()
            return true
        } catch {
            message = (error as? APIError)?.message ?? String(localized: "cottage.checkin.send.failed")
            return false
        }
    }
}

struct CottageCheckInView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: CheckInViewModel?
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
        .navigationTitle("cottage.checkin.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = CheckInViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
        .sheet(isPresented: $editorPresented) {
            if let model {
                CheckInEditorSheet(model: model)
            }
        }
    }

    private func content(_ model: CheckInViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error, model.items.isEmpty {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else if model.items.isEmpty {
                    LoveEmptyState(
                        systemImage: "location.circle",
                        titleKey: "cottage.checkin.empty",
                        messageKey: "cottage.checkin.empty.hint"
                    )
                } else {
                    ForEach(model.items) { item in
                        checkInCard(item)
                    }
                    if model.hasNext {
                        Button {
                            Task { await model.loadMore() }
                        } label: {
                            if model.loadingMore {
                                ProgressView().tint(LoveTheme.primaryAccessible)
                            } else {
                                Text("cottage.checkin.load.more")
                                    .font(.footnote.weight(.medium))
                                    .foregroundStyle(LoveTheme.primaryAccessible)
                            }
                        }
                        .padding(.vertical, 8)
                    }
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
        .overlay(alignment: .bottomTrailing) {
            Button {
                model.resetDraft()
                editorPresented = true
            } label: {
                Label("cottage.checkin.new", systemImage: "plus")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(LoveTheme.gradient, in: Capsule())
                    .shadow(color: LoveTheme.rose.opacity(0.35), radius: 8, y: 3)
            }
            .padding(20)
        }
    }

    private func checkInCard(_ item: CottageDTOs.CheckIn) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 6) {
                    Image(systemName: "person.crop.circle")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.primaryAccessible)
                    Text(item.authorNickname)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.text)
                    Spacer()
                    Text(Format.dateTime(item.createdAt))
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                if let content = item.content, !content.isEmpty {
                    Text(content)
                        .font(.subheadline)
                        .foregroundStyle(LoveTheme.text)
                }
                if !item.mediaUrls.isEmpty {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(item.mediaUrls, id: \.self) { path in
                                LoveAsyncImage(url: ServerSettings.mediaURL(path))
                                    .frame(width: 110, height: 110)
                                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                            }
                        }
                    }
                }
                locationLine(item)
            }
        }
    }

    @ViewBuilder
    private func locationLine(_ item: CottageDTOs.CheckIn) -> some View {
        // resolved | permission_denied | lookup_failed | omitted
        switch item.locationStatus {
        case "resolved":
            Label {
                Text(item.locationText ?? "")
                    .lineLimit(1)
            } icon: {
                Image(systemName: "mappin.and.ellipse")
            }
            .font(.caption)
            .foregroundStyle(LoveTheme.secondaryText)
        case "permission_denied":
            Label("cottage.checkin.location.denied", systemImage: "location.slash")
                .font(.caption)
                .foregroundStyle(LoveTheme.secondaryText)
        case "lookup_failed":
            Label("cottage.checkin.location.failed", systemImage: "questionmark.circle")
                .font(.caption)
                .foregroundStyle(LoveTheme.secondaryText)
        default:
            EmptyView()
        }
    }
}

// MARK: - Editor sheet

private struct CheckInEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: CheckInViewModel

    @State private var content = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: "cottage.checkin.content") {
                        TextField("cottage.checkin.content.placeholder", text: $content, axis: .vertical)
                            .lineLimit(3...6)
                    }
                    LoveSectionTitle(textKey: "cottage.checkin.photos")
                    HStack(spacing: 12) {
                        LoveImagePicker { data in
                            Task { await model.uploadPhoto(data) }
                        }
                        if model.uploading {
                            ProgressView()
                                .tint(LoveTheme.primaryAccessible)
                        }
                    }
                    if !model.draftMediaUrls.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(Array(model.draftMediaUrls.enumerated()), id: \.element) { index, path in
                                    ZStack(alignment: .topTrailing) {
                                        LoveAsyncImage(url: ServerSettings.mediaURL(path))
                                            .frame(width: 84, height: 84)
                                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                                        Button {
                                            model.removeDraftPhoto(at: index)
                                        } label: {
                                            Image(systemName: "xmark.circle.fill")
                                                .font(.footnote)
                                                .foregroundStyle(.white)
                                                .shadow(radius: 2)
                                        }
                                        .padding(4)
                                    }
                                }
                            }
                        }
                    }
                    if let message = model.message {
                        LoveErrorBanner(message: message)
                    }
                    LovePrimaryButton(
                        titleKey: "cottage.checkin.send",
                        loading: model.submitting || model.uploading
                    ) {
                        let text = content
                        Task {
                            if await model.submit(content: text) {
                                dismiss()
                            }
                        }
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle("cottage.checkin.new")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("common.cancel") {
                        model.resetDraft()
                        dismiss()
                    }
                }
            }
        }
        .presentationDetents([.large])
    }
}
