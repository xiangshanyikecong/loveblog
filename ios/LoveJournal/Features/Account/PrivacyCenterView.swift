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
final class PrivacyViewModel {
    private(set) var loading = true
    var error: String?
    private(set) var summary: CareDTOs.PrivacySummary?

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        do {
            summary = try await api.request(
                CareDTOs.PrivacySummary.self, "GET", "/privacy/summary"
            )
            error = nil
        } catch {
            self.error = M6AErrorText.describe(error)
        }
        loading = false
    }
}

// MARK: - View

/// Read-only privacy dashboard: visibility totals, per-module access
/// breakdown, E2EE state and an account snapshot.
struct PrivacyCenterView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: PrivacyViewModel?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m6a: "m6a.privacy.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = PrivacyViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: PrivacyViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let error = model.error, model.summary == nil {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else if let summary = model.summary {
                    totalsCard(summary.totals)
                    protectionCard(summary.protection)
                    modulesCard(summary.modules)
                    encryptionCard(summary.encryption)
                    accountCard(summary.account)
                    Text(
                        String(
                            localized: "m6a.privacy.generated.at \(Format.dateTime(summary.generatedAt))",
                            table: "M6A"
                        )
                    )
                    .font(.caption2)
                    .foregroundStyle(LoveTheme.secondaryText)
                    .frame(maxWidth: .infinity, alignment: .center)
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
    }

    // MARK: Cards

    private func totalsCard(_ totals: CareDTOs.PrivacyCounts?) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.privacy.totals"))
            statGrid([
                ("m6a.privacy.access.public", totals?.`public`),
                ("m6a.privacy.access.signedin", totals?.signedIn),
                ("m6a.privacy.access.partners", totals?.partners),
                ("m6a.privacy.access.author", totals?.authorOnly),
                ("m6a.privacy.access.password", totals?.password),
            ])
        }
    }

    private func protectionCard(_ protection: CareDTOs.PrivacyCounts?) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.privacy.protection"))
            statGrid([
                ("m6a.privacy.protection.e2ee", protection?.endToEndEncrypted),
                ("m6a.privacy.protection.readable", protection?.serverReadable),
                ("m6a.privacy.protection.masked", protection?.serverMasked),
            ])
        }
    }

    private func modulesCard(_ modules: [CareDTOs.PrivacyModule]) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.privacy.modules"))
            ForEach(modules) { module in
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        Text(module.label)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(LoveTheme.text)
                        Spacer()
                        Text("\(module.total)")
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(LoveTheme.primaryAccessible)
                        protectionPill(module.protection)
                    }
                    if let access = module.access {
                        Text(accessSummary(access))
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    if let note = module.note {
                        Text(note)
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                }
                .padding(.vertical, 3)
            }
        }
    }

    private func encryptionCard(_ encryption: [CareDTOs.PrivacyEncryption]) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.privacy.encryption"))
            ForEach(encryption) { scope in
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        Text(scope.label)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(LoveTheme.text)
                        Spacer()
                        LovePill(
                            text: String(
                                localized: scope.initialized
                                    ? "m6a.privacy.encryption.on" : "m6a.privacy.encryption.off",
                                table: "M6A"
                            ),
                            tint: scope.initialized ? LoveTheme.mint : LoveTheme.secondaryText
                        )
                    }
                    Text(encryptionDetail(scope))
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                .padding(.vertical, 3)
            }
        }
    }

    private func accountCard(_ account: CareDTOs.PrivacyAccount) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.privacy.account"))
            infoRow(
                labelKey: .init(m6a: "m6a.privacy.account.nickname"),
                value: account.nickname
            )
            infoRow(
                labelKey: .init(m6a: "m6a.security.last.login"),
                value: account.lastLoginAt.map {
                    (account.lastLoginIp ?? "—") + " · " + Format.dateTime($0)
                } ?? "—"
            )
            infoRow(
                labelKey: .init(m6a: "m6a.security.password.changed"),
                value: account.passwordChangedAt.map { Format.dateTime($0) } ?? "—"
            )
            infoRow(
                labelKey: .init(m6a: "m6a.security.session.version"),
                value: "\(account.sessionVersion)"
            )
        }
    }

    // MARK: Helpers

    private func statGrid(_ stats: [(String, Int?)]) -> some View {
        let columns = [GridItem(.flexible()), GridItem(.flexible())]
        return LazyVGrid(columns: columns, spacing: 8) {
            ForEach(stats, id: \.0) { key, value in
                VStack(alignment: .leading, spacing: 2) {
                    Text(LocalizedStringKey(m6a: key))
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                    Text("\(value ?? 0)")
                        .font(.title3.weight(.bold))
                        .foregroundStyle(LoveTheme.primaryAccessible)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
                .background(LoveTheme.background.opacity(0.6))
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
        }
    }

    /// "public 12 · signed-in 3 · partners 2 · author-only 5 · password 1" —
    /// only the non-zero access buckets are listed (the count is appended to
    /// the translated label, not baked into the key).
    private func accessSummary(_ access: CareDTOs.PrivacyCounts) -> String {
        var parts: [String] = []
        func append(_ key: String, _ value: Int?) {
            guard let value, value > 0 else { return }
            parts.append(M6AL10n.value(String.LocalizationValue(key)) + " \(value)")
        }
        append("m6a.privacy.access.public", access.`public`)
        append("m6a.privacy.access.signedin", access.signedIn)
        append("m6a.privacy.access.partners", access.partners)
        append("m6a.privacy.access.author", access.authorOnly)
        append("m6a.privacy.access.password", access.password)
        return parts.joined(separator: " · ")
    }

    @ViewBuilder
    private func protectionPill(_ protection: CareDTOs.PrivacyCounts?) -> some View {
        if let protection {
            if (protection.endToEndEncrypted ?? 0) > 0 {
                LovePill(
                    text: String(localized: "m6a.privacy.protection.e2ee", table: "M6A"),
                    tint: LoveTheme.mint
                )
            } else if (protection.serverMasked ?? 0) > 0 {
                LovePill(
                    text: String(localized: "m6a.privacy.protection.masked", table: "M6A"),
                    tint: LoveTheme.lavender
                )
            } else if (protection.serverReadable ?? 0) > 0 {
                LovePill(
                    text: String(localized: "m6a.privacy.protection.readable", table: "M6A"),
                    tint: LoveTheme.secondaryText
                )
            }
        }
    }

    private func encryptionDetail(_ scope: CareDTOs.PrivacyEncryption) -> String {
        var parts: [String] = []
        if let algorithm = scope.algorithm { parts.append(algorithm) }
        if let kdf = scope.kdf {
            parts.append(
                kdf + (scope.iterations.map { " \($0)" } ?? "")
            )
        }
        parts.append(
            String(
                localized: "m6a.privacy.encryption.counts \(scope.encryptedCount) \(scope.itemCount)",
                table: "M6A"
            )
        )
        return parts.joined(separator: " · ")
    }

    private func infoRow(labelKey: LocalizedStringKey, value: String) -> some View {
        HStack(alignment: .top) {
            Text(labelKey)
                .font(.footnote)
                .foregroundStyle(LoveTheme.secondaryText)
            Spacer()
            Text(value)
                .font(.footnote.weight(.medium))
                .foregroundStyle(LoveTheme.text)
                .multilineTextAlignment(.trailing)
        }
    }
}
