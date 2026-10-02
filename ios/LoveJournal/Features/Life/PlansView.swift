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

/// `LifeDTOs.PlanChecklistItem` has no public memberwise initializer, so the
/// plans write path carries its own wire structs (identical JSON shape).
struct PlanChecklistWire: Encodable {
    var key: String?
    var text: String
    var done: Bool

    enum CodingKeys: String, CodingKey {
        case key, text, done
    }
}

struct PlanBody: Encodable {
    var title: String
    var description: String?
    var location: String?
    /// YYYY-MM-DD
    var planDate: String?
    var priority: Int?
    var checklist: [PlanChecklistWire]?
    var status: String?

    enum CodingKeys: String, CodingKey {
        case title, description, location, priority, checklist, status
        case planDate = "plan_date"
    }
}

/// Editor row for a checklist item (keeps existing server keys on edit).
struct PlanChecklistDraft: Identifiable {
    var id = UUID()
    var key: String?
    var text: String
    var done: Bool
}

@MainActor
@Observable
final class PlansViewModel {
    private(set) var loading = true
    private(set) var items: [LifeDTOs.Plan] = []
    private(set) var active = 0
    private(set) var completed = 0
    private(set) var cancelled = 0
    /// Local status bucket: all | active | done | cancelled
    var filter = "all"
    var message: String?
    var error: String?
    var saving = false

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    var visible: [LifeDTOs.Plan] {
        switch filter {
        case "active":
            items.filter { $0.status == "planned" || $0.status == "in_progress" }
        case "done":
            items.filter { $0.status == "done" }
        case "cancelled":
            items.filter { $0.status == "cancelled" }
        default:
            items
        }
    }

    func refresh() async {
        do {
            let list = try await api.request(
                LifeDTOs.PlanList.self,
                "GET",
                "/cottage/plans",
                query: [URLQueryItem(name: "limit", value: "100")]
            )
            items = list.items
            active = list.active
            completed = list.completed
            cancelled = list.cancelled
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? M5CL10n.value("m5c.plans.failed")
        }
        loading = false
    }

    /// Checklist ticks PATCH the full checklist (server-side replacement).
    func toggleChecklistItem(_ plan: LifeDTOs.Plan, item: LifeDTOs.PlanChecklistItem) async {
        guard let index = plan.checklist.firstIndex(where: { $0.id == item.id }) else { return }
        var checklist = plan.checklist
        checklist[index].done.toggle()
        let body = PlanBody(
            title: plan.title,
            description: plan.description,
            location: plan.location,
            planDate: plan.planDate,
            priority: plan.priority,
            checklist: checklist.map { PlanChecklistWire(key: $0.key, text: $0.text, done: $0.done) }
        )
        do {
            _ = try await api.request(
                LifeDTOs.Plan.self, "PATCH", "/cottage/plans/\(plan.pid)", body: body
            )
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.plans.failed")
        }
    }

    /// planned/in_progress → done.
    func complete(_ plan: LifeDTOs.Plan) async {
        do {
            _ = try await api.request(
                LifeDTOs.Plan.self, "POST", "/cottage/plans/\(plan.pid)/complete"
            )
            message = M5CL10n.value("m5c.plans.completed.msg")
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.plans.failed")
        }
    }

    /// done → planned.
    func reopen(_ plan: LifeDTOs.Plan) async {
        do {
            _ = try await api.request(
                LifeDTOs.Plan.self, "POST", "/cottage/plans/\(plan.pid)/reopen"
            )
            message = M5CL10n.value("m5c.plans.reopened")
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.plans.failed")
        }
    }

    /// active → cancelled (status only reaches `cancelled` via PATCH).
    func cancel(_ plan: LifeDTOs.Plan) async {
        await patchStatus(plan, status: "cancelled", successKey: "m5c.plans.cancelled.msg")
    }

    /// cancelled → planned.
    func restore(_ plan: LifeDTOs.Plan) async {
        await patchStatus(plan, status: "planned", successKey: "m5c.plans.restored")
    }

