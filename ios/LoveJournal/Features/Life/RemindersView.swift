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

/// `LifeDTOs.ReminderUpsert` carries `remind_at` as a `Date`, but the shared
/// `LoveAPIClient` encoder emits dates as non-ISO numbers that FastAPI's
/// `datetime` field would misinterpret — the wire body needs a preformatted
/// ISO-8601 string (same approach as `CapsuleCreateBody`).
private struct ReminderBody: Encodable {
    var title: String
    var note: String?
    var remindAt: Date
    var audience: String

    private static let isoFormatter = ISO8601DateFormatter()

    enum CodingKeys: String, CodingKey {
        case title, note, audience
        case remindAt = "remind_at"
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(title, forKey: .title)
        try container.encodeIfPresent(note, forKey: .note)
        try container.encode(Self.isoFormatter.string(from: remindAt), forKey: .remindAt)
        try container.encode(audience, forKey: .audience)
    }
}

@MainActor
@Observable
final class RemindersViewModel {
    private(set) var loading = true
    private(set) var items: [LifeDTOs.Reminder] = []
    private(set) var active = 0
    private(set) var due = 0
    var includeDone = false
    var message: String?
    var error: String?
    var saving = false

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        var query = [URLQueryItem(name: "limit", value: "100")]
        if includeDone {
            query.append(URLQueryItem(name: "include_done", value: "true"))
        }
        do {
            let list = try await api.request(
                LifeDTOs.ReminderList.self, "GET", "/cottage/reminders", query: query
            )
            items = list.items
            active = list.active
            due = list.due
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? M5CL10n.value("m5c.reminders.failed")
        }
        loading = false
    }

    /// Mark done / reopen (both partners may act on a reminder).
    func toggleDone(_ reminder: LifeDTOs.Reminder) async {
        do {
            _ = try await api.request(
                LifeDTOs.Reminder.self,
                "POST",
                "/cottage/reminders/\(reminder.rid)/\(reminder.isDone ? "reopen" : "done")"
            )
            message = reminder.isDone
                ? M5CL10n.value("m5c.reminders.reopened")
                : M5CL10n.value("m5c.reminders.marked.done")
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.reminders.failed")
        }
    }

    /// Returns true when the sheet should close.
    func save(
        existing: LifeDTOs.Reminder?,
        title: String,
        note: String,
        remindAt: Date,
        audience: String
    ) async -> Bool {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty else {
            message = M5CL10n.value("m5c.reminders.need.title")
            return false
        }
        saving = true
        defer { saving = false }
        let body = ReminderBody(
            title: trimmedTitle,
            note: normalizedOptional(note),
            remindAt: remindAt,
            audience: audience
        )
        do {
            if let existing {
                _ = try await api.request(
                    LifeDTOs.Reminder.self, "PATCH", "/cottage/reminders/\(existing.rid)", body: body
                )
                message = M5CL10n.value("m5c.reminders.updated")
            } else {
                _ = try await api.request(
                    LifeDTOs.Reminder.self, "POST", "/cottage/reminders", body: body
                )
                message = M5CL10n.value("m5c.reminders.created")
            }
            await refresh()
            return true
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.reminders.failed")
            return false
        }
    }

    func delete(_ reminder: LifeDTOs.Reminder) async {
        do {
            try await api.requestVoid("DELETE", "/cottage/reminders/\(reminder.rid)")
            message = M5CL10n.value("m5c.reminders.deleted")
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.reminders.failed")
        }
    }

    private func normalizedOptional(_ raw: String) -> String? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

