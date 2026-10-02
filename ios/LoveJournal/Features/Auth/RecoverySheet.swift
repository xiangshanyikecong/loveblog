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

/// Password recovery, authorized by the instance bootstrap token (the only
/// unauthenticated reset path the server offers).
struct RecoverySheet: View {
    @Environment(\.dismiss) private var dismiss
    let viewModel: LoginViewModel

    @State private var username = ""
    @State private var newPassword = ""
    @State private var token = ""
    @State private var submitting = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    Text("recovery.note")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                    LoveField(labelKey: "login.username") {
                        TextField("login.username", text: $username)
                            .textContentType(.username)
                    }
                    LoveField(labelKey: "recovery.new_password") {
                        SecureField("recovery.new_password", text: $newPassword)
                            .textContentType(.newPassword)
                    }
                    LoveField(labelKey: "bootstrap.token") {
                        SecureField("bootstrap.token.placeholder", text: $token)
                    }
                    if let error {
                        LoveErrorBanner(message: error)
                    }
                    LovePrimaryButton(
                        titleKey: "recovery.action.submit",
                        loading: submitting
                    ) {
                        Task {
                            submitting = true
                            defer { submitting = false }
                            if let failure = await viewModel.submitRecovery(
                                username: username,
                                newPassword: newPassword,
                                token: token
                            ) {
                                self.error = failure
                            } else {
                                // Success: the view model closes the sheet;
                                // there is no in-sheet success state to keep.
                                self.error = nil
                                dismiss()
                            }
                        }
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle("recovery.title")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        dismiss()
                    } label: {
                        Text("common.done")
                    }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}