    private func patchStatus(_ plan: LifeDTOs.Plan, status: String, successKey: String) async {
        let body = PlanBody(
            title: plan.title,
            description: plan.description,
            location: plan.location,
            planDate: plan.planDate,
            priority: plan.priority,
            checklist: plan.checklist.map { PlanChecklistWire(key: $0.key, text: $0.text, done: $0.done) },
            status: status
        )
        do {
            _ = try await api.request(
                LifeDTOs.Plan.self, "PATCH", "/cottage/plans/\(plan.pid)", body: body
            )
            message = M5CL10n.value(String.LocalizationValue(successKey))
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.plans.failed")
        }
    }

    /// Returns true when the sheet should close.
    func save(
        existing: LifeDTOs.Plan?,
        title: String,
        detail: String,
        location: String,
        planDate: Date,
        priority: Int,
        checklist: [PlanChecklistDraft]
    ) async -> Bool {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty else {
            message = M5CL10n.value("m5c.plans.need.title")
            return false
        }
        saving = true
        defer { saving = false }
        let items = checklist.compactMap { row -> PlanChecklistWire? in
            let text = row.text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !text.isEmpty else { return nil }
            return PlanChecklistWire(key: row.key, text: text, done: row.done)
        }
        let body = PlanBody(
            title: trimmedTitle,
            description: normalizedOptional(detail),
            location: normalizedOptional(location),
            planDate: Format.date(planDate),
            priority: priority,
            checklist: items
        )
        do {
            if let existing {
                _ = try await api.request(
                    LifeDTOs.Plan.self, "PATCH", "/cottage/plans/\(existing.pid)", body: body
                )
                message = M5CL10n.value("m5c.plans.updated")
            } else {
                _ = try await api.request(
                    LifeDTOs.Plan.self, "POST", "/cottage/plans", body: body
                )
                message = M5CL10n.value("m5c.plans.created")
            }
            await refresh()
            return true
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.plans.failed")
            return false
        }
    }

    func delete(_ plan: LifeDTOs.Plan) async {
        do {
            try await api.requestVoid("DELETE", "/cottage/plans/\(plan.pid)")
            message = M5CL10n.value("m5c.plans.deleted")
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.plans.failed")
        }
    }

    private func normalizedOptional(_ raw: String) -> String? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

struct PlansView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: PlansViewModel?
    @State private var editorPresented = false
    @State private var editing: LifeDTOs.Plan?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m5c: "m5c.plans.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = PlansViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: PlansViewModel) -> some View {
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
                    if model.visible.isEmpty {
                        LoveEmptyState(
                            systemImage: "calendar.badge.heart",
                            titleKey: .init(m5c: "m5c.plans.empty"),
                            messageKey: .init(m5c: "m5c.plans.empty.hint")
                        )
                    } else {
                        ForEach(model.visible) { plan in
                            planCard(plan, model: model)
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
                Label(.init(m5c: "m5c.plans.new"), systemImage: "plus")
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
            PlanEditorSheet(model: model, editing: editing)
        }
    }

    private func header(_ model: PlansViewModel) -> some View {
        VStack(spacing: 10) {
            Text("m5c.plans.count \(model.active) \(model.completed) \(model.cancelled)", tableName: "M5C")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(LoveTheme.secondaryText)
                .frame(maxWidth: .infinity, alignment: .leading)
            Picker(
                selection: Binding(
                    get: { model.filter },
                    set: { model.filter = $0 }
                )
            ) {
                Text(.init(m5c: "m5c.plans.filter.all")).tag("all")
                Text(.init(m5c: "m5c.plans.filter.active")).tag("active")
                Text(.init(m5c: "m5c.plans.filter.done")).tag("done")
                Text(.init(m5c: "m5c.plans.filter.cancelled")).tag("cancelled")
            } label: {
                EmptyView()
            }
            .pickerStyle(.segmented)
        }
    }

