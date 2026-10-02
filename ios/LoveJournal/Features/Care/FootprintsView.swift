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

// MARK: - Footprints view model

@MainActor
@Observable
final class FootprintsViewModel {
    var loading = true
    var error: String?
    private(set) var footprints: CareDTOs.Footprints?

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        if footprints == nil { loading = true }
        do {
            footprints = try await api.request(
                CareDTOs.Footprints.self, "GET", "/cottage/footprints"
            )
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? M6BL10n.value("m6b.common.load.failed")
        }
        loading = false
    }
}

// MARK: - Footprints screen

/// Read-only city list + recent check-in feed (source of truth is the
/// location check-in module; no map coordinates in the contract).
struct FootprintsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: FootprintsViewModel?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m6b: "m6b.footprints.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = FootprintsViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: FootprintsViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let error = model.error, model.footprints == nil {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else if let data = model.footprints,
                    !data.cities.isEmpty || !data.recent.isEmpty {
                    headerCard(data)
                    if !data.cities.isEmpty {
                        Text(.init(m6b: "m6b.footprints.cities.section"))
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.secondaryText)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        ForEach(Array(data.cities.enumerated()), id: \.element.id) {
                            index, city in
                            cityCard(city, rank: index)
                        }
                    }
                    if !data.recent.isEmpty {
                        Text(.init(m6b: "m6b.footprints.recent.section"))
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.secondaryText)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        recentCard(data.recent)
                    }
                } else {
                    LoveEmptyState(
                        systemImage: "map",
                        titleKey: .init(m6b: "m6b.footprints.empty"),
                        messageKey: .init(m6b: "m6b.footprints.empty.hint")
                    )
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
    }

    // MARK: Sections

    private func headerCard(_ data: CareDTOs.Footprints) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 6) {
                Text(verbatim: "🗺️")
                    .font(.title3)
                Text(
                    verbatim: M6BL10n.value(
                        "m6b.footprints.summary \(data.totalCities) \(data.totalCheckins)"
                    )
                )
                .font(.title3.weight(.bold))
                .foregroundStyle(LoveTheme.primaryAccessible)
            }
        }
    }

    private func cityCard(_ city: CareDTOs.FootprintCity, rank: Int) -> some View {
        LoveSoftCard {
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        if rank == 0 {
                            Text(verbatim: "👑")
                                .font(.footnote)
                        } else if rank < 3 {
                            Text(verbatim: "⭐️")
                                .font(.footnote)
                        }
                        Text(city.city)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.text)
                    }
                    Text(verbatim: cityRange(city))
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 5) {
                    LovePill(
                        text: M6BL10n.value("m6b.common.times \(city.count)"),
                        tint: rank == 0 ? LoveTheme.primaryAccessible : LoveTheme.lavender
                    )
                    if rank == 0 {
                        LovePill(
                            text: M6BL10n.value("m6b.footprints.most.visited"),
                            tint: LoveTheme.peach
                        )
                    }
                }
            }
        }
    }

    private func recentCard(_ recent: [CareDTOs.FootprintRecent]) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(recent) { item in
                    HStack(alignment: .top, spacing: 10) {
                        Text(verbatim: "📍")
                            .font(.footnote)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(
                                verbatim: M6BL10n.value(
                                    "m6b.footprints.recent.row \(item.authorNickname) \(item.city)"
                                )
                            )
                            .font(.footnote.weight(.medium))
                            .foregroundStyle(LoveTheme.text)
                            Text(Format.dateTime(item.createdAt))
                                .font(.caption2)
                                .foregroundStyle(LoveTheme.secondaryText)
                        }
                        Spacer(minLength: 0)
                    }
                }
            }
        }
    }

    private func cityRange(_ city: CareDTOs.FootprintCity) -> String {
        switch (city.firstAt, city.lastAt) {
        case let (first?, last?):
            return M6BL10n.value(
                "m6b.footprints.range \(Format.dateTime(first)) \(Format.dateTime(last))"
            )
        case let (nil, last?):
            return Format.dateTime(last)
        default:
            return ""
        }
    }
}
