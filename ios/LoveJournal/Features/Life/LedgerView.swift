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
final class LedgerViewModel {
    private(set) var loading = true
    private(set) var loadingMore = false
    private(set) var summary: LifeDTOs.LedgerSummary?
    private(set) var entries: [LifeDTOs.LedgerEntry] = []
    private(set) var hasNext = false
    private(set) var month = Date()
    var message: String?
    var error: String?
    var saving = false

    private(set) var page = 1
    private let pageSize = 30

    /// Needed to prefill the payer segment when editing (the entry only
    /// carries `payer_uid`).
    let selfUid: String?

    private let api: LoveAPIClient

    init(api: LoveAPIClient, selfUid: String?) {
        self.api = api
        self.selfUid = selfUid
    }

    func refresh() async {
        if entries.isEmpty { loading = true }
        page = 1
        let monthKey = M5CFormat.monthKey(month)
        do {
            async let summaryRequest = api.request(
                LifeDTOs.LedgerSummary.self,
                "GET",
                "/cottage/ledger/summary",
                query: [URLQueryItem(name: "month", value: monthKey)]
            )
            async let pageRequest = api.request(
                LifeDTOs.LedgerPage.self,
                "GET",
                "/cottage/ledger",
                query: [
                    URLQueryItem(name: "month", value: monthKey),
                    URLQueryItem(name: "page", value: "1"),
                    URLQueryItem(name: "page_size", value: String(pageSize)),
                ]
            )
            let (loadedSummary, loadedPage) = try await (summaryRequest, pageRequest)
            summary = loadedSummary
            entries = loadedPage.items
            hasNext = loadedPage.hasNext
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? M5CL10n.value("m5c.ledger.failed")
        }
        loading = false
    }

    func changeMonth(by delta: Int) async {
        guard let next = Calendar.current.date(byAdding: .month, value: delta, to: month) else {
            return
        }
        month = next
        entries = []
        summary = nil
        hasNext = false
        await refresh()
    }

    func loadMore() async {
        guard hasNext, !loadingMore else { return }
        loadingMore = true
        defer { loadingMore = false }
        let nextPage = page + 1
        do {
            let pageResult = try await api.request(
                LifeDTOs.LedgerPage.self,
                "GET",
                "/cottage/ledger",
                query: [
                    URLQueryItem(name: "month", value: M5CFormat.monthKey(month)),
                    URLQueryItem(name: "page", value: String(nextPage)),
                    URLQueryItem(name: "page_size", value: String(pageSize)),
                ]
            )
            page = nextPage
            entries += pageResult.items
            hasNext = pageResult.hasNext
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.ledger.failed")
        }
    }

    /// Returns true when the sheet should close.
    func save(
        existing: LifeDTOs.LedgerEntry?,
        title: String,
        amountText: String,
        category: String?,
        payer: String,
        splitType: String,
        spentOn: Date,
        note: String
    ) async -> Bool {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty else {
            message = M5CL10n.value("m5c.ledger.need.title")
            return false
        }
        let normalized = amountText
            .replacingOccurrences(of: ",", with: ".")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard let yuan = Double(normalized), yuan > 0, yuan <= 10_000_000 else {
            message = M5CL10n.value("m5c.ledger.amount.invalid")
            return false
        }
        let cents = Int((yuan * 100).rounded())
        saving = true
        defer { saving = false }
        let body = LifeDTOs.LedgerUpsert(
            title: trimmedTitle,
            amountCents: cents,
            note: normalizedOptional(note),
            category: normalizedOptional(category ?? ""),
            payer: payer,
            splitType: splitType,
            spentOn: Format.date(spentOn)
        )
        do {
            if let existing {
                _ = try await api.request(
                    LifeDTOs.LedgerEntry.self, "PATCH", "/cottage/ledger/\(existing.leid)", body: body
                )
                message = M5CL10n.value("m5c.ledger.updated")
            } else {
                _ = try await api.request(
                    LifeDTOs.LedgerEntry.self, "POST", "/cottage/ledger", body: body
                )
                message = M5CL10n.value("m5c.ledger.created")
            }
            await refresh()
            return true
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.ledger.failed")
            return false
        }
    }

    func delete(_ entry: LifeDTOs.LedgerEntry) async {
        do {
            try await api.requestVoid("DELETE", "/cottage/ledger/\(entry.leid)")
            message = M5CL10n.value("m5c.ledger.deleted")
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.ledger.failed")
        }
    }

