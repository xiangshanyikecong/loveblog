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

/// `GET /cottage/mood/calendar` — not part of `CottageDTOs`.
private struct MoodCalendarResponse: Decodable {
    var year: Int
    var month: Int
    var items: [CottageDTOs.Mood]
}

@MainActor
@Observable
final class MoodViewModel {
    private(set) var loading = true
    private(set) var today: CottageDTOs.TodayMoods?
    private(set) var calendarItems: [CottageDTOs.Mood] = []
    var message: String?
    var error: String?
    var saving = false

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        do {
            async let todayResponse = api.request(
                CottageDTOs.TodayMoods.self, "GET", "/cottage/mood/today"
            )
            let now = Calendar.current.dateComponents([.year, .month], from: Date())
            async let calendarResponse = api.request(
                MoodCalendarResponse.self, "GET", "/cottage/mood/calendar",
                query: [
                    URLQueryItem(name: "year", value: String(now.year ?? 0)),
                    URLQueryItem(name: "month", value: String(now.month ?? 0)),
                ]
            )
            let (today, calendar) = try await (todayResponse, calendarResponse)
            self.today = today
            calendarItems = calendar.items.sorted { $0.moodDate > $1.moodDate }
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? String(localized: "cottage.error.generic")
        }
        loading = false
    }

    /// Upsert today's mood; the local calendar date is sent so the entry lands
    /// on the couple's day, not the server's UTC day.
    func checkIn(mood: String, emoji: String, note: String) async {
        saving = true
        defer { saving = false }
        let trimmed = note.trimmingCharacters(in: .whitespacesAndNewlines)
        let body = CottageDTOs.MoodCreate(
            mood: mood,
            emoji: emoji,
            note: trimmed.isEmpty ? nil : trimmed,
            moodDate: Format.todayString()
        )
        do {
            _ = try await api.request(
                CottageDTOs.Mood.self, "POST", "/cottage/mood",
                body: body, headers: ["Idempotency-Key": UUID().uuidString]
            )
            message = String(localized: "cottage.mood.recorded")
            await refresh()
        } catch {
            message = (error as? APIError)?.message ?? String(localized: "cottage.mood.failed")
        }
    }
}

/// Preset mood chips; `mood` values match the Android client (shared display
/// vocabulary across platforms), labels are localized for the UI only.
private let moodOptions: [(mood: String, emoji: String, labelKey: LocalizedStringKey)] = [
    ("开心", "😄", "cottage.mood.option.happy"),
    ("幸福", "🥰", "cottage.mood.option.blissful"),
    ("平静", "😌", "cottage.mood.option.calm"),
    ("想你", "🥺", "cottage.mood.option.missyou"),
    ("难过", "😢", "cottage.mood.option.sad"),
    ("生气", "😠", "cottage.mood.option.angry"),
]

