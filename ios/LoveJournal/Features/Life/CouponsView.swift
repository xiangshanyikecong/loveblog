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
final class CouponsViewModel {
    private(set) var loading = true
    private(set) var items: [LifeDTOs.Coupon] = []
    private(set) var active = 0
    private(set) var redeemed = 0
    /// all | sent | received
    var box = "all"
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
                LifeDTOs.CouponList.self,
                "GET",
                "/cottage/coupons",
                query: [URLQueryItem(name: "box", value: box)]
            )
            items = list.items
            active = list.active
            redeemed = list.redeemed
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? M5CL10n.value("m5c.coupons.failed")
        }
        loading = false
    }

    /// Redemption is partner-only and one-shot; the card gates the button on
    /// `!isMine` and the view asks for confirmation first.
    func redeem(_ coupon: LifeDTOs.Coupon) async {
        do {
            _ = try await api.request(
                LifeDTOs.Coupon.self, "POST", "/cottage/coupons/\(coupon.cpid)/redeem"
            )
            message = M5CL10n.value("m5c.coupons.redeemed.done")
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.coupons.failed")
        }
    }

    func delete(_ coupon: LifeDTOs.Coupon) async {
        do {
            try await api.requestVoid("DELETE", "/cottage/coupons/\(coupon.cpid)")
            message = M5CL10n.value("m5c.coupons.deleted")
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.coupons.failed")
        }
    }

    /// Create or update (PATCH is author-only and active-only; the card only
    /// offers editing in that case). Returns true when the sheet should close.
    func save(
        existing: LifeDTOs.Coupon?, title: String, description: String, icon: String
    ) async -> Bool {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty else {
            message = M5CL10n.value("m5c.coupons.need.title")
            return false
        }
        saving = true
        defer { saving = false }
        let emoji = icon.trimmingCharacters(in: .whitespacesAndNewlines)
        let body = LifeDTOs.CouponCreate(
            title: trimmedTitle,
            description: normalizedOptional(description),
            icon: emoji.isEmpty ? nil : String(emoji.prefix(1))
        )
        do {
            if let existing {
                _ = try await api.request(
                    LifeDTOs.Coupon.self, "PATCH", "/cottage/coupons/\(existing.cpid)", body: body
                )
                message = M5CL10n.value("m5c.coupons.updated")
            } else {
                _ = try await api.request(
                    LifeDTOs.Coupon.self, "POST", "/cottage/coupons", body: body
                )
                message = M5CL10n.value("m5c.coupons.created")
            }
            await refresh()
            return true
        } catch {
            message = (error as? APIError)?.message ?? M5CL10n.value("m5c.coupons.failed")
            return false
        }
    }

    private func normalizedOptional(_ raw: String) -> String? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

