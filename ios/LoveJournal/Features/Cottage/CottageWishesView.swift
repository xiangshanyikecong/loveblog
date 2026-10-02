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
final class WishesViewModel {
    private(set) var loading = true
    private(set) var items: [CottageDTOs.Wish] = []
    private(set) var pending = 0
    private(set) var completed = 0
    var message: String?
    var error: String?
    var saving = false

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        do {
            let list = try await api.request(
                CottageDTOs.WishList.self, "GET", "/cottage/wishes"
            )
            items = list.items
            pending = list.pending
            completed = list.completed
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? String(localized: "cottage.error.generic")
        }
        loading = false
    }

    func toggle(_ wish: CottageDTOs.Wish) async {
        do {
            _ = try await api.request(
                CottageDTOs.Wish.self,
                "POST",
                "/cottage/wishes/\(wish.wid)/\(wish.isCompleted ? "reopen" : "complete")"
            )
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? String(localized: "cottage.wishes.failed")
        }
    }

    func delete(_ wish: CottageDTOs.Wish) async {
        do {
            try await api.requestVoid("DELETE", "/cottage/wishes/\(wish.wid)")
            message = String(localized: "cottage.wishes.deleted")
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? String(localized: "cottage.wishes.failed")
        }
    }

    /// Create or update (full-field PATCH; the editor owns every field).
    /// Returns true when the sheet should close.
    func save(
        existing: CottageDTOs.Wish?, title: String, note: String, category: String
    ) async -> Bool {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty else {
            message = String(localized: "cottage.wishes.need.title")
            return false
        }
        saving = true
        defer { saving = false }
        let body = CottageDTOs.WishCreate(
            title: trimmedTitle,
            description: normalizedOptional(note),
            category: normalizedOptional(category),
            priority: existing?.priority ?? 0
        )
        do {
            if let existing {
                _ = try await api.request(
                    CottageDTOs.Wish.self, "PATCH", "/cottage/wishes/\(existing.wid)", body: body
                )
                message = String(localized: "cottage.wishes.updated")
            } else {
                _ = try await api.request(
                    CottageDTOs.Wish.self, "POST", "/cottage/wishes", body: body
                )
                message = String(localized: "cottage.wishes.added")
            }
            await refresh()
            return true
        } catch {
            message = (error as? APIError)?.message ?? String(localized: "cottage.wishes.failed")
            return false
        }
    }

    private func normalizedOptional(_ raw: String) -> String? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

struct CottageWishesView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: WishesViewModel?
    @State private var editorPresented = false
    @State private var editing: CottageDTOs.Wish?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("cottage.wishes.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = WishesViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
        .sheet(isPresented: $editorPresented) {
            if let model {
                WishEditorSheet(model: model, editing: editing)
            }
        }
    }

    private func content(_ model: WishesViewModel) -> some View {
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
                } else {
                    if !model.items.isEmpty {
                        Text("cottage.wishes.count \(model.pending) \(model.completed)")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.secondaryText)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    if model.items.isEmpty {
                        LoveEmptyState(
                            systemImage: "heart.text.square",
                            titleKey: "cottage.wishes.empty",
                            messageKey: "cottage.wishes.empty.hint"
                        )
                    } else {
                        ForEach(model.items) { wish in
                            wishCard(wish, model: model)
                        }
                    }
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
        .overlay(alignment: .bottomTrailing) {
            Button {
                editing = nil
                editorPresented = true
            } label: {
                Label("cottage.wishes.new", systemImage: "plus")
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

    private func wishCard(_ wish: CottageDTOs.Wish, model: WishesViewModel) -> some View {
        LoveSoftCard {
            HStack(alignment: .top, spacing: 12) {
                Button {
                    Task { await model.toggle(wish) }
                } label: {
                    Image(systemName: wish.isCompleted ? "checkmark.circle.fill" : "circle")
                        .font(.title3)
                        .foregroundStyle(wish.isCompleted ? LoveTheme.mint : LoveTheme.outline)
                }
                .buttonStyle(.plain)

                Button {
                    editing = wish
                    editorPresented = true
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(wish.title)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.text)
                            .strikethrough(wish.isCompleted, color: LoveTheme.secondaryText)
                        if let description = wish.description, !description.isEmpty {
                            Text(description)
                                .font(.footnote)
                                .foregroundStyle(LoveTheme.secondaryText)
                                .lineLimit(2)
                        }
                        HStack(spacing: 8) {
                            if let category = wish.category, !category.isEmpty {
                                LovePill(text: "#\(category)", tint: LoveTheme.lavender)
                            }
                            if wish.isCompleted {
                                if let by = wish.completedByNickname {
                                    LovePill(
                                        text: String(localized: "cottage.wishes.completed.by \(by)"),
                                        tint: LoveTheme.mint
                                    )
                                } else {
                                    LovePill(
                                        text: String(localized: "cottage.wishes.completed"),
                                        tint: LoveTheme.mint
                                    )
                                }
                            }
                        }
                    }
                }
                .buttonStyle(.plain)

                Spacer()

                Button {
                    Task { await model.delete(wish) }
                } label: {
                    Image(systemName: "trash")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.rose)
                }
                .buttonStyle(.plain)
            }
        }
    }
}

// MARK: - Editor sheet

private struct WishEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: WishesViewModel
    let editing: CottageDTOs.Wish?

    @State private var title = ""
    @State private var note = ""
    @State private var category = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: "cottage.wishes.title.field") {
                        TextField("cottage.wishes.title.field", text: $title)
                    }
                    LoveField(labelKey: "cottage.wishes.note") {
                        TextField("cottage.wishes.note.placeholder", text: $note, axis: .vertical)
                            .lineLimit(2...4)
                    }
                    LoveField(labelKey: "cottage.wishes.category") {
                        TextField("cottage.wishes.category.placeholder", text: $category)
                    }
                    if let message = model.message {
                        LoveErrorBanner(message: message)
                    }
                    LovePrimaryButton(
                        titleKey: editing == nil ? "cottage.wishes.add" : "common.save",
                        loading: model.saving
                    ) {
                        let values = (title, note, category)
                        Task {
                            if await model.save(
                                existing: editing,
                                title: values.0,
                                note: values.1,
                                category: values.2
                            ) {
                                dismiss()
                            }
                        }
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(editing == nil ? "cottage.wishes.new" : "cottage.wishes.edit")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("common.cancel") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
        .onAppear {
            if let editing {
                title = editing.title
                note = editing.description ?? ""
                category = editing.category ?? ""
            }
        }
    }
}