struct CottageMoodView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: MoodViewModel?
    @State private var selectedMood = 0
    @State private var note = ""

    private let chipColumns = [
        GridItem(.adaptive(minimum: 104), spacing: 8)
    ]

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("cottage.mood.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = MoodViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: MoodViewModel) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error, model.today == nil {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else {
                    checkInCard(model)
                    todayCard(model)
                    calendarCard(model)
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
    }

    // MARK: Check-in

    private func checkInCard(_ model: MoodViewModel) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: "cottage.mood.today")
            LazyVGrid(columns: chipColumns, spacing: 8) {
                ForEach(Array(moodOptions.enumerated()), id: \.offset) { index, option in
                    Button {
                        selectedMood = index
                    } label: {
                        Text("\(option.emoji) \(option.labelKey)")
                            .font(.footnote.weight(selectedMood == index ? .semibold : .regular))
                            .foregroundStyle(
                                selectedMood == index ? LoveTheme.primaryAccessible : LoveTheme.secondaryText
                            )
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                            .background(
                                selectedMood == index
                                    ? LoveTheme.primaryAccessible.opacity(0.12)
                                    : LoveTheme.background.opacity(0.6),
                                in: Capsule()
                            )
                            .overlay {
                                Capsule().stroke(
                                    selectedMood == index
                                        ? LoveTheme.primaryAccessible.opacity(0.5)
                                        : LoveTheme.outline,
                                    lineWidth: 1
                                )
                            }
                    }
                    .buttonStyle(.plain)
                }
            }
            LoveField(labelKey: "cottage.mood.note") {
                TextField("cottage.mood.note.placeholder", text: $note, axis: .vertical)
                    .lineLimit(2...4)
            }
            LovePrimaryButton(titleKey: "cottage.mood.checkin", loading: model.saving) {
                let option = moodOptions[selectedMood]
                let text = note
                Task { await model.checkIn(mood: option.mood, emoji: option.emoji, note: text) }
            }
        }
    }

    // MARK: Today's two cards

    @ViewBuilder
    private func todayCard(_ model: MoodViewModel) -> some View {
        if let today = model.today {
            LoveSoftCard {
                LoveSectionTitle(textKey: "cottage.mood.today.cards")
                moodRow(
                    mood: today.mine,
                    emptyKey: "cottage.mood.mine.empty",
                    alignment: .leading
                )
                Divider().overlay(LoveTheme.outline)
                moodRow(
                    mood: today.partner,
                    emptyKey: "cottage.mood.partner.empty",
                    alignment: .trailing
                )
            }
        }
    }

    @ViewBuilder
    private func moodRow(
        mood: CottageDTOs.Mood?, emptyKey: LocalizedStringKey, alignment: HorizontalAlignment
    ) -> some View {
        if let mood {
            VStack(alignment: alignment, spacing: 4) {
                HStack(spacing: 6) {
                    Text(mood.emoji ?? "💬")
                        .font(.title3)
                    Text(mood.mood)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(LoveTheme.text)
                    LovePill(
                        text: mood.isSelf
                            ? String(localized: "cottage.mood.mine")
                            : mood.authorNickname,
                        tint: LoveTheme.lavender
                    )
                }
                if let note = mood.note, !note.isEmpty {
                    Text(note)
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                        .multilineTextAlignment(alignment == .leading ? .leading : .trailing)
                }
                Text(Format.dateTime(mood.updatedAt))
                    .font(.caption2)
                    .foregroundStyle(LoveTheme.secondaryText)
            }
            .frame(maxWidth: .infinity, alignment: alignment == .leading ? .leading : .trailing)
        } else {
            Text(emptyKey)
                .font(.footnote)
                .foregroundStyle(LoveTheme.secondaryText)
                .frame(maxWidth: .infinity, alignment: alignment == .leading ? .leading : .trailing)
        }
    }

    // MARK: Month calendar

    private func calendarCard(_ model: MoodViewModel) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: "cottage.mood.calendar")
            if model.calendarItems.isEmpty {
                LoveEmptyState(
                    systemImage: "calendar.badge.clock",
                    titleKey: "cottage.mood.calendar.empty",
                    messageKey: "cottage.mood.calendar.empty.hint"
                )
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(model.calendarItems.enumerated()), id: \.element.id) { index, mood in
                        if index > 0 {
                            Divider().overlay(LoveTheme.outline)
                        }
                        HStack(spacing: 10) {
                            Text(mood.emoji ?? "💬")
                                .font(.title3)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("\(mood.mood) · \(mood.authorNickname)")
                                    .font(.footnote.weight(.medium))
                                    .foregroundStyle(LoveTheme.text)
                                if let note = mood.note, !note.isEmpty {
                                    Text(note)
                                        .font(.caption)
                                        .foregroundStyle(LoveTheme.secondaryText)
                                        .lineLimit(1)
                                }
                            }
                            Spacer()
                            Text(mood.moodDate)
                                .font(.caption)
                                .foregroundStyle(LoveTheme.secondaryText)
                        }
                        .padding(.vertical, 8)
                    }
                }
            }
        }
    }
}
