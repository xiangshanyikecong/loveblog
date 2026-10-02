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

// MARK: - M6B shared localization (table "M6B")

/// M6 care-bundle lookups. The keys live in `M6B.xcstrings`, whose table
/// name is `"M6B"` — every lookup must therefore pass the table explicitly
/// (String Catalogs are per-file tables; the default stays `Localizable`).
enum M6BL10n {
    static func value(_ keyAndValue: String.LocalizationValue) -> String {
        String(localized: keyAndValue, table: "M6B")
    }
}

extension LocalizedStringKey {
    /// Resolves an M6B key up front so shared components that only take
    /// `LocalizedStringKey` (LoveField, LovePrimaryButton, …) render the
    /// translated text (same trick as the M2 table).
    init(m6b key: String) {
        self.init(stringLiteral: M6BL10n.value(String.LocalizationValue(key)))
    }
}

// MARK: - Period view model

@MainActor
@Observable
final class PeriodViewModel {
    var loading = true
    var error: String?
    var message: String?
    var saving = false
    private(set) var items: [CareDTOs.Period] = []
    private(set) var summary: CareDTOs.PeriodSummary?

    let selfUid: String?

    private let api: LoveAPIClient

    init(api: LoveAPIClient, selfUid: String?) {
        self.api = api
        self.selfUid = selfUid
    }

    func refresh() async {
        if summary == nil { loading = true }
        do {
            async let list = api.request(
                CareDTOs.PeriodList.self,
                "GET",
                "/cottage/period",
                query: [URLQueryItem(name: "limit", value: "60")]
            )
            async let summary = api.request(
                CareDTOs.PeriodSummary.self, "GET", "/cottage/period/summary"
            )
            let (page, stats) = try await (list, summary)
            items = page.items
            self.summary = stats
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? M6BL10n.value("m6b.common.load.failed")
        }
        loading = false
    }

    /// Create (`existing == nil`) or PATCH a cycle. Returns nil on success —
    /// the caller then closes the sheet — otherwise the message to show.
    func save(
        existing: CareDTOs.Period?, start: Date, end: Date?, note: String
    ) async -> String? {
        let calendar = Calendar.current
        let startDay = calendar.startOfDay(for: start)
        if let end, calendar.startOfDay(for: end) < startDay {
            return M6BL10n.value("m6b.period.editor.end.before.start")
        }
        let trimmed = note.trimmingCharacters(in: .whitespacesAndNewlines)
        let body = CareDTOs.PeriodUpsert(
            startDate: Format.date(start),
            endDate: end.map { Format.date($0) },
            note: trimmed.isEmpty ? nil : trimmed
        )
        saving = true
        defer { saving = false }
        do {
            if let existing {
                _ = try await api.request(
                    CareDTOs.Period.self,
                    "PATCH",
                    "/cottage/period/\(existing.pcid)",
                    body: body
                )
            } else {
                _ = try await api.request(
                    CareDTOs.Period.self, "POST", "/cottage/period", body: body
                )
            }
            message = M6BL10n.value("m6b.period.saved")
            await refresh()
            return nil
        } catch {
            return (error as? APIError)?.message ?? M6BL10n.value("m6b.common.save.failed")
        }
    }

    func delete(_ period: CareDTOs.Period) async {
        do {
            try await api.requestVoid("DELETE", "/cottage/period/\(period.pcid)")
            items.removeAll { $0.pcid == period.pcid }
            message = M6BL10n.value("m6b.period.deleted")
            // The summary is derived server-side; refetch so predictions drop
            // the removed cycle.
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? M6BL10n.value("m6b.common.delete.failed")
        }
    }
}

// MARK: - Period screen

