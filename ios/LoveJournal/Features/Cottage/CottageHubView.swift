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

import SwiftUI

/// One module tile on the cottage hub grid (mirrors Android `CottageScreen`).
/// `route == nil` marks an upcoming module: rendered greyed-out with a
/// "coming soon" pill and without a navigation link.
private struct CottageFeature {
    let emoji: String
    let titleKey: LocalizedStringKey
    let subtitleKey: LocalizedStringKey
    let route: CottageRoute?
}

private let cottageFeatures: [CottageFeature] = [
    CottageFeature(emoji: "💬", titleKey: "cottage.feature.chat", subtitleKey: "cottage.feature.chat.sub", route: .chat),
    CottageFeature(emoji: "🌤️", titleKey: "cottage.feature.mood", subtitleKey: "cottage.feature.mood.sub", route: .mood),
    CottageFeature(emoji: "📍", titleKey: "cottage.feature.checkin", subtitleKey: "cottage.feature.checkin.sub", route: .checkin),
    CottageFeature(emoji: "💝", titleKey: "cottage.feature.wishes", subtitleKey: "cottage.feature.wishes.sub", route: .wishes),
    CottageFeature(emoji: "💌", titleKey: "cottage.feature.questions", subtitleKey: "cottage.feature.questions.sub", route: .questions),
    CottageFeature(emoji: "📺", titleKey: "cottage.feature.watch", subtitleKey: "cottage.feature.watch.sub", route: .watch),
    CottageFeature(emoji: "🎮", titleKey: "cottage.feature.games", subtitleKey: "cottage.feature.games.sub", route: .games),
    CottageFeature(emoji: "🎧", titleKey: "cottage.feature.listen", subtitleKey: "cottage.feature.listen.sub", route: .listen),
    CottageFeature(emoji: "🎟️", titleKey: "cottage.feature.coupons", subtitleKey: "cottage.feature.coupons.sub", route: .coupons),
    CottageFeature(emoji: "🔔", titleKey: "cottage.feature.reminders", subtitleKey: "cottage.feature.reminders.sub", route: .reminders),
    CottageFeature(emoji: "🗓️", titleKey: "cottage.feature.plans", subtitleKey: "cottage.feature.plans.sub", route: .plans),
    CottageFeature(emoji: "💰", titleKey: "cottage.feature.ledger", subtitleKey: "cottage.feature.ledger.sub", route: .ledger),
    CottageFeature(emoji: "📊", titleKey: "cottage.feature.reports", subtitleKey: "cottage.feature.reports.sub", route: .reports),
    CottageFeature(emoji: "🗺️", titleKey: "cottage.feature.footprints", subtitleKey: "cottage.feature.footprints.sub", route: .footprints),
    CottageFeature(emoji: "🌸", titleKey: "cottage.feature.period", subtitleKey: "cottage.feature.period.sub", route: .period),
    CottageFeature(emoji: "🔐", titleKey: "cottage.feature.vault", subtitleKey: "cottage.feature.vault.sub", route: .vault),
    CottageFeature(emoji: "💬", titleKey: "cottage.feature.messages", subtitleKey: "cottage.feature.messages.sub", route: .boardMessages),
]

/// Cottage tab root: a 2-column grid of the couple's interactive modules.
struct CottageHubView: View {
    private let columns = [
        GridItem(.flexible(), spacing: 12),
        GridItem(.flexible(), spacing: 12),
    ]

    var body: some View {
        ScrollView {
            LazyVGrid(columns: columns, spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("cottage.title")
                        .font(.title3.weight(.bold))
                        .foregroundStyle(LoveTheme.text)
                    Text("cottage.subtitle")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                .gridCellColumns(2)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.bottom, 4)

                ForEach(Array(cottageFeatures.enumerated()), id: \.offset) { _, feature in
                    featureCard(feature)
                }
            }
            .padding(16)
        }
        .loveScreenBackground()
        .navigationTitle("tab.cottage")
        .navigationBarTitleDisplayMode(.inline)
    }

    @ViewBuilder
    private func featureCard(_ feature: CottageFeature) -> some View {
        if let route = feature.route {
            NavigationLink(value: route) {
                cardBody(feature)
            }
            .buttonStyle(.plain)
        } else {
            cardBody(feature)
                .opacity(0.45)
                .disabled(true)
        }
    }

    private func cardBody(_ feature: CottageFeature) -> some View {
        LoveSoftCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .center) {
                    Text(feature.emoji)
                        .font(.title2)
                    Spacer()
                    if feature.route == nil {
                        LovePill(
                            text: String(localized: "cottage.coming.soon"),
                            tint: LoveTheme.secondaryText
                        )
                    } else {
                        Image(systemName: "chevron.right")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                }
                Text(feature.titleKey)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                Text(feature.subtitleKey)
                    .font(.caption)
                    .foregroundStyle(LoveTheme.secondaryText)
            }
        }
    }
}