struct RemindersView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: RemindersViewModel?
    @State private var editorPresented = false
    @State private var editing: LifeDTOs.Reminder?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m5c: "m5c.reminders.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = RemindersViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: RemindersViewModel) -> some View {
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
                    header(model)
                    if model.items.isEmpty {
                        LoveEmptyState(
                            systemImage: "bell.badge",
                            titleKey: .init(m5c: "m5c.reminders.empty"),
                            messageKey: .init(m5c: "m5c.reminders.empty.hint")
                        )
                    } else {
                        ForEach(model.items) { reminder in
                            reminderCard(reminder, model: model)
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
                Label(.init(m5c: "m5c.reminders.new"), systemImage: "plus")
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
            ReminderEditorSheet(model: model, editing: editing)
        }
    }

    private func header(_ model: RemindersViewModel) -> some View {
        VStack(spacing: 10) {
            HStack {
                Text("m5c.reminders.count \(model.active) \(model.due)", tableName: "M5C")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.secondaryText)
                Spacer()
            }
            Toggle(
                isOn: Binding(
                    get: { model.includeDone },
                    set: { newValue in
                        model.includeDone = newValue
                        Task { await model.refresh() }
                    }
                )
            ) {
                Text(.init(m5c: "m5c.reminders.include.done"))
                    .font(.footnote)
            }
            .tint(LoveTheme.primaryAccessible)
        }
    }

    private func reminderCard(_ reminder: LifeDTOs.Reminder, model: RemindersViewModel) -> some View {
        LoveSoftCard {
            HStack(alignment: .top, spacing: 12) {
                Button {
                    Task { await model.toggleDone(reminder) }
                } label: {
                    Image(systemName: reminder.isDone ? "checkmark.circle.fill" : "circle")
                        .font(.title3)
                        .foregroundStyle(reminder.isDone ? LoveTheme.mint : LoveTheme.outline)
                }
                .buttonStyle(.plain)

                Button {
                    editing = reminder
                    editorPresented = true
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 6) {
                            Text(reminder.title)
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(LoveTheme.text)
                                .strikethrough(reminder.isDone, color: LoveTheme.secondaryText)
                            if reminder.isDue && !reminder.isDone {
                                Circle()
                                    .fill(LoveTheme.rose)
                                    .frame(width: 6, height: 6)
                            }
                        }
                        if let note = reminder.note, !note.isEmpty {
                            Text(note)
                                .font(.footnote)
                                .foregroundStyle(LoveTheme.secondaryText)
                                .lineLimit(2)
                        }
                        HStack(spacing: 8) {
                            Text(timeText(reminder))
                                .font(.caption)
                                .foregroundStyle(
                                    reminder.isDue && !reminder.isDone
                                        ? LoveTheme.rose
                                        : LoveTheme.secondaryText
                                )
                            audiencePill(reminder.audience)
                            if reminder.isDone {
                                donePill(reminder)
                            }
                        }
                    }
                }
                .buttonStyle(.plain)

                Spacer()

                Button {
                    Task { await model.delete(reminder) }
                } label: {
                    Image(systemName: "trash")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.rose)
                }
                .buttonStyle(.plain)
            }
        }
    }

    /// Countdown while the reminder is still in the future; the absolute time
    /// once it has passed (the `is_due` dot flags the overdue ones).
    private func timeText(_ reminder: LifeDTOs.Reminder) -> String {
        if reminder.isDone, let doneAt = reminder.doneAt {
            return Format.dateTime(doneAt)
        }
        let interval = reminder.remindAt.timeIntervalSinceNow
        if interval > 0 {
            let minutes = Int(interval / 60)
            if minutes >= 60 * 24 {
                return M5CL10n.value("m5c.reminders.in.days \(minutes / 1440)")
            }
            if minutes >= 60 {
                return M5CL10n.value("m5c.reminders.in.hours \(minutes / 60)")
            }
            return M5CL10n.value("m5c.reminders.in.minutes \(max(minutes, 1))")
        }
        return Format.dateTime(reminder.remindAt)
    }

    private func audiencePill(_ audience: String) -> some View {
        switch audience {
        case "me":
            return LovePill(
                text: M5CL10n.value("m5c.reminders.audience.me"),
                tint: LoveTheme.peach
            )
        case "partner":
            return LovePill(
                text: M5CL10n.value("m5c.reminders.audience.partner"),
                tint: LoveTheme.mint
            )
        default:
            return LovePill(
                text: M5CL10n.value("m5c.reminders.audience.both"),
                tint: LoveTheme.lavender
            )
        }
    }

    @ViewBuilder
    private func donePill(_ reminder: LifeDTOs.Reminder) -> some View {
        if let by = reminder.doneByNickname {
            LovePill(
                text: M5CL10n.value("m5c.reminders.done.by \(by)"),
                tint: LoveTheme.mint
            )
        } else {
            LovePill(text: M5CL10n.value("m5c.reminders.done"), tint: LoveTheme.mint)
        }
    }
}

// MARK: - Editor sheet

private struct ReminderEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: RemindersViewModel
    let editing: LifeDTOs.Reminder?

    @State private var title = ""
    @State private var note = ""
    @State private var remindAt = Date().addingTimeInterval(3600)
    /// both | me | partner
    @State private var audience = "both"

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: .init(m5c: "m5c.reminders.editor.title")) {
                        TextField(M5CL10n.value("m5c.reminders.editor.title"), text: $title)
                    }
                    LoveField(labelKey: .init(m5c: "m5c.reminders.editor.note")) {
                        TextField(
                            M5CL10n.value("m5c.reminders.editor.note.placeholder"),
                            text: $note,
                            axis: .vertical
                        )
                        .lineLimit(2...4)
                    }
                    DatePicker(
                        .init(m5c: "m5c.reminders.editor.remind.at"),
                        selection: $remindAt,
                        displayedComponents: [.date, .hourAndMinute]
                    )
                    .tint(LoveTheme.primaryAccessible)
                    Picker(.init(m5c: "m5c.reminders.editor.audience"), selection: $audience) {
                        Text(.init(m5c: "m5c.reminders.audience.both")).tag("both")
                        Text(.init(m5c: "m5c.reminders.audience.me")).tag("me")
                        Text(.init(m5c: "m5c.reminders.audience.partner")).tag("partner")
                    }
                    .pickerStyle(.segmented)
                    if let message = model.message {
                        LoveErrorBanner(message: message)
                    }
                    LovePrimaryButton(
                        titleKey: editing == nil
                            ? .init(m5c: "m5c.reminders.add")
                            : .init(m5c: "m5c.common.save"),
                        loading: model.saving
                    ) {
                        let values = (title, note, remindAt, audience)
                        Task {
                            if await model.save(
                                existing: editing,
                                title: values.0,
                                note: values.1,
                                remindAt: values.2,
                                audience: values.3
                            ) {
                                dismiss()
                            }
                        }
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(
                editing == nil
                    ? .init(m5c: "m5c.reminders.new")
                    : .init(m5c: "m5c.reminders.edit")
            )
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(M5CL10n.value("m5c.common.cancel")) { dismiss() }
                }
            }
        }
        .presentationDetents([.large])
        .onAppear {
            if let editing {
                title = editing.title
                note = editing.note ?? ""
                remindAt = editing.remindAt
                audience = editing.audience
            }
        }
    }
}
