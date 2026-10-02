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

/// `POST /cottage/questions` — not part of `CottageDTOs`.
private struct QuestionCreateBody: Encodable {
    var prompt: String
}

/// `POST /cottage/questions/{qid}/answer` (upsert).
private struct QuestionAnswerBody: Encodable {
    var content: String
}

@MainActor
@Observable
final class QuestionsViewModel {
    private(set) var loading = true
    private(set) var question: CottageDTOs.DailyQuestion?
    var message: String?
    var error: String?
    var saving = false

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        do {
            let today = try await api.request(
                CottageDTOs.TodayQuestion.self, "GET", "/cottage/questions/today"
            )
            question = today.item
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? String(localized: "cottage.error.generic")
        }
        loading = false
    }

    /// Returns true when the input should clear.
    func create(prompt: String) async -> Bool {
        let trimmed = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            message = String(localized: "cottage.questions.need.prompt")
            return false
        }
        saving = true
        defer { saving = false }
        do {
            _ = try await api.request(
                CottageDTOs.DailyQuestion.self, "POST", "/cottage/questions",
                body: QuestionCreateBody(prompt: trimmed)
            )
            message = String(localized: "cottage.questions.created")
            await refresh()
            return true
        } catch {
            message = (error as? APIError)?.message ?? String(localized: "cottage.questions.failed")
            return false
        }
    }

    /// Answer upsert — my answer can be edited until the reveal.
    func answer(content: String) async -> Bool {
        guard let qid = question?.qid else { return false }
        let trimmed = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            message = String(localized: "cottage.questions.need.answer")
            return false
        }
        saving = true
        defer { saving = false }
        do {
            _ = try await api.request(
                CottageDTOs.DailyQuestion.self, "POST", "/cottage/questions/\(qid)/answer",
                body: QuestionAnswerBody(content: trimmed)
            )
            message = String(localized: "cottage.questions.answered")
            await refresh()
            return true
        } catch {
            message = (error as? APIError)?.message ?? String(localized: "cottage.questions.failed")
            return false
        }
    }
}

struct CottageQuestionsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: QuestionsViewModel?
    @State private var promptDraft = ""
    @State private var answerDraft = ""
    @State private var editingAnswer = false

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("cottage.questions.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = QuestionsViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: QuestionsViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error, model.question == nil, !model.loading {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else if let question = model.question {
                    questionCard(question, model: model)
                } else {
                    createCard(model)
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
    }

    // MARK: State 1 — no question today yet

    private func createCard(_ model: QuestionsViewModel) -> some View {
        LoveSoftCard {
            LoveEmptyState(
                systemImage: "envelope.open",
                titleKey: "cottage.questions.none",
                messageKey: "cottage.questions.create.hint"
            )
            LoveField(labelKey: "cottage.questions.prompt") {
                TextField("cottage.questions.prompt.placeholder", text: $promptDraft, axis: .vertical)
                    .lineLimit(2...4)
            }
            LovePrimaryButton(titleKey: "cottage.questions.create", loading: model.saving) {
                let prompt = promptDraft
                Task {
                    if await model.create(prompt: prompt) {
                        promptDraft = ""
                    }
                }
            }
        }
    }

    // MARK: State 2 — today's question

    private func questionCard(
        _ question: CottageDTOs.DailyQuestion, model: QuestionsViewModel
    ) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    LovePill(text: question.questionDate, tint: LoveTheme.lavender)
                    if question.revealed {
                        LovePill(
                            text: String(localized: "cottage.questions.revealed"),
                            tint: LoveTheme.mint
                        )
                    }
                }
                Text(question.prompt)
                    .font(.headline)
                    .foregroundStyle(LoveTheme.text)
                Text("cottage.questions.by \(question.authorNickname)")
                    .font(.caption)
                    .foregroundStyle(LoveTheme.secondaryText)
            }

            Divider().overlay(LoveTheme.outline)

            answerCard(
                titleKey: "cottage.questions.mine",
                answer: question.myAnswer,
                isMine: true
            )

            Divider().overlay(LoveTheme.outline)

            answerCard(
                titleKey: "cottage.questions.partner",
                answer: question.answers.first { !$0.isSelf },
                isMine: false,
                revealed: question.revealed
            )

            if let mine = question.myAnswer {
                if mine.answered && !question.revealed {
                    if editingAnswer {
                        answerInput(model, prefill: mine.content ?? "")
                    } else {
                        LoveSecondaryButton(titleKey: "cottage.questions.edit.answer") {
                            editingAnswer = true
                            answerDraft = mine.content ?? ""
                        }
                    }
                }
            } else {
                answerInput(model, prefill: nil)
            }
        }
    }

    /// One side of the answer pair: mine is always visible; the partner's
    /// stays sealed until both have answered (revealed).
    @ViewBuilder
    private func answerCard(
        titleKey: LocalizedStringKey,
        answer: CottageDTOs.QuestionAnswer?,
        isMine: Bool,
        revealed: Bool = true
    ) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            LoveSectionTitle(textKey: titleKey)
            if isMine {
                if let answer, answer.answered, let content = answer.content {
                    Text(content)
                        .font(.subheadline)
                        .foregroundStyle(LoveTheme.text)
                } else {
                    Text("cottage.questions.mine.pending")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
            } else if let answer, answer.answered {
                if revealed, answer.contentVisible, let content = answer.content {
                    Text(content)
                        .font(.subheadline)
                        .foregroundStyle(LoveTheme.text)
                } else {
                    HStack(spacing: 6) {
                        Image(systemName: "lock.fill")
                            .font(.caption)
                        Text("cottage.questions.partner.hidden")
                    }
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
                }
            } else {
                Text("cottage.questions.partner.waiting")
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(LoveTheme.background.opacity(0.5))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private func answerInput(_ model: QuestionsViewModel, prefill: String?) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if prefill != nil {
                Text("cottage.questions.editing.hint")
                    .font(.caption)
                    .foregroundStyle(LoveTheme.primaryAccessible)
            }
            LoveField(labelKey: "cottage.questions.answer") {
                TextField("cottage.questions.answer.placeholder", text: $answerDraft, axis: .vertical)
                    .lineLimit(3...6)
            }
            HStack(spacing: 12) {
                if prefill != nil {
                    Button("common.cancel") {
                        editingAnswer = false
                        answerDraft = ""
                    }
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
                }
                LovePrimaryButton(
                    titleKey: "cottage.questions.submit",
                    loading: model.saving
                ) {
                    let content = answerDraft
                    Task {
                        if await model.answer(content: content) {
                            answerDraft = ""
                            editingAnswer = false
                        }
                    }
                }
            }
        }
    }
}