    private func planCard(_ plan: LifeDTOs.Plan, model: PlansViewModel) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .top) {
                    Button {
                        editing = plan
                        editorPresented = true
                    } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(plan.title)
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(LoveTheme.text)
                            if let description = plan.description, !description.isEmpty {
                                Text(description)
                                    .font(.footnote)
                                    .foregroundStyle(LoveTheme.secondaryText)
                                    .lineLimit(2)
                            }
                            if let location = plan.location, !location.isEmpty {
                                Text("📍 \(location)")
                                    .font(.footnote)
                                    .foregroundStyle(LoveTheme.secondaryText)
                            }
                            if let planDate = plan.planDate, !planDate.isEmpty {
                                Text(planDate)
                                    .font(.caption)
                                    .foregroundStyle(LoveTheme.secondaryText)
                            }
                        }
                    }
                    .buttonStyle(.plain)
                    Spacer()
                    VStack(alignment: .trailing, spacing: 8) {
                        statusPill(plan.status)
                        Button {
                            Task { await model.delete(plan) }
                        } label: {
                            Image(systemName: "trash")
                                .font(.footnote)
                                .foregroundStyle(LoveTheme.rose)
                        }
                        .buttonStyle(.plain)
                    }
                }

                if !plan.checklist.isEmpty {
                    checklistSection(plan, model: model)
                }

                actionRow(plan, model: model)
            }
        }
    }

    private func checklistSection(_ plan: LifeDTOs.Plan, model: PlansViewModel) -> some View {
        let done = plan.checklist.filter(\.done).count
        return VStack(alignment: .leading, spacing: 8) {
            ProgressView(value: Double(done), total: Double(plan.checklist.count))
                .tint(LoveTheme.mint)
            Text("m5c.plans.checklist \(done) \(plan.checklist.count)", tableName: "M5C")
                .font(.caption2)
                .foregroundStyle(LoveTheme.secondaryText)
            ForEach(plan.checklist) { item in
                Button {
                    Task { await model.toggleChecklistItem(plan, item: item) }
                } label: {
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: item.done ? "checkmark.circle.fill" : "circle")
                            .font(.footnote)
                            .foregroundStyle(item.done ? LoveTheme.mint : LoveTheme.outline)
                        Text(item.text)
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.text)
                            .strikethrough(item.done, color: LoveTheme.secondaryText)
                            .multilineTextAlignment(.leading)
                    }
                }
                .buttonStyle(.plain)
            }
        }
        .padding(10)
        .background(LoveTheme.background.opacity(0.6), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    @ViewBuilder
    private func actionRow(_ plan: LifeDTOs.Plan, model: PlansViewModel) -> some View {
        HStack(spacing: 12) {
            switch plan.status {
            case "planned", "in_progress":
                Button {
                    Task { await model.complete(plan) }
                } label: {
                    Text(M5CL10n.value("m5c.plans.complete"))
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 7)
                        .background(LoveTheme.gradient, in: Capsule())
                }
                .buttonStyle(.plain)
                Button {
                    Task { await model.cancel(plan) }
                } label: {
                    Text(M5CL10n.value("m5c.plans.cancel"))
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(LoveTheme.rose)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .overlay(Capsule().stroke(LoveTheme.rose.opacity(0.4), lineWidth: 1))
                }
                .buttonStyle(.plain)
            case "done":
                secondaryAction("m5c.plans.reopen") {
                    Task { await model.reopen(plan) }
                }
            case "cancelled":
                secondaryAction("m5c.plans.restore") {
                    Task { await model.restore(plan) }
                }
            default:
                EmptyView()
            }
            Spacer()
        }
    }

    private func secondaryAction(_ key: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(String(localized: String.LocalizationValue(key), table: "M5C"))
                .font(.caption.weight(.semibold))
                .foregroundStyle(LoveTheme.primaryAccessible)
                .padding(.horizontal, 14)
                .padding(.vertical, 7)
                .overlay(Capsule().stroke(LoveTheme.primaryAccessible.opacity(0.4), lineWidth: 1))
        }
        .buttonStyle(.plain)
    }

    private func statusPill(_ status: String) -> some View {
        switch status {
        case "in_progress":
            return LovePill(
                text: M5CL10n.value("m5c.plans.status.in_progress"),
                tint: LoveTheme.peach
            )
        case "done":
            return LovePill(
                text: M5CL10n.value("m5c.plans.status.done"),
                tint: LoveTheme.mint
            )
        case "cancelled":
            return LovePill(
                text: M5CL10n.value("m5c.plans.status.cancelled"),
                tint: LoveTheme.secondaryText
            )
        default:
            return LovePill(
                text: M5CL10n.value("m5c.plans.status.planned"),
                tint: LoveTheme.lavender
            )
        }
    }
}

