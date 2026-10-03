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
final class SearchViewModel {
    enum Mode: Hashable {
        case keyword
        case semantic
    }

    var query = ""
    var mode: Mode = .keyword
    var loading = false
    var results: [ContentDTOs.SearchResultItem] = []
    var total = 0
    var searched = false
    var error: String?

    /// AI semantic search state (visible only when status supports it).
    private(set) var aiStatus: AIDTOs.Status?
    var aiResults: [AIDTOs.SemanticSearchResult] = []
    var aiIndexedCount = 0

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func loadAIStatusIfNeeded() async {
        guard aiStatus == nil else { return }
        aiStatus = try? await api.aiStatus()
        if aiStatus?.supports(AIDTOs.Feature.semanticSearch) != true {
            mode = .keyword
        }
    }

    func search() async {
        let trimmed = query.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        loading = true
        switch mode {
        case .keyword:
            do {
                let response = try await api.request(
                    ContentDTOs.SearchResponse.self,
                    "GET",
                    "/search",
                    query: [
                        URLQueryItem(name: "q", value: trimmed),
                        URLQueryItem(name: "page", value: "1"),
                        URLQueryItem(name: "page_size", value: "20"),
                    ]
                )
                results = response.items
                total = response.total
                searched = true
                error = nil
            } catch {
                self.error = (error as? APIError)?.message ?? "搜索失败，请稍后重试"
            }
        case .semantic:
            do {
                let response = try await api.aiSemanticSearch(query: trimmed, topK: 5)
                aiResults = response.results
                aiIndexedCount = response.indexedCount
                searched = true
                error = nil
            } catch {
                self.error = AIFeature.message(for: error)
            }
        }
        loading = false
    }

    static func typeLabel(_ type: String) -> String {
        switch type {
        case "article": return String(localized: "search.type.article")
        case "album": return String(localized: "search.type.album")
        case "event": return String(localized: "search.type.event")
        case "moment": return String(localized: "search.type.moment")
        case "message": return String(localized: "search.type.message")
        default: return type
        }
    }
}

struct SearchView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: SearchViewModel?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("search.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = SearchViewModel(api: environment.api)
            }
            Task { await model?.loadAIStatusIfNeeded() }
        }
    }

    private func content(_ model: SearchViewModel) -> some View {
        VStack(spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(LoveTheme.secondaryText)
                TextField("search.placeholder", text: Binding(
                    get: { model.query },
                    set: { model.query = $0 }
                ))
                .submitLabel(.search)
                .onSubmit {
                    Task { await model.search() }
                }
                if !model.query.isEmpty {
                    Button {
                        model.query = ""
                        model.searched = false
                        model.results = []
                        model.aiResults = []
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                }
            }
            .font(.subheadline)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(LoveTheme.surface, in: RoundedRectangle(cornerRadius: 14))
            .overlay {
                RoundedRectangle(cornerRadius: 14)
                    .stroke(LoveTheme.outline, lineWidth: 1)
            }
            .padding(.horizontal, 16)

            if model.aiStatus?.supports(AIDTOs.Feature.semanticSearch) == true {
                Picker("search.mode", selection: Binding(
                    get: { model.mode },
                    set: { model.mode = $0 }
                )) {
                    Text("search.mode.keyword").tag(SearchViewModel.Mode.keyword)
                    Text("search.mode.semantic").tag(SearchViewModel.Mode.semantic)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, 16)
            }

            ScrollView {
                VStack(spacing: 10) {
                    if model.loading {
                        LoveLoadingView()
                    } else if let error = model.error {
                        LoveErrorView(message: error) {
                            Task { await model.search() }
                        }
                    } else if !model.searched {
                        LoveEmptyState(
                            systemImage: "magnifyingglass",
                            titleKey: model.mode == .semantic ? "search.semantic.idle.title" : "search.idle.title",
                            messageKey: model.mode == .semantic ? "search.semantic.idle.hint" : "search.idle.hint"
                        )
                    } else if model.mode == .semantic {
                        semanticResults(model)
                    } else if model.results.isEmpty {
                        LoveEmptyState(
                            systemImage: "tray",
                            titleKey: "search.empty",
                            messageKey: "search.empty.hint"
                        )
                    } else {
                        Text("search.total \(model.total)")
                            .font(.caption)
                            .foregroundStyle(LoveTheme.secondaryText)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        ForEach(model.results) { item in
                            resultCard(item)
                        }
                    }
                }
                .padding(16)
            }
        }
        .navigationDestination(for: ArticleRoute.self) { route in
            ArticleDetailView(api: environment.api, aid: route.aid)
        }
    }

    // MARK: Semantic (AI) results

    @ViewBuilder
    private func semanticResults(_ model: SearchViewModel) -> some View {
        if model.aiResults.isEmpty {
            LoveEmptyState(
                systemImage: "sparkle.magnifyingglass",
                titleKey: "search.empty",
                messageKey: "search.empty.hint"
            )
        } else {
            Text("search.semantic.indexed \(model.aiIndexedCount)")
                .font(.caption)
                .foregroundStyle(LoveTheme.secondaryText)
                .frame(maxWidth: .infinity, alignment: .leading)
            ForEach(model.aiResults) { item in
                NavigationLink(value: ArticleRoute(aid: item.aid)) {
                    semanticCard(item)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func semanticCard(_ item: AIDTOs.SemanticSearchResult) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 8) {
                    LovePill(text: SearchViewModel.typeLabel("article"))
                    LovePill(
                        text: String(localized: "search.similarity \(Int((item.score * 100).rounded()))"),
                        tint: LoveTheme.lavender
                    )
                    if let updatedAt = item.updatedAt {
                        Text(Format.date(updatedAt))
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                }
                Text(item.title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                    .lineLimit(2)
                Text(item.snippet)
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
                    .lineLimit(3)
            }
        }
    }

    private func resultCard(_ item: ContentDTOs.SearchResultItem) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 8) {
                    LovePill(text: SearchViewModel.typeLabel(item.type))
                    Text(Format.date(item.date))
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                    if item.isEncrypted {
                        Image(systemName: "lock.fill")
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.lavender)
                    }
                }
                Text(item.title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                    .lineLimit(2)
                Text(item.snippet)
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
                    .lineLimit(3)
                if let author = item.authorNickname {
                    Text("search.by \(author)")
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
            }
        }
    }
}
