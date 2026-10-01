/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, version 3 of the License.
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

/// First-time initialization: creates Partner A plus the site settings in one
/// call, authorized by the server's `BOOTSTRAP_SETUP_TOKEN`.
struct BootstrapSheet: View {
    @Environment(\.dismiss) private var dismiss
    let viewModel: LoginViewModel

    @State private var token = ""
    @State private var username = ""
    @State private var password = ""
    @State private var nickname = ""
    @State private var siteName = ""
    @State private var dateEnabled = false
    @State private var startDate = Date()
    @State private var submitting = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    Text("bootstrap.note")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                    LoveField(labelKey: "bootstrap.token") {
                        SecureField("bootstrap.token.placeholder", text: $token)
                    }
                    LoveField(labelKey: "bootstrap.username") {
                        TextField("bootstrap.username", text: $username)
                            .textContentType(.username)
                    }
                    LoveField(labelKey: "bootstrap.password") {
                        SecureField("bootstrap.password", text: $password)
                            .textContentType(.newPassword)
                    }
                    LoveField(labelKey: "bootstrap.nickname") {
                        TextField("bootstrap.nickname", text: $nickname)
                            .textContentType(.name)
                    }
                    LoveField(labelKey: "bootstrap.site_name") {
                        TextField("bootstrap.site_name.placeholder", text: $siteName)
                    }
                    Toggle(isOn: $dateEnabled) {
                        Text("bootstrap.date.toggle")
                            .font(.subheadline)
                            .foregroundStyle(LoveTheme.text)
                    }
                    .tint(LoveTheme.primaryAccessible)
                    if dateEnabled {
                        DatePicker(
                            "bootstrap.date",
                            selection: $startDate,
                            displayedComponents: .date
                        )
                        .tint(LoveTheme.primaryAccessible)
                    }
                    if let error {
                        LoveErrorBanner(message: error)
                    }
                    LovePrimaryButton(
                        titleKey: "bootstrap.action.submit",
                        loading: submitting
                    ) {
                        Task {
                            submitting = true
                            defer { submitting = false }
                            if let failure = await viewModel.submitBootstrap(
                                token: token,
                                username: username,
                                password: password,
                                nickname: nickname,
                                siteName: siteName,
                                startDate: startDate,
                                dateEnabled: dateEnabled
                            ) {
                                self.error = failure
                            } else {
                                dismiss()
                            }
                        }
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle("bootstrap.title")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        dismiss()
                    } label: {
                        Text("common.cancel")
                    }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}