// MARK: - Editor sheet

private struct PlanEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: PlansViewModel
    let editing: LifeDTOs.Plan?

    @State private var title = ""
    @State private var detail = ""
    @State private var location = ""
    @State private var planDate = Date()
    @State private var priority = 100
    @State private var checklist: [PlanChecklistDraft] = []

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: .init(m5c: "m5c.plans.editor.title")) {
                        TextField(M5CL10n.value("m5c.plans.editor.title"), text: $title)
                    }
                    LoveField(labelKey: .init(m5c: "m5c.plans.editor.description")) {
                        TextField(
                            M5CL10n.value("m5c.plans.editor.description"),
                            text: $detail,
                            axis: .vertical
                        )
                        .lineLimit(2...4)
                    }
                    LoveField(labelKey: .init(m5c: "m5c.plans.editor.location")) {
                        TextField(M5CL10n.value("m5c.plans.editor.location"), text: $location)
                    }
                    DatePicker(
                        .init(m5c: "m5c.plans.editor.date"),
                        selection: $planDate,
                        displayedComponents: .date
                    )
                    .tint(LoveTheme.primaryAccessible)
                    Stepper(value: $priority, in: 0...1000, step: 10) {
                        HStack {
                            Text(.init(m5c: "m5c.plans.editor.priority"))
                                .font(.subheadline)
                            Spacer()
                            Text("\(priority)")
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(LoveTheme.secondaryText)
                        }
                    }
                    checklistSection
                    if let message = model.message {
                        LoveErrorBanner(message: message)
                    }
                    LovePrimaryButton(
                        titleKey: editing == nil
                            ? .init(m5c: "m5c.plans.add")
                            : .init(m5c: "m5c.common.save"),
                        loading: model.saving
                    ) {
                        let values = (title, detail, location, planDate, priority, checklist)
                        Task {
                            if await model.save(
                                existing: editing,
                                title: values.0,
                                detail: values.1,
                                location: values.2,
                                planDate: values.3,
                                priority: values.4,
                                checklist: values.5
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
                    ? .init(m5c: "m5c.plans.new")
                    : .init(m5c: "m5c.plans.edit")
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
                detail = editing.description ?? ""
                location = editing.location ?? ""
                planDate = editing.planDate.flatMap(Self.dayParser.date(from:)) ?? Date()
                priority = editing.priority
                checklist = editing.checklist.map {
                    PlanChecklistDraft(key: $0.key, text: $0.text, done: $0.done)
                }
            }
        }
    }

    private var checklistSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(.init(m5c: "m5c.plans.editor.checklist"))
                .font(.footnote.weight(.medium))
                .foregroundStyle(LoveTheme.secondaryText)
            ForEach($checklist) { $row in
                HStack(spacing: 8) {
                    Button {
                        row.done.toggle()
                    } label: {
                        Image(systemName: row.done ? "checkmark.circle.fill" : "circle")
                            .font(.footnote)
                            .foregroundStyle(row.done ? LoveTheme.mint : LoveTheme.outline)
                    }
                    .buttonStyle(.plain)
                    TextField(
                        M5CL10n.value("m5c.plans.editor.checklist.placeholder"),
                        text: $row.text
                    )
                    Button {
                        checklist.removeAll { $0.id == row.id }
                    } label: {
                        Image(systemName: "minus.circle")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.rose)
                    }
                    .buttonStyle(.plain)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(LoveTheme.background.opacity(0.6), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            Button {
                guard checklist.count < 30 else { return }
                checklist.append(PlanChecklistDraft(key: nil, text: "", done: false))
            } label: {
                Label(.init(m5c: "m5c.plans.editor.checklist.add"), systemImage: "plus.circle")
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(LoveTheme.primaryAccessible)
            }
            .buttonStyle(.plain)
        }
    }

    /// Parses the `YYYY-MM-DD` contract string for the editor DatePicker.
    private static let dayParser: DateFormatter = {
        let parser = DateFormatter()
        parser.dateFormat = "yyyy-MM-dd"
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.timeZone = .current
        return parser
    }()
}