struct CouponsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: CouponsViewModel?
    @State private var editorPresented = false
    @State private var editing: LifeDTOs.Coupon?
    @State private var redeeming: LifeDTOs.Coupon?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m5c: "m5c.coupons.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = CouponsViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: CouponsViewModel) -> some View {
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
                            systemImage: "ticket",
                            titleKey: .init(m5c: "m5c.coupons.empty"),
                            messageKey: .init(m5c: "m5c.coupons.empty.hint")
                        )
                    } else {
                        ForEach(model.items) { coupon in
                            couponCard(coupon, model: model)
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
                Label(.init(m5c: "m5c.coupons.new"), systemImage: "plus")
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
            CouponEditorSheet(model: model, editing: editing)
        }
        .confirmationDialog(
            Text(redeeming == nil ? "" : M5CL10n.value("m5c.coupons.redeem.confirm")),
            isPresented: Binding(
                get: { redeeming != nil },
                set: { if !$0 { redeeming = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button(M5CL10n.value("m5c.coupons.redeem"), role: .destructive) {
                if let coupon = redeeming {
                    Task { await model.redeem(coupon) }
                }
                redeeming = nil
            }
            Button(M5CL10n.value("m5c.common.cancel"), role: .cancel) {
                redeeming = nil
            }
        }
    }

    private func header(_ model: CouponsViewModel) -> some View {
        VStack(spacing: 10) {
            Text("m5c.coupons.count \(model.active) \(model.redeemed)", tableName: "M5C")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(LoveTheme.secondaryText)
                .frame(maxWidth: .infinity, alignment: .leading)
            Picker(
                selection: Binding(
                    get: { model.box },
                    set: { newValue in
                        model.box = newValue
                        Task { await model.refresh() }
                    }
                )
            ) {
                Text(.init(m5c: "m5c.coupons.box.all")).tag("all")
                Text(.init(m5c: "m5c.coupons.box.sent")).tag("sent")
                Text(.init(m5c: "m5c.coupons.box.received")).tag("received")
            } label: {
                EmptyView()
            }
            .pickerStyle(.segmented)
        }
    }

    private func couponCard(_ coupon: LifeDTOs.Coupon, model: CouponsViewModel) -> some View {
        LoveSoftCard {
            HStack(alignment: .top, spacing: 12) {
                Text(iconText(coupon))
                    .font(.title2)

                bodyButton(coupon)

                Spacer()

                VStack(alignment: .trailing, spacing: 10) {
                    if coupon.isRedeemed {
                        if let redeemedAt = coupon.redeemedAt {
                            Text("m5c.coupons.redeemed.at \(Format.dateTime(redeemedAt))", tableName: "M5C")
                                .font(.caption2)
                                .foregroundStyle(LoveTheme.secondaryText)
                        }
                    } else if !coupon.isMine {
                        Button {
                            redeeming = coupon
                        } label: {
                            Text(M5CL10n.value("m5c.coupons.redeem"))
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 7)
                                .background(LoveTheme.gradient, in: Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                    Button {
                        Task { await model.delete(coupon) }
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

    /// Tapping the body opens the editor — only the author may edit, and only
    /// while the coupon is still active.
    @ViewBuilder
    private func bodyButton(_ coupon: LifeDTOs.Coupon) -> some View {
        let details = VStack(alignment: .leading, spacing: 4) {
            Text(coupon.title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(LoveTheme.text)
            if let description = coupon.description, !description.isEmpty {
                Text(description)
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
                    .lineLimit(2)
            }
            Text("m5c.coupons.by \(coupon.authorNickname)", tableName: "M5C")
                .font(.caption2)
                .foregroundStyle(LoveTheme.secondaryText)
            if coupon.isRedeemed {
                LovePill(
                    text: M5CL10n.value("m5c.coupons.redeemed"),
                    tint: LoveTheme.mint
                )
            }
        }
        if coupon.isMine && !coupon.isRedeemed {
            Button {
                editing = coupon
                editorPresented = true
            } label: {
                details
            }
            .buttonStyle(.plain)
        } else {
            details
        }
    }

    private func iconText(_ coupon: LifeDTOs.Coupon) -> String {
        if let icon = coupon.icon, !icon.isEmpty {
            return icon
        }
        return "🎟️"
    }
}

// MARK: - Editor sheet

private struct CouponEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: CouponsViewModel
    let editing: LifeDTOs.Coupon?

    @State private var title = ""
    @State private var description = ""
    @State private var icon = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: .init(m5c: "m5c.coupons.editor.title")) {
                        TextField(M5CL10n.value("m5c.coupons.editor.title"), text: $title)
                    }
                    LoveField(labelKey: .init(m5c: "m5c.coupons.editor.description")) {
                        TextField(
                            M5CL10n.value("m5c.coupons.editor.description"),
                            text: $description,
                            axis: .vertical
                        )
                        .lineLimit(2...4)
                    }
                    LoveField(labelKey: .init(m5c: "m5c.coupons.editor.icon")) {
                        TextField("🎟️", text: $icon)
                            .multilineTextAlignment(.center)
                    }
                    if let message = model.message {
                        LoveErrorBanner(message: message)
                    }
                    LovePrimaryButton(
                        titleKey: editing == nil
                            ? .init(m5c: "m5c.coupons.add")
                            : .init(m5c: "m5c.common.save"),
                        loading: model.saving
                    ) {
                        let values = (title, description, icon)
                        Task {
                            if await model.save(
                                existing: editing,
                                title: values.0,
                                description: values.1,
                                icon: values.2
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
                    ? .init(m5c: "m5c.coupons.new")
                    : .init(m5c: "m5c.coupons.edit")
            )
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(M5CL10n.value("m5c.common.cancel")) { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
        .onAppear {
            if let editing {
                title = editing.title
                description = editing.description ?? ""
                icon = editing.icon ?? ""
            }
        }
        .onChange(of: icon) { _, newValue in
            // Single-grapheme emoji input: keep the first character only.
            let limited = String(newValue.prefix(1))
            if limited != newValue {
                icon = limited
            }
        }
    }
}