    private func normalizedOptional(_ raw: String) -> String? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

struct LedgerView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: LedgerViewModel?
    @State private var editorPresented = false
    @State private var editing: LifeDTOs.LedgerEntry?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m5c: "m5c.ledger.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                let uid: String?
                if case .loggedIn(let profile) = environment.session.state {
                    uid = profile.uid
                } else {
                    uid = nil
                }
                model = LedgerViewModel(api: environment.api, selfUid: uid)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: LedgerViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error, model.entries.isEmpty {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else {
                    monthHeader(model)
                    if let summary = model.summary {
                        summaryCard(summary)
                    }
                    if model.entries.isEmpty {
                        LoveEmptyState(
                            systemImage: "yensign.circle",
                            titleKey: .init(m5c: "m5c.ledger.empty"),
                            messageKey: .init(m5c: "m5c.ledger.empty.hint")
                        )
                    } else {
                        ForEach(model.entries) { entry in
                            entryCard(entry, model: model)
                        }
                        loadMoreRow(model)
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
                Label(.init(m5c: "m5c.ledger.new"), systemImage: "plus")
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
            LedgerEditorSheet(model: model, editing: editing)
        }
    }

    private func monthHeader(_ model: LedgerViewModel) -> some View {
        LoveSoftCard {
            HStack {
                Button {
                    Task { await model.changeMonth(by: -1) }
                } label: {
                    Image(systemName: "chevron.left")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.primaryAccessible)
                        .frame(width: 36, height: 36)
                }
                .buttonStyle(.plain)
                Spacer()
                Text(M5CFormat.monthLabel(model.month))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                Spacer()
                Button {
                    Task { await model.changeMonth(by: 1) }
                } label: {
                    Image(systemName: "chevron.right")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.primaryAccessible)
                        .frame(width: 36, height: 36)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func summaryCard(_ summary: LifeDTOs.LedgerSummary) -> some View {
        LoveSoftCard {
            HStack(alignment: .firstTextBaseline) {
                Text("m5c.ledger.summary.total \(M5CFormat.money(summary.totalSpentCents))", tableName: "M5C")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                Spacer()
                Text("m5c.ledger.summary.count \(summary.entryCount)", tableName: "M5C")
                    .font(.caption)
                    .foregroundStyle(LoveTheme.secondaryText)
            }

            if !summary.byPayer.isEmpty {
                breakdownSection(titleKey: "m5c.ledger.summary.by.payer") {
                    ForEach(summary.byPayer, id: \.uid) { row in
                        breakdownRow(row.nickname, M5CFormat.money(row.paidCents))
                    }
                }
            }

            if !summary.byCategory.isEmpty {
                breakdownSection(titleKey: "m5c.ledger.summary.by.category") {
                    ForEach(summary.byCategory, id: \.category) { row in
                        breakdownRow(
                            M5CFormat.categoryLabel(row.category) ?? row.category,
                            M5CFormat.money(row.amountCents)
                        )
                    }
                }
            }

            balanceView(summary.balance)
        }
    }

    private func breakdownSection<Rows: View>(
        titleKey: String,
        @ViewBuilder rows: () -> Rows
    ) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(.init(m5c: titleKey))
                .font(.footnote.weight(.medium))
                .foregroundStyle(LoveTheme.secondaryText)
            VStack(alignment: .leading, spacing: 4) {
                rows()
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(LoveTheme.background.opacity(0.6), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private func breakdownRow(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label)
                .font(.footnote)
                .foregroundStyle(LoveTheme.text)
            Spacer()
            Text(value)
                .font(.footnote.weight(.semibold))
                .foregroundStyle(LoveTheme.text)
        }
    }

    @ViewBuilder
    private func balanceView(_ balance: LifeDTOs.LedgerBalance) -> some View {
        if balance.settled {
            LovePill(text: M5CL10n.value("m5c.ledger.balance.settled"), tint: LoveTheme.mint)
        } else if let debtor = balance.debtorNickname,
            let creditor = balance.creditorNickname,
            balance.amountCents > 0
        {
            Text(
                "m5c.ledger.balance.owes \(debtor) \(creditor) \(M5CFormat.money(balance.amountCents))",
                tableName: "M5C"
            )
                .font(.footnote.weight(.semibold))
                .foregroundStyle(LoveTheme.rose)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
                .background(LoveTheme.rose.opacity(0.1), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
    }

    private func entryCard(_ entry: LifeDTOs.LedgerEntry, model: LedgerViewModel) -> some View {
        LoveSoftCard {
            HStack(alignment: .top, spacing: 12) {
                Button {
                    editing = entry
                    editorPresented = true
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(entry.title)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.text)
                        HStack(spacing: 8) {
                            splitPill(entry.splitType)
                            if let category = M5CFormat.categoryLabel(entry.category) {
                                LovePill(text: category, tint: LoveTheme.lavender)
                            }
                        }
                        HStack(spacing: 6) {
                            Text(entry.payerNickname)
                            Text("·")
                            Text(entry.spentOn)
                        }
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                        if let note = entry.note, !note.isEmpty {
                            Text(note)
                                .font(.caption2)
                                .foregroundStyle(LoveTheme.secondaryText)
                                .lineLimit(2)
                        }
                    }
                }
                .buttonStyle(.plain)
                Spacer()
                VStack(alignment: .trailing, spacing: 8) {
                    Text(M5CFormat.money(entry.amountCents))
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.primaryAccessible)
                    Button {
                        Task { await model.delete(entry) }
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

    @ViewBuilder
    private func loadMoreRow(_ model: LedgerViewModel) -> some View {
        if model.loadingMore {
            ProgressView()
                .tint(LoveTheme.primaryAccessible)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 4)
        } else if model.hasNext {
            LoveSecondaryButton(titleKey: .init(m5c: "m5c.ledger.load.more")) {
                Task { await model.loadMore() }
            }
        }
    }

    private func splitPill(_ splitType: String) -> some View {
        switch splitType {
        case "treat":
            return LovePill(
                text: M5CL10n.value("m5c.ledger.split.treat"),
                tint: LoveTheme.peach
            )
        case "owed_full":
            return LovePill(
                text: M5CL10n.value("m5c.ledger.split.owed_full"),
                tint: LoveTheme.rose
            )
        default:
            return LovePill(
                text: M5CL10n.value("m5c.ledger.split.aa"),
                tint: LoveTheme.mint
            )
        }
    }
}

// MARK: - Editor sheet

private struct LedgerEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: LedgerViewModel
    let editing: LifeDTOs.LedgerEntry?

    @State private var title = ""
    @State private var amountText = ""
    @State private var category: String?
    @State private var payer = "me"
    @State private var splitType = "aa"
    @State private var spentOn = Date()
    @State private var note = ""

    private let chipColumns = [
        GridItem(.adaptive(minimum: 76), spacing: 8)
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: .init(m5c: "m5c.ledger.editor.title")) {
                        TextField(M5CL10n.value("m5c.ledger.editor.title"), text: $title)
                    }
                    LoveField(labelKey: .init(m5c: "m5c.ledger.editor.amount")) {
                        TextField("0.00", text: $amountText)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.leading)
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        Text(.init(m5c: "m5c.ledger.editor.category"))
                            .font(.footnote.weight(.medium))
                            .foregroundStyle(LoveTheme.secondaryText)
                        LazyVGrid(columns: chipColumns, spacing: 8) {
                            ForEach(M5CFormat.categoryKeys, id: \.self) { key in
                                categoryChip(key)
                            }
                        }
                    }
                    Picker(.init(m5c: "m5c.ledger.editor.payer"), selection: $payer) {
                        Text(.init(m5c: "m5c.ledger.payer.me")).tag("me")
                        Text(.init(m5c: "m5c.ledger.payer.partner")).tag("partner")
                    }
                    .pickerStyle(.segmented)
                    Picker(.init(m5c: "m5c.ledger.editor.split"), selection: $splitType) {
                        Text(.init(m5c: "m5c.ledger.split.aa")).tag("aa")
                        Text(.init(m5c: "m5c.ledger.split.treat")).tag("treat")
                        Text(.init(m5c: "m5c.ledger.split.owed_full")).tag("owed_full")
                    }
                    .pickerStyle(.segmented)
                    DatePicker(
                        .init(m5c: "m5c.ledger.editor.date"),
                        selection: $spentOn,
                        displayedComponents: .date
                    )
                    .tint(LoveTheme.primaryAccessible)
                    LoveField(labelKey: .init(m5c: "m5c.ledger.editor.note")) {
                        TextField(
                            M5CL10n.value("m5c.ledger.editor.note.placeholder"),
                            text: $note,
                            axis: .vertical
                        )
                        .lineLimit(2...4)
                    }
                    if let message = model.message {
                        LoveErrorBanner(message: message)
                    }
                    LovePrimaryButton(
                        titleKey: editing == nil
                            ? .init(m5c: "m5c.ledger.add")
                            : .init(m5c: "m5c.common.save"),
                        loading: model.saving
                    ) {
                        let values = (title, amountText, category, payer, splitType, spentOn, note)
                        Task {
                            if await model.save(
                                existing: editing,
                                title: values.0,
                                amountText: values.1,
                                category: values.2,
                                payer: values.3,
                                splitType: values.4,
                                spentOn: values.5,
                                note: values.6
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
                    ? .init(m5c: "m5c.ledger.new")
                    : .init(m5c: "m5c.ledger.edit")
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
                amountText = String(format: "%.2f", Double(editing.amountCents) / 100.0)
                category = editing.category
                payer = model.selfUid == nil || editing.payerUid == model.selfUid ? "me" : "partner"
                splitType = editing.splitType
                spentOn = Self.dayParser.date(from: editing.spentOn) ?? Date()
                note = editing.note ?? ""
            }
        }
    }

    private func categoryChip(_ key: String) -> some View {
        let selected = category == key
        return Button {
            category = selected ? nil : key
        } label: {
            Text(M5CFormat.categoryLabel(key) ?? key)
                .font(.footnote.weight(.medium))
                .foregroundStyle(selected ? .white : LoveTheme.primaryAccessible)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(
                    selected
                        ? AnyShapeStyle(LoveTheme.gradient)
                        : AnyShapeStyle(LoveTheme.primaryAccessible.opacity(0.1)),
                    in: Capsule()
                )
        }
        .buttonStyle(.plain)
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
