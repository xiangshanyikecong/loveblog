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
final class NotificationsViewModel {
    var loading = true
    var error: String?
    var items: [ContentDTOs.AppNotification] = []
    var unreadCount = 0

    private let api: LoveAPIClient

    init(api: LoveAPIClient) {
        self.api = api
    }

    func refresh() async {
        if items.isEmpty { loading = true }
        do {
            let list = try await api.request(
                ContentDTOs.NotificationList.self,
                "GET",
                "/notifications",
                query: [URLQueryItem(name: "limit", value: "50")]
            )
            items = list.items
            unreadCount = list.unreadCount
            error = nil
        } catch {
            self.error = (error as? APIError)?.message ?? "加载失败，请稍后重试"
        }
        loading = false
    }

    func markRead(_ notification: ContentDTOs.AppNotification) async {
        guard !notification.isRead else { return }
        do {
            let updated = try await api.request(
                ContentDTOs.AppNotification.self,
                "POST",
                "/notifications/\(notification.nid)/read"
            )
            if let index = items.firstIndex(where: { $0.nid == updated.nid }) {
                items[index] = updated
            }
            unreadCount = max(0, unreadCount - 1)
        } catch {
            // Read-state sync is best effort; the list refreshes anyway.
        }
    }

    func markAllRead() async {
        do {
            _ = try await api.request(ReadAllResult.self, "POST", "/notifications/read-all")
            await refresh()
        } catch {
            self.error = (error as? APIError)?.message ?? "操作失败，请稍后重试"
        }
    }

    private struct ReadAllResult: Decodable {
        var updated: Int
    }
}

struct NotificationsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: NotificationsViewModel?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle("notifications.title")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = NotificationsViewModel(api: environment.api)
                Task { await model?.refresh() }
            }
        }
    }

    private func content(_ model: NotificationsViewModel) -> some View {
        ScrollView {
            VStack(spacing: 10) {
                if let error = model.error, model.items.isEmpty {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else if model.items.isEmpty {
                    LoveEmptyState(
                        systemImage: "bell.slash",
                        titleKey: "notifications.empty",
                        messageKey: "notifications.empty.hint"
                    )
                } else {
                    HStack {
                        Text("notifications.unread \(model.unreadCount)")
                            .font(.caption.weight(.medium))
                            .foregroundStyle(model.unreadCount > 0 ? LoveTheme.primaryAccessible : LoveTheme.secondaryText)
                        Spacer()
                        if model.unreadCount > 0 {
                            Button("notifications.read_all") {
                                Task { await model.markAllRead() }
                            }
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(LoveTheme.primaryAccessible)
                        }
                    }
                    .padding(.horizontal, 4)
                    ForEach(model.items) { notification in
                        notificationCard(notification) {
                            Task { await model.markRead(notification) }
                        }
                    }
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
    }

    private func notificationCard(
        _ notification: ContentDTOs.AppNotification,
        onTap: @escaping () -> Void
    ) -> some View {
        Button(action: onTap) {
            HStack(alignment: .top, spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(notification.title)
                        .font(.subheadline.weight(notification.isRead ? .regular : .semibold))
                        .foregroundStyle(LoveTheme.text)
                        .multilineTextAlignment(.leading)
                    if let body = notification.body, !body.isEmpty {
                        Text(body)
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                    }
                    Text(Format.dateTime(notification.createdAt))
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText.opacity(0.8))
                }
                Spacer()
                if !notification.isRead {
                    Circle()
                        .fill(LoveTheme.rose)
                        .frame(width: 8, height: 8)
                }
            }
            .padding(14)
            .background(
                notification.isRead
                    ? LoveTheme.surface
                    : LoveTheme.primaryAccessible.opacity(0.1),
                in: RoundedRectangle(cornerRadius: 16, style: .continuous)
            )
            .shadow(color: .black.opacity(0.04), radius: 6, y: 2)
        }
        .buttonStyle(.plain)
    }
}
