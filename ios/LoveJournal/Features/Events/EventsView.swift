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
final class EventsViewModel {
    var loading = true
    var error: String?
    var events: [ContentDTOs.Event] = []
    var message: String?
    var saving = false

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        if events.isEmpty { loading = true }
        do {
            let page = try await api.request(
                ContentDTOs.Page<ContentDTOs.Event>.self, "GET", "/events"
            )
            events = page.items
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? "加载失败，请稍后重试"
        }
        loading = false
    }

    func save(
        existing: ContentDTOs.Event?,
        title: String,
        date: Date,
        type: String,
        isImportant: Bool,
        isYearlyRepeat: Bool
    ) async {
        guard !title.trimmingCharacters(in: .whitespaces).isEmpty else {
            message = "请输入标题"
            return
        }
        saving = true
        defer { saving = false }
        let payload = ContentDTOs.EventUpsert(
            title: title.trimmingCharacters(in: .whitespaces),
            date: Format.date(date),
            type: type,
            isImportant: isImportant,
            isYearlyRepeat: isYearlyRepeat
        )
        do {
            if let existing {
                _ = try await api.request(
                    ContentDTOs.Event.self, "PUT", "/events/\(existing.eid)", body: payload
                )
                message = "已保存"
            } else {
                _ = try await api.request(
                    ContentDTOs.Event.self, "POST", "/events", body: payload
                )
                message = "已添加"
            }
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? "保存失败，请稍后重试"
        }
    }

    func delete(_ event: ContentDTOs.Event) async {
        do {
            try await api.requestVoid("DELETE", "/events/\(event.eid)")
            events.removeAll { $0.eid == event.eid }
            message = "已删除"
        } catch {
            message = (error as? APIError)?.message ?? "删除失败，请稍后重试"
        }
    }
}

struct EventsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: EventsViewModel?
    @State private var editorPresented = false
    @State private var editing: ContentDTOs.Event?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("tab.events")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = EventsViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
        .sheet(isPresented: $editorPresented) {
            EventEditorSheet(model: model!, editing: editing)
        }
    }

    private func content(_ model: EventsViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error, model.events.isEmpty {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else if model.events.isEmpty {
                    LoveEmptyState(
                        systemImage: "calendar.badge.heart",
                        titleKey: "events.empty",
                        messageKey: "events.empty.hint"
                    )
                } else {
                    ForEach(model.events) { event in
                        eventCard(event)
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
                Label("events.add", systemImage: "plus")
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

    private func eventCard(_ event: ContentDTOs.Event) -> some View {
        LoveSoftCard {
            HStack(alignment: .top) {
                Button {
                    editing = event
                    editorPresented = true
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 6) {
                            Text(event.title)
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(LoveTheme.text)
                            if event.isImportant {
                                Image(systemName: "star.fill")
                                    .font(.caption)
                                    .foregroundStyle(LoveTheme.peach)
                            }
                        }
                        Text(event.date)
                            .font(.caption)
                            .foregroundStyle(LoveTheme.secondaryText)
                        LovePill(
                            text: event.isAnniversary
                                ? String(localized: "event.type.anniversary")
                                : String(localized: "event.type.countdown"),
                            tint: LoveTheme.lavender
                        )
                    }
                }
                .buttonStyle(.plain)
                Spacer()
                VStack(alignment: .trailing, spacing: 8) {
                    if let days = event.nextOccurrenceDays {
                        Text(days == 0 ? String(localized: "event.days.today") : String(localized: "event.days.count \(days)"))
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(LoveTheme.primaryAccessible)
                    }
                    Button {
                        Task { await model?.delete(event) }
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
}

struct EventEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: EventsViewModel
    let editing: ContentDTOs.Event?

    @State private var title = ""
    @State private var date = Date()
    @State private var isAnniversary = false
    @State private var isImportant = false
    @State private var isYearlyRepeat = false

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: "events.editor.title") {
                        TextField("events.editor.title", text: $title)
                    }
                    DatePicker(
                        "events.editor.date",
                        selection: $date,
                        displayedComponents: .date
                    )
                    .tint(LoveTheme.primaryAccessible)
                    Picker("events.editor.type", selection: $isAnniversary) {
                        Text("event.type.countdown").tag(false)
                        Text("event.type.anniversary").tag(true)
                    }
                    .pickerStyle(.segmented)
                    Toggle(isOn: $isImportant) {
                        Text("events.editor.important")
                    }
                    .tint(LoveTheme.primaryAccessible)
                    Toggle(isOn: $isYearlyRepeat) {
                        Text("events.editor.yearly")
                    }
                    .tint(LoveTheme.primaryAccessible)
                    LovePrimaryButton(titleKey: editing == nil ? "events.add" : "common.save", loading: model.saving) {
                        let type = isAnniversary ? "Anniversary" : "Countdown"
                        Task {
                            await model.save(
                                existing: editing,
                                title: title,
                                date: date,
                                type: type,
                                isImportant: isImportant,
                                isYearlyRepeat: isYearlyRepeat
                            )
                            dismiss()
                        }
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(editing == nil ? "events.add" : "events.edit")
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
                date = editing.dateDate ?? Date()
                isAnniversary = editing.isAnniversary
                isImportant = editing.isImportant
                isYearlyRepeat = editing.isYearlyRepeat
            }
        }
    }
}

private extension ContentDTOs.Event {
    /// Parses the `YYYY-MM-DD` contract string for the editor DatePicker.
    var dateDate: Date? {
        let parser = DateFormatter()
        parser.dateFormat = "yyyy-MM-dd"
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.timeZone = TimeZone(identifier: "UTC")
        return parser.date(from: date)
    }
}
