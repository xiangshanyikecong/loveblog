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

/// Sign-in screen with the self-hosted server address field, health probe,
/// TOTP second factor, first-time bootstrap entry and password recovery.
struct LoginView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var viewModel: LoginViewModel?

    var body: some View {
        Group {
            if let viewModel {
                loginContent(viewModel)
            } else {
                Color.clear.loveScreenBackground()
            }
        }
        .onAppear {
            if viewModel == nil {
                viewModel = LoginViewModel(api: environment.api, session: environment.session)
            }
        }
    }

    private func loginContent(_ viewModel: LoginViewModel) -> some View {
        ScrollView {
            VStack(spacing: 20) {
                header
                serverCard(viewModel)
                loginCard(viewModel)
                if viewModel.showBootstrapEntry {
                    Button {
                        viewModel.showBootstrapSheet = true
                    } label: {
                        Label("login.bootstrap.entry", systemImage: "sparkles")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.primaryAccessible)
                    }
                }
                Button {
                    viewModel.showRecoverySheet = true
                } label: {
                    Text("login.recovery.entry")
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                versionFooter
            }
            .padding(20)
        }
        .scrollDismissesKeyboard(.interactively)
        .loveScreenBackground()
        .sheet(isPresented: Binding(
            get: { viewModel.showBootstrapSheet },
            set: { viewModel.showBootstrapSheet = $0 }
        )) {
            BootstrapSheet(viewModel: viewModel)
        }
        .sheet(isPresented: Binding(
            get: { viewModel.showRecoverySheet },
            set: { viewModel.showRecoverySheet = $0 }
        )) {
            RecoverySheet(viewModel: viewModel)
        }
        .onChange(of: viewModel.serverAddress) { _, _ in
            Task { await viewModel.checkBootstrapStatus() }
        }
        .task {
            await viewModel.checkBootstrapStatus()
        }
    }

    private var header: some View {
        VStack(spacing: 8) {
            Image(systemName: "heart.fill")
                .font(.system(size: 40, weight: .semibold))
                .foregroundStyle(LoveTheme.gradient)
            Text("app.name")
                .font(.largeTitle.bold())
                .foregroundStyle(LoveTheme.text)
            Text("app.tagline")
                .font(.footnote)
                .foregroundStyle(LoveTheme.secondaryText)
        }
        .padding(.top, 12)
        .padding(.bottom, 4)
    }

    private func serverCard(_ viewModel: LoginViewModel) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: "login.section.server")
            LoveField(labelKey: "login.server.address") {
                TextField("login.server.placeholder", text: Binding(
                    get: { viewModel.serverAddress },
                    set: { viewModel.serverAddress = $0 }
                ))
                .keyboardType(.URL)
            }
            Text(viewModel.isDebugBuild ? "login.server.hint.debug" : "login.server.hint.release")
                .font(.caption2)
                .foregroundStyle(LoveTheme.secondaryText)
            LoveSecondaryButton(
                titleKey: "login.action.test_connection",
                loading: viewModel.testingConnection
            ) {
                Task { await viewModel.testConnection() }
            }
            if let ok = viewModel.connectionOk {
                LoveSuccessBanner(message: ok)
            }
        }
    }

    private func loginCard(_ viewModel: LoginViewModel) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: "login.section.account")
            LoveField(labelKey: "login.username") {
                TextField("login.username", text: Binding(
                    get: { viewModel.username },
                    set: { viewModel.username = $0 }
                ))
                .textContentType(.username)
            }
            LoveField(labelKey: "login.password") {
                SecureField("login.password", text: Binding(
                    get: { viewModel.password },
                    set: { viewModel.password = $0 }
                ))
                .textContentType(.password)
            }
            if viewModel.showTOTPField {
                LoveField(labelKey: "login.totp") {
                    TextField("login.totp.placeholder", text: Binding(
                        get: { viewModel.totpCode },
                        set: { viewModel.totpCode = $0 }
                    ))
                    .textContentType(.oneTimeCode)
                }
            }
            if let error = viewModel.error {
                LoveErrorBanner(message: error)
            }
            LovePrimaryButton(titleKey: "login.action.sign_in", loading: viewModel.loading) {
                Task { await viewModel.login() }
            }
        }
    }

    private var versionFooter: some View {
        Text("common.version \(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "-")")
            .font(.caption2)
            .foregroundStyle(LoveTheme.secondaryText.opacity(0.7))
            .padding(.top, 8)
    }
}
