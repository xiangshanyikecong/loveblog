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

@MainActor
@Observable
final class RecycleViewModel {
    enum Filter: String, CaseIterable, Identifiable {
        case all
        case article
        case album
        case event
        case moment
        case message

        var id: String { rawValue }

        /// `type=` query value (nil = every type).
        var queryValue: String? {
            self == .all ? nil : rawValue
        }

        var labelKey: String {
            self == .all ? "m6a.recycle.filter.all" : "m6a.recycle.type.\(rawValue)"
        }
    }

    private(set) var loading = true
    private(set) var working = false
    private(set) var items: [CareDTOs.RecycleItem] = []
    private(set) var total = 0
    private(set) var filter: Filter = .all
    var error: String?
    var message: String?

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func select(_ filter: Filter) async {
        guard filter != self.filter else { return }
        self.filter = filter
        await refresh()
    }

    func refresh() async {
        var query: [URLQueryItem] = []
        if let type = filter.queryValue {
            query.append(URLQueryItem(name: "type", value: type))
        }
        do {
            let page = try await api.request(
                CareDTOs.RecycleList.self, "GET", "/recycle-bin", query: query
            )
            items = page.items
            total = page.total
            error = nil
        } catch {
            self.error = M6AErrorText.describe(error)
        }
        loading = false
    }

    /// Soft-restore one item back to its module.
    func restore(_ item: CareDTOs.RecycleItem) async {
        working = true
        defer { working = false }
        do {
            try await api.requestVoid(
                "POST", "/recycle-bin/\(item.type)/\(item.id)/restore"
            )
            await refresh()
            message = String(localized: "m6a.recycle.restored", table: "M6A")
        } catch {
            self.error = M6AErrorText.describe(error)
        }
    }

    /// Hard-delete one item (cascades to comments/media). Irreversible.
    func purge(_ item: CareDTOs.RecycleItem) async {
        working = true
        defer { working = false }
        do {
            try await api.requestVoid("DELETE", "/recycle-bin/\(item.type)/\(item.id)")
            await refresh()
            message = String(localized: "m6a.recycle.purged", table: "M6A")
        } catch {
            self.error = M6AErrorText.describe(error)
        }
    }

    /// Empty the whole bin (`DELETE /recycle-bin` with no type filter).
    func emptyBin() async {
        working = true
        defer { working = false }
        do {
            try await api.requestVoid("DELETE", "/recycle-bin")
            await refresh()
            message = String(localized: "m6a.recycle.emptied", table: "M6A")
        } catch {
            self.error = M6AErrorText.describe(error)
        }
    }
}

// MARK: - View

struct RecycleBinView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: RecycleViewModel?

    @State private var purgeTarget: CareDTOs.RecycleItem?
    @State private var emptyConfirm = false

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m6a: "m6a.recycle.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = RecycleViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: RecycleViewModel) -> some View {
        VStack(spacing: 0) {
            Picker(
                .init(m6a: "m6a.recycle.filter"),
                selection: Binding(
                    get: { model.filter },
                    set: { filter in Task { await model.select(filter) } }
                )
            ) {
                ForEach(RecycleViewModel.Filter.allCases) { filter in
                    Text(LocalizedStringKey(m6a: filter.labelKey)).tag(filter)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 16)
            .padding(.vertical, 10)

            if let message = model.message {
                LoveSuccessBanner(message: message)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 8)
            }
            if let error = model.error, model.items.isEmpty {
                LoveErrorView(message: error) {
                    Task { await model.refresh() }
                }
            } else if model.loading {
                LoveLoadingView()
            } else if model.items.isEmpty {
                LoveEmptyState(
                    systemImage: "trash.slash",
                    titleKey: .init(m6a: "m6a.recycle.empty"),
                    messageKey: .init(m6a: "m6a.recycle.empty.hint")
                )
            } else {
                binList(model)
            }
        }
        .refreshable { await model.refresh() }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button(role: .destructive) {
                    emptyConfirm = true
                } label: {
                    Image(systemName: model.filter == .all ? "trash" : "trash.circle")
                }
                .disabled(model.items.isEmpty)
            }
        }
        .confirmationDialog(
            Text(purgeTarget == nil
                ? ""
                : String(localized: "m6a.recycle.purge.confirm", table: "M6A")),
            isPresented: Binding(
                get: { purgeTarget != nil },
                set: { if !$0 { purgeTarget = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button(String(localized: "common.delete"), role: .destructive) {
                if let target = purgeTarget {
                    Task { await model.purge(target) }
                }
                purgeTarget = nil
            }
            Button(String(localized: "common.cancel"), role: .cancel) {
                purgeTarget = nil
            }
        } message: {
            Text(String(localized: "m6a.recycle.purge.message", table: "M6A"))
        }
        .confirmationDialog(
            Text(String(localized: "m6a.recycle.empty.confirm", table: "M6A")),
            isPresented: $emptyConfirm,
            titleVisibility: .visible
        ) {
            Button(String(localized: "m6a.recycle.empty.action", table: "M6A"), role: .destructive) {
                Task { await model.emptyBin() }
            }
            Button(String(localized: "common.cancel"), role: .cancel) {}
        } message: {
            Text(String(localized: "m6a.recycle.purge.message", table: "M6A"))
        }
    }

    private func binList(_ model: RecycleViewModel) -> some View {
        List {
            ForEach(model.items) { item in
                RecycleRow(item: item) {
                    Task { await model.restore(item) }
                }
                .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))
                .listRowSeparator(.hidden)
                .listRowBackground(Color.clear)
                .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                    Button(role: .destructive) {
                        purgeTarget = item
                    } label: {
                        Label(
                            String(localized: "common.delete"),
                            systemImage: "trash.fill"
                        )
                    }
                }
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .scrollIndicators(.hidden)
    }
}

// MARK: - Row

private struct RecycleRow: View {
    let item: CareDTOs.RecycleItem
    let onRestore: () -> Void

    private var typeTint: Color {
        switch item.type {
        case "article": LoveTheme.primaryAccessible
        case "album": LoveTheme.peach
        case "event": LoveTheme.lavender
        case "moment": LoveTheme.rose
        case "message": LoveTheme.mint
        default: LoveTheme.secondaryText
        }
    }

    var body: some View {
        LoveSoftCard {
            HStack(alignment: .center, spacing: 10) {
                Image(systemName: "tray.full")
                    .font(.footnote)
                    .foregroundStyle(typeTint)
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        LovePill(
                            // Runtime-built key: stringLiteral keeps the raw
                            // key text (no format specifiers involved).
                            text: String(
                                localized: String.LocalizationValue(
                                    stringLiteral: "m6a.recycle.type.\(item.type)"
                                ),
                                table: "M6A"
                            ),
                            tint: typeTint
                        )
                    }
                    Text(item.title)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.text)
                        .lineLimit(2)
                    Text(Format.dateTime(item.deletedAt))
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                Spacer()
                Button(action: onRestore) {
                    Label(.init(m6a: "m6a.recycle.restore"), systemImage: "arrow.uturn.backward")
                        .font(.footnote.weight(.medium))
                }
                .buttonStyle(.plain)
                .foregroundStyle(LoveTheme.primaryAccessible)
            }
        }
    }
}
