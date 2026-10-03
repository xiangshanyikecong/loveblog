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
import UIKit

import LoveCore

// MARK: - Reports view model

@MainActor
@Observable
final class ReportsViewModel {
    var monthlyLoading = false
    var monthlyError: String?
    var annualLoading = false
    var annualError: String?

    private(set) var monthly: CareDTOs.MonthlyReport?
    private(set) var annual: CareDTOs.AnnualReport?

    /// AI monthly copy (visible only when the instance advertises it).
    private(set) var aiStatus: AIDTOs.Status?
    var aiText: String?
    var aiLoading = false
    var aiError: String?

    let currentYear: Int

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
        currentYear = Calendar.current.component(.year, from: Date())
    }

    var availableYears: [Int] {
        Array((currentYear - 4)...max(currentYear - 4, currentYear)).reversed()
    }

    func loadAIStatusIfNeeded() async {
        guard aiStatus == nil else { return }
        aiStatus = try? await api.aiStatus()
    }

    func loadMonthly(year: Int, month: Int, force: Bool = false) async {
        if let report = monthly, !force, report.year == year, report.month == month {
            return
        }
        monthlyLoading = true
        do {
            monthly = try await api.request(
                CareDTOs.MonthlyReport.self,
                "GET",
                "/cottage/reports/monthly",
                query: [
                    URLQueryItem(name: "year", value: "\(year)"),
                    URLQueryItem(name: "month", value: "\(month)"),
                ]
            )
            monthlyError = nil
        } catch {
            monthlyError = (error as? APIError)?.message ?? M6BL10n.value("m6b.common.load.failed")
        }
        monthlyLoading = false
    }

    /// Note: annual reports live under `/reports` (no `cottage` prefix).
    func loadAnnual(year: Int, force: Bool = false) async {
        if let report = annual, !force, report.year == year {
            return
        }
        annualLoading = true
        do {
            annual = try await api.request(
                CareDTOs.AnnualReport.self,
                "GET",
                "/reports/annual",
                query: [URLQueryItem(name: "year", value: "\(year)")]
            )
            annualError = nil
        } catch {
            annualError = (error as? APIError)?.message ?? M6BL10n.value("m6b.common.load.failed")
        }
        annualLoading = false
    }

    /// `POST /ai/report/monthly` — AI-written summary for the selected month.
    func generateAICopy(year: Int, month: Int) async {
        guard !aiLoading else { return }
        aiLoading = true
        aiError = nil
        do {
            let response = try await api.aiMonthlyReport(year: year, month: month)
            aiText = response.text
        } catch {
            aiError = AIFeature.message(for: error)
        }
        aiLoading = false
    }
}

// MARK: - Reports screen

private enum ReportTab: Hashable {
    case monthly
    case annual
}

private enum ChartSeries: Hashable {
    case articles
    case songs
    case checkins
}