struct PeriodView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: PeriodViewModel?
    @State private var editorPresented = false
    @State private var editing: CareDTOs.Period?
    @State private var deleting: CareDTOs.Period?
    @State private var monthAnchor = Date()

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m6b: "m6b.period.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                let uid: String?
                if case .loggedIn(let profile) = environment.session.state {
                    uid = profile.uid
                } else {
                    uid = nil
                }
                model = PeriodViewModel(api: environment.api, selfUid: uid)
                Task { await model?.refresh() }
            }
        }
        .sheet(isPresented: $editorPresented) {
            if let model {
                PeriodEditorSheet(model: model, editing: editing)
            }
        }
        .confirmationDialog(
            Text(deleting == nil ? "" : M6BL10n.value("m6b.period.delete.confirm")),
            isPresented: Binding(
                get: { deleting != nil },
                set: { if !$0 { deleting = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button(M6BL10n.value("m6b.common.delete"), role: .destructive) {
                if let period = deleting {
                    Task { await model?.delete(period) }
                }
                deleting = nil
            }
            Button(M6BL10n.value("m6b.common.cancel"), role: .cancel) {
                deleting = nil
            }
        }
    }

    private func content(_ model: PeriodViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error, model.summary == nil {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading, model.summary == nil {
                    LoveLoadingView()
                } else {
                    if let summary = model.summary {
                        summaryCard(summary)
                        PeriodCalendarView(
                            items: model.items,
                            predictedNextStart: summary.predictedNextStart,
                            month: $monthAnchor
                        )
                    }
                    Text(.init(m6b: "m6b.period.records.section"))
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.secondaryText)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if model.items.isEmpty {
                        LoveEmptyState(
                            systemImage: "calendar.badge.heart",
                            titleKey: .init(m6b: "m6b.period.empty"),
                            messageKey: .init(m6b: "m6b.period.empty.hint")
                        )
                    } else {
                        ForEach(model.items) { period in
                            periodCard(period, model: model)
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
                Label(.init(m6b: "m6b.period.add"), systemImage: "plus")
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

    // MARK: Care summary card

    private func summaryCard(_ summary: CareDTOs.PeriodSummary) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 8) {
                Text(.init(m6b: "m6b.period.phase.current"))
                    .font(.caption)
                    .foregroundStyle(LoveTheme.secondaryText)
                let info = phaseInfo(summary.phase)
                HStack(spacing: 8) {
                    Text(verbatim: info.emoji)
                        .font(.title3)
                    Text(verbatim: info.label)
                        .font(.title3.weight(.bold))
                        .foregroundStyle(info.tint)
                }
                if let next = summary.predictedNextStart {
                    Text(verbatim: predictionText(next, summary: summary))
                        .font(.subheadline)
                        .foregroundStyle(LoveTheme.text)
                }
                HStack(spacing: 12) {
                    if let cycle = summary.avgCycleDays {
                        Text(verbatim: M6BL10n.value("m6b.period.avg.cycle \(cycle)"))
                    }
                    if let days = summary.avgPeriodDays {
                        Text(verbatim: M6BL10n.value("m6b.period.avg.period \(days)"))
                    }
                    Text(verbatim: M6BL10n.value("m6b.period.records \(summary.cycleCount)"))
                }
                .font(.caption)
                .foregroundStyle(LoveTheme.secondaryText)
            }
        }
    }

    private func predictionText(
        _ next: String, summary: CareDTOs.PeriodSummary
    ) -> String {
        var text = M6BL10n.value("m6b.period.predicted.next \(next)")
        if let days = summary.predictedDaysUntil {
            let hint = days > 0
                ? M6BL10n.value("m6b.period.days.until \(days)")
                : days == 0
                    ? M6BL10n.value("m6b.period.days.today")
                    : M6BL10n.value("m6b.period.days.overdue \(-days)")
            text += " · " + hint
        }
        return text
    }

    // MARK: Record cards

    private func periodCard(
        _ period: CareDTOs.Period, model: PeriodViewModel
    ) -> some View {
        let isAuthor = model.selfUid != nil && period.authorUid == model.selfUid
        return LoveSoftCard {
            HStack(alignment: .top) {
                Button {
                    guard isAuthor else { return }
                    editing = period
                    editorPresented = true
                } label: {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(verbatim: rangeTitle(period))
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.text)
                        if let days = period.lengthDays {
                            LovePill(
                                text: M6BL10n.value("m6b.period.length \(days)"),
                                tint: LoveTheme.primaryAccessible
                            )
                        } else {
                            LovePill(
                                text: M6BL10n.value("m6b.period.ongoing"),
                                tint: LoveTheme.rose
                            )
                        }
                        if let note = period.note, !note.isEmpty {
                            Text(note)
                                .font(.footnote)
                                .foregroundStyle(LoveTheme.secondaryText)
                        }
                        Text(verbatim: M6BL10n.value("m6b.period.by \(period.authorNickname)"))
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                }
                .buttonStyle(.plain)
                Spacer()
                if isAuthor {
                    VStack(alignment: .trailing, spacing: 10) {
                        Button {
                            editing = period
                            editorPresented = true
                        } label: {
                            Image(systemName: "pencil")
                                .font(.footnote)
                                .foregroundStyle(LoveTheme.primaryAccessible)
                        }
                        .buttonStyle(.plain)
                        Button {
                            deleting = period
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

    private func rangeTitle(_ period: CareDTOs.Period) -> String {
        if let end = period.endDate {
            return M6BL10n.value("m6b.period.range \(period.startDate) \(end)")
        }
        return M6BL10n.value("m6b.period.start.only \(period.startDate)")
    }

    private func phaseInfo(_ phase: String) -> (label: String, emoji: String, tint: Color) {
        switch phase {
        case "in_period":
            return (
                M6BL10n.value("m6b.period.phase.in_period"), "🌸", LoveTheme.rose
            )
        case "due_soon":
            return (
                M6BL10n.value("m6b.period.phase.due_soon"), "⏳", LoveTheme.lavender
            )
        case "overdue":
            return (
                M6BL10n.value("m6b.period.phase.overdue"), "⏰", LoveTheme.peach
            )
        case "normal":
            return (
                M6BL10n.value("m6b.period.phase.normal"), "💚", LoveTheme.mint
            )
        default:
            return (
                M6BL10n.value("m6b.period.phase.unknown"), "🌙", LoveTheme.secondaryText
            )
        }
    }
}

// MARK: - Month calendar (self-drawn, no system DatePicker)

/// Plain SwiftUI month grid: recorded cycles paint `start_date...end_date`
/// pink (an open range runs through today), the predicted next start paints
/// lavender, today gets an outline ring. Weeks follow the user's calendar
/// (`firstWeekday`), keys are local-day `yyyy-MM-dd` strings matching the
/// wire format.
private struct PeriodCalendarView: View {
    let items: [CareDTOs.Period]
    let predictedNextStart: String?
    @Binding var month: Date

    private var calendar: Calendar { Calendar.current }

    private static let ymdFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = .current
        return formatter
    }()

    private var monthStart: Date {
        calendar.dateInterval(of: .month, for: month)?.start ?? month
    }

    private var todayKey: String {
        Self.ymdFormatter.string(from: Date())
    }

    private var dayCount: Int {
        calendar.range(of: .day, in: .month, for: monthStart)?.count ?? 30
    }

    private var leadingBlanks: Int {
        let weekday = calendar.component(.weekday, from: monthStart)
        return (weekday - calendar.firstWeekday + 7) % 7
    }

    private var weekdaySymbols: [String] {
        let symbols = calendar.veryShortWeekdaySymbols
        let offset = calendar.firstWeekday - 1
        return Array(symbols[offset...] + symbols[..<offset])
    }

    private func dayKey(_ day: Int) -> String? {
        var components = calendar.dateComponents([.year, .month], from: monthStart)
        components.day = day
        guard let date = calendar.date(from: components) else { return nil }
        return Self.ymdFormatter.string(from: date)
    }

    private func isPeriodDay(_ key: String) -> Bool {
        items.contains { record in
            record.startDate <= key && key <= (record.endDate ?? todayKey)
        }
    }

    var body: some View {
        LoveSoftCard {
            VStack(spacing: 10) {
                header
                HStack(spacing: 4) {
                    ForEach(weekdaySymbols, id: \.self) { symbol in
                        Text(verbatim: symbol)
                            .font(.caption2.weight(.medium))
                            .foregroundStyle(LoveTheme.secondaryText)
                            .frame(maxWidth: .infinity)
                    }
                }
                LazyVGrid(
                    columns: Array(
                        repeating: GridItem(.flexible(), spacing: 4), count: 7
                    ),
                    spacing: 6
                ) {
                    ForEach(0..<leadingBlanks, id: \.self) { _ in
                        Color.clear.frame(height: 34)
                    }
                    ForEach(1...dayCount, id: \.self) { day in
                        if let key = dayKey(day) {
                            dayCell(day: day, key: key)
                        } else {
                            Color.clear.frame(height: 34)
                        }
                    }
                }
                legend
            }
        }
    }

    private var header: some View {
        HStack {
            Button {
                shiftMonth(-1)
            } label: {
                Image(systemName: "chevron.left")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(LoveTheme.primaryAccessible)
                    .frame(width: 32, height: 32)
                    .background(LoveTheme.background.opacity(0.6), in: Circle())
            }
            .buttonStyle(.plain)
            Spacer()
            Text(monthStart.formatted(.dateTime.year().month()))
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(LoveTheme.text)
            Spacer()
            Button {
                shiftMonth(1)
            } label: {
                Image(systemName: "chevron.right")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(LoveTheme.primaryAccessible)
                    .frame(width: 32, height: 32)
                    .background(LoveTheme.background.opacity(0.6), in: Circle())
            }
            .buttonStyle(.plain)
        }
    }

    private var legend: some View {
        HStack(spacing: 14) {
            Circle()
                .fill(LoveTheme.pink)
                .frame(width: 10, height: 10)
            Text(.init(m6b: "m6b.period.legend.period"))
                .font(.caption2)
                .foregroundStyle(LoveTheme.secondaryText)
            Circle()
                .fill(LoveTheme.lavender.opacity(0.5))
                .frame(width: 10, height: 10)
            Text(.init(m6b: "m6b.period.legend.predicted"))
                .font(.caption2)
                .foregroundStyle(LoveTheme.secondaryText)
            Spacer()
        }
    }

    private func dayCell(day: Int, key: String) -> some View {
        let inPeriod = isPeriodDay(key)
        let predicted = predictedNextStart == key
        let isToday = key == todayKey
        return Text(verbatim: "\(day)")
            .font(.footnote.weight(inPeriod || isToday ? .semibold : .regular))
            .foregroundStyle(
                inPeriod ? .white : predicted ? LoveTheme.lavender : LoveTheme.text
            )
            .frame(maxWidth: .infinity)
            .frame(height: 34)
            .background {
                if inPeriod {
                    Circle().fill(LoveTheme.pink)
                } else if predicted {
                    Circle().fill(LoveTheme.lavender.opacity(0.22))
                } else if isToday {
                    Circle().fill(LoveTheme.outline.opacity(0.35))
                }
            }
            .overlay {
                if isToday {
                    Circle().stroke(LoveTheme.primaryAccessible, lineWidth: 1.5)
                }
            }
    }

    private func shiftMonth(_ delta: Int) {
        month = calendar.date(byAdding: .month, value: delta, to: monthStart) ?? month
    }
}

// MARK: - Editor sheet

private struct PeriodEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: PeriodViewModel
    let editing: CareDTOs.Period?

    @State private var startDate = Date()
    @State private var hasEndDate = false
    @State private var endDate = Date()
    @State private var note = ""
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    DatePicker(
                        .init(m6b: "m6b.period.editor.start"),
                        selection: $startDate,
                        displayedComponents: .date
                    )
                    .tint(LoveTheme.primaryAccessible)
                    Toggle(.init(m6b: "m6b.period.editor.hasEnd"), isOn: $hasEndDate)
                        .tint(LoveTheme.primaryAccessible)
                        .font(.footnote.weight(.medium))
                        .foregroundStyle(LoveTheme.secondaryText)
                    if hasEndDate {
                        DatePicker(
                            .init(m6b: "m6b.period.editor.end"),
                            selection: $endDate,
                            displayedComponents: .date
                        )
                        .tint(LoveTheme.primaryAccessible)
                    } else {
                        Text(.init(m6b: "m6b.period.editor.end.hint"))
                            .font(.caption)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    LoveField(labelKey: .init(m6b: "m6b.period.editor.note")) {
                        TextField(
                            M6BL10n.value("m6b.period.editor.note"),
                            text: $note,
                            axis: .vertical
                        )
                        .lineLimit(1...3)
                    }
                    if let error {
                        LoveErrorBanner(message: error)
                    }
                    LovePrimaryButton(
                        titleKey: .init(
                            m6b: editing == nil ? "m6b.period.add" : "m6b.period.edit"
                        ),
                        loading: model.saving
                    ) {
                        let values = (startDate, hasEndDate ? endDate : nil, note)
                        Task {
                            if let failure = await model.save(
                                existing: editing,
                                start: values.0,
                                end: values.1,
                                note: values.2
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
            .navigationTitle(
                .init(m6b: editing == nil ? "m6b.period.add" : "m6b.period.edit")
            )
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(M6BL10n.value("m6b.common.cancel")) { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
        .onAppear {
            if let editing {
                startDate = Self.parseDay(editing.startDate) ?? Date()
                hasEndDate = editing.endDate != nil
                endDate = editing.endDate.flatMap(Self.parseDay) ?? startDate
                note = editing.note ?? ""
            }
        }
    }

    /// Parses the `YYYY-MM-DD` contract string for the editor DatePickers.
    private static func parseDay(_ raw: String) -> Date? {
        let parser = DateFormatter()
        parser.dateFormat = "yyyy-MM-dd"
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.timeZone = .current
        return parser.date(from: raw)
    }
}