struct ReportsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: ReportsViewModel?
    @State private var tab: ReportTab = .monthly
    @State private var year = Calendar.current.component(.year, from: Date())
    @State private var month = Calendar.current.component(.month, from: Date())
    @State private var series: ChartSeries = .articles
    @State private var aiCopied = false

    private var taskKey: String {
        "\(tab == .monthly ? "monthly" : "annual")/\(year)/\(month)"
    }

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m6b: "m6b.reports.title"))
        .navigationBarTitleDisplayMode(.inline)
        .task(id: taskKey) {
            if model == nil {
                model = ReportsViewModel(api: environment.api)
            }
            guard let model else { return }
            switch tab {
            case .monthly:
                await model.loadMonthly(year: year, month: month)
            case .annual:
                await model.loadAnnual(year: year)
            }
        }
        .task {
            await model?.loadAIStatusIfNeeded()
        }
    }

    private func content(_ model: ReportsViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                Picker(.init(m6b: "m6b.reports.title"), selection: $tab) {
                    Text(.init(m6b: "m6b.reports.tab.monthly")).tag(ReportTab.monthly)
                    Text(.init(m6b: "m6b.reports.tab.annual")).tag(ReportTab.annual)
                }
                .pickerStyle(.segmented)
                periodPicker(model)
                switch tab {
                case .monthly:
                    monthlySection(model)
                case .annual:
                    annualSection(model)
                }
            }
            .padding(16)
        }
        .refreshable {
            switch tab {
            case .monthly:
                await model.loadMonthly(year: year, month: month, force: true)
            case .annual:
                await model.loadAnnual(year: year, force: true)
            }
        }
    }

    // MARK: Year / month pickers

    private func periodPicker(_ model: ReportsViewModel) -> some View {
        HStack(spacing: 12) {
            yearMenu(model)
            if tab == .monthly {
                monthMenu
            }
        }
        .frame(maxWidth: .infinity)
    }

    private func yearMenu(_ model: ReportsViewModel) -> some View {
        Menu {
            ForEach(model.availableYears, id: \.self) { candidate in
                Button(M6BL10n.value("m6b.reports.year \(candidate)")) {
                    year = candidate
                }
            }
        } label: {
            menuLabel(M6BL10n.value("m6b.reports.year \(year)"))
        }
    }

    private var monthMenu: some View {
        Menu {
            ForEach(1...12, id: \.self) { candidate in
                Button(M6BL10n.value("m6b.reports.month \(candidate)")) {
                    month = candidate
                }
            }
        } label: {
            menuLabel(M6BL10n.value("m6b.reports.month \(month)"))
        }
    }

    private func menuLabel(_ text: String) -> some View {
        HStack(spacing: 4) {
            Text(verbatim: text)
                .font(.subheadline.weight(.semibold))
            Image(systemName: "chevron.down")
                .font(.caption2)
        }
        .foregroundStyle(LoveTheme.primaryAccessible)
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(LoveTheme.surface, in: Capsule())
        .overlay(Capsule().stroke(LoveTheme.outline, lineWidth: 1))
    }

    // MARK: Monthly report

    @ViewBuilder
    private func monthlySection(_ model: ReportsViewModel) -> some View {
        if model.monthlyLoading, model.monthly == nil {
            LoveLoadingView()
        } else if let error = model.monthlyError, model.monthly == nil {
            LoveErrorView(message: error) {
                Task { await model.loadMonthly(year: year, month: month, force: true) }
            }
        } else if let report = model.monthly {
            monthlyStatsGrid(report.stats)
            if model.aiStatus?.supports(AIDTOs.Feature.monthlyReport) == true {
                aiCopySection(model)
            }
            if !report.topMoods.isEmpty {
                moodsCard(report.topMoods)
            }
            if !report.highlights.isEmpty {
                VStack(spacing: 8) {
                    Text(.init(m6b: "m6b.reports.highlights.section"))
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.secondaryText)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(report.highlights) { highlight in
                        highlightCard(highlight)
                    }
                }
            }
        }
    }

    // MARK: AI monthly copy

    private func aiCopySection(_ model: ReportsViewModel) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    LoveSectionTitle(textKey: "ai.report.card.title")
                    Spacer()
                    if let text = model.aiText {
                        Button {
                            UIPasteboard.general.string = text
                            aiCopied = true
                            DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) {
                                aiCopied = false
                            }
                        } label: {
                            Label(
                                aiCopied ? String(localized: "common.copied") : String(localized: "common.copy"),
                                systemImage: aiCopied ? "checkmark" : "doc.on.doc"
                            )
                            .font(.caption.weight(.semibold))
                        }
                        .foregroundStyle(LoveTheme.primaryAccessible)
                    }
                }
                if model.aiLoading {
                    HStack(spacing: 8) {
                        ProgressView().tint(LoveTheme.primaryAccessible)
                        Text("ai.generating")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                }
                if let text = model.aiText {
                    Text(text)
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.text)
                        .lineSpacing(4)
                }
                if let aiError = model.aiError {
                    LoveErrorBanner(message: aiError)
                }
                LoveSecondaryButton(titleKey: "ai.report.button", loading: model.aiLoading) {
                    let targetYear = year
                    let targetMonth = month
                    Task { await model.generateAICopy(year: targetYear, month: targetMonth) }
                }
            }
        }
    }

    private func monthlyStatsGrid(_ stats: CareDTOs.MonthlyStats) -> some View {
        let entries: [(key: String, value: Int)] = [
            ("m6b.reports.stat.checkins", stats.checkins),
            ("m6b.reports.stat.moods", stats.moods),
            ("m6b.reports.stat.questions", stats.questions),
            ("m6b.reports.stat.answers", stats.answers),
            ("m6b.reports.stat.chat.messages", stats.chatMessages),
            ("m6b.reports.stat.wishes.created", stats.wishesCreated),
            ("m6b.reports.stat.wishes.completed", stats.wishesCompleted),
            ("m6b.reports.stat.plans.created", stats.plansCreated),
            ("m6b.reports.stat.plans.completed", stats.plansCompleted),
            ("m6b.reports.stat.reminders.created", stats.remindersCreated),
        ]
        return LoveSoftCard {
            LazyVGrid(
                columns: [
                    GridItem(.flexible(), spacing: 12),
                    GridItem(.flexible(), spacing: 12),
                ],
                spacing: 14
            ) {
                ForEach(entries, id: \.key) { entry in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(verbatim: "\(entry.value)")
                            .font(.title3.weight(.bold))
                            .foregroundStyle(LoveTheme.primaryAccessible)
                        Text(M6BL10n.value(String.LocalizationValue(entry.key)))
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    private func moodsCard(_ moods: [CareDTOs.MoodCount]) -> some View {
        let maxCount = max(1, moods.map(\.count).max() ?? 1)
        return LoveSoftCard {
            VStack(alignment: .leading, spacing: 10) {
                Text(.init(m6b: "m6b.reports.moods.section"))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                ForEach(moods) { mood in
                    HStack(spacing: 10) {
                        Text(verbatim: "\(mood.emoji ?? "💗") \(mood.mood)")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.text)
                            .lineLimit(1)
                            .frame(width: 108, alignment: .leading)
                        GeometryReader { geo in
                            ZStack(alignment: .leading) {
                                Capsule()
                                    .fill(LoveTheme.outline.opacity(0.4))
                                Capsule()
                                    .fill(LoveTheme.gradient)
                                    .frame(
                                        width: max(
                                            6,
                                            geo.size.width * CGFloat(mood.count) / CGFloat(maxCount)
                                        )
                                    )
                            }
                        }
                        .frame(height: 10)
                        Text(verbatim: M6BL10n.value("m6b.common.times \(mood.count)"))
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                            .frame(width: 42, alignment: .trailing)
                    }
                }
            }
        }
    }

    private func highlightCard(_ highlight: CareDTOs.ReportHighlight) -> some View {
        LoveSoftCard {
            HStack(alignment: .top, spacing: 10) {
                LovePill(text: highlightKindLabel(highlight.kind), tint: highlightTint(highlight.kind))
                VStack(alignment: .leading, spacing: 3) {
                    Text(highlight.title)
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(LoveTheme.text)
                    if let subtitle = highlight.subtitle, !subtitle.isEmpty {
                        Text(subtitle)
                            .font(.caption)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    if let occurredAt = highlight.occurredAt {
                        Text(Format.dateTime(occurredAt))
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                }
            }
        }
    }

    private func highlightKindLabel(_ kind: String) -> String {
        switch kind {
        case "wish":
            return M6BL10n.value("m6b.reports.highlight.wish")
        case "plan":
            return M6BL10n.value("m6b.reports.highlight.plan")
        case "question":
            return M6BL10n.value("m6b.reports.highlight.question")
        default:
            return kind
        }
    }

    private func highlightTint(_ kind: String) -> Color {
        switch kind {
        case "wish": LoveTheme.rose
        case "plan": LoveTheme.lavender
        case "question": LoveTheme.mint
        default: LoveTheme.primaryAccessible
        }
    }

    // MARK: Annual report

    @ViewBuilder
    private func annualSection(_ model: ReportsViewModel) -> some View {
        if model.annualLoading, model.annual == nil {
            LoveLoadingView()
        } else if let error = model.annualError, model.annual == nil {
            LoveErrorView(message: error) {
                Task { await model.loadAnnual(year: year, force: true) }
            }
        } else if let report = model.annual {
            daysCard(report)
            annualStatsGrid(report.stats)
            chartCard(report)
            if !report.topSongs.isEmpty {
                songsCard(report.topSongs)
            }
            if !report.highlights.isEmpty {
                annualHighlightsCard(report.highlights)
            }
        }
    }

    private func daysCard(_ report: CareDTOs.AnnualReport) -> some View {
        LoveSoftCard {
            VStack(spacing: 6) {
                Text(verbatim: M6BL10n.value("m6b.reports.days.together \(report.daysTogether)"))
                    .font(.system(size: 30, weight: .bold, design: .rounded))
                    .foregroundStyle(LoveTheme.gradient)
                    .multilineTextAlignment(.center)
                if let since = report.coupleSince, !since.isEmpty {
                    Text(verbatim: M6BL10n.value("m6b.reports.since \(since)"))
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
            }
            .frame(maxWidth: .infinity)
        }
    }

    private func annualStatsGrid(_ stats: CareDTOs.AnnualStats) -> some View {
        let entries: [(key: String, value: Int)] = [
            ("m6b.reports.annual.articles", stats.articles),
            ("m6b.reports.annual.albums", stats.albums),
            ("m6b.reports.annual.photos", stats.photos),
            ("m6b.reports.annual.checkins", stats.checkins),
            ("m6b.reports.annual.messages", stats.messages),
            ("m6b.reports.annual.songs.played", stats.songsPlayed),
            ("m6b.reports.annual.songs.minutes", stats.songsMinutes),
            ("m6b.reports.annual.capsules", stats.capsulesCreated),
            ("m6b.reports.annual.wishes.completed", stats.wishesCompleted),
        ]
        let columns = Array(
            repeating: GridItem(.flexible(), spacing: 10), count: 3
        )
        return LoveSoftCard {
            LazyVGrid(columns: columns, spacing: 14) {
                ForEach(entries, id: \.key) { entry in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(verbatim: "\(entry.value)")
                            .font(.title3.weight(.bold))
                            .foregroundStyle(LoveTheme.primaryAccessible)
                        Text(M6BL10n.value(String.LocalizationValue(entry.key)))
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    /// Self-drawn 12-month bar chart with an articles/songs/checkins series
    /// switch (no third-party chart dependency).
    private func chartCard(_ report: CareDTOs.AnnualReport) -> some View {
        let months = report.monthly.sorted { $0.month < $1.month }
        let values = months.map { seriesValue($0) }
        let maxValue = max(1, values.max() ?? 1)
        return LoveSoftCard {
            VStack(alignment: .leading, spacing: 12) {
                Text(.init(m6b: "m6b.reports.chart.section"))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                Picker(.init(m6b: "m6b.reports.chart.section"), selection: $series) {
                    Text(.init(m6b: "m6b.reports.chart.articles")).tag(ChartSeries.articles)
                    Text(.init(m6b: "m6b.reports.chart.songs")).tag(ChartSeries.songs)
                    Text(.init(m6b: "m6b.reports.chart.checkins")).tag(ChartSeries.checkins)
                }
                .pickerStyle(.segmented)
                HStack(alignment: .bottom, spacing: 6) {
                    ForEach(months) { entry in
                        let value = seriesValue(entry)
                        VStack(spacing: 4) {
                            Text(verbatim: "\(value)")
                                .font(.system(size: 9))
                                .foregroundStyle(LoveTheme.secondaryText)
                            RoundedRectangle(cornerRadius: 4, style: .continuous)
                                .fill(LoveTheme.gradient)
                                .frame(
                                    height: max(
                                        3,
                                        110 * CGFloat(value) / CGFloat(maxValue)
                                    )
                                )
                            Text(verbatim: "\(entry.month)")
                                .font(.system(size: 9))
                                .foregroundStyle(LoveTheme.secondaryText)
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
                .frame(height: 160, alignment: .bottom)
            }
        }
    }

    private func seriesValue(_ entry: CareDTOs.AnnualMonth) -> Int {
        switch series {
        case .articles: entry.articles
        case .songs: entry.songs
        case .checkins: entry.checkins
        }
    }

    private func songsCard(_ songs: [CareDTOs.TopSong]) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 12) {
                Text(.init(m6b: "m6b.reports.songs.section"))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                ForEach(Array(songs.enumerated()), id: \.element.id) { index, song in
                    HStack(spacing: 10) {
                        Text(verbatim: "\(index + 1)")
                            .font(.subheadline.weight(.bold))
                            .foregroundStyle(
                                index < 3
                                    ? LoveTheme.primaryAccessible
                                    : LoveTheme.secondaryText
                            )
                            .frame(width: 20)
                        LoveAsyncImage(url: ServerSettings.mediaURL(song.coverUrl))
                            .frame(width: 44, height: 44)
                            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                        VStack(alignment: .leading, spacing: 2) {
                            Text(song.name)
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(LoveTheme.text)
                                .lineLimit(1)
                            Text(verbatim: (song.artists ?? []).joined(separator: " / "))
                                .font(.caption2)
                                .foregroundStyle(LoveTheme.secondaryText)
                                .lineLimit(1)
                        }
                        Spacer(minLength: 0)
                        LovePill(
                            text: M6BL10n.value("m6b.common.times \(song.playCount)"),
                            tint: LoveTheme.lavender
                        )
                    }
                }
            }
        }
    }

    private func annualHighlightsCard(_ highlights: [String]) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 8) {
                Text(.init(m6b: "m6b.reports.annual.highlights"))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                ForEach(highlights, id: \.self) { sentence in
                    Text(verbatim: "✨ \(sentence)")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.text)
                }
            }
        }
    }
}
