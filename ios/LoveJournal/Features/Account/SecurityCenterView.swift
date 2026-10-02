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

// MARK: - Wire bodies (extra=forbid — never send surplus fields)

private struct ChangePasswordBody: Encodable {
    var oldPassword: String
    var newPassword: String

    enum CodingKeys: String, CodingKey {
        case oldPassword = "old_password"
        case newPassword = "new_password"
    }
}

private struct ConfirmBody: Encodable {
    var confirm = true
}

private struct TotpCodeBody: Encodable {
    var code: String
}

private struct TotpDisableBody: Encodable {
    var code: String
    var password: String
}

// MARK: - View model

@MainActor
@Observable
final class SecurityViewModel {
    private(set) var loading = true
    private(set) var working = false
    var error: String?
    var message: String?

    private(set) var profiles: [CareDTOs.SecurityProfile] = []
    private(set) var devices: [CareDTOs.LoginDevice] = []
    private(set) var totp: CareDTOs.TotpStatus?

    let selfUid: String?

    private let api: LoveAPIClient

    init(api: LoveAPIClient, selfUid: String?) {
        self.api = api
        self.selfUid = selfUid
    }

    func refresh() async {
        do {
            async let users = api.request(
                CareDTOs.SecurityUserList.self, "GET", "/security/users"
            )
            async let totpStatus = api.request(
                CareDTOs.TotpStatus.self, "GET", "/auth/totp/status"
            )
            async let devicePage = api.request(
                [CareDTOs.LoginDevice].self, "GET", "/auth/devices"
            )
            let (userPage, status, deviceList) = try await (users, totpStatus, devicePage)
            profiles = userPage.items
            totp = status
            devices = deviceList
            error = nil
        } catch {
            self.error = M6AErrorText.describe(error)
        }
        loading = false
    }

    // MARK: Self operations (both bump session_version → 401 auto-logout)

    /// Change my password. On success the server bumps `session_version`, so
    /// the next request 401s and the app returns to the login screen — the
    /// sheet only needs to surface the "re-login required" hint.
    func changePassword(old: String, new: String) async -> String? {
        guard new.count >= 8, new.count <= 128,
              new.contains(where: \.isLetter), new.contains(where: \.isNumber)
        else {
            return String(localized: "m6a.security.password.policy", table: "M6A")
        }
        guard let selfUid else {
            return String(localized: "m6a.error.generic", table: "M6A")
        }
        working = true
        defer { working = false }
        do {
            _ = try await api.request(
                CareDTOs.SecurityProfile.self, "POST",
                "/security/users/\(selfUid)/change-password",
                body: ChangePasswordBody(oldPassword: old, newPassword: new)
            )
            message = String(localized: "m6a.security.relogin.hint", table: "M6A")
            return nil
        } catch {
            return M6AErrorText.describe(error)
        }
    }

    /// Revoke every session **except** the current device's (self only).
    func revokeOtherSessions() async {
        guard let selfUid else { return }
        working = true
        defer { working = false }
        do {
            _ = try await api.requestVoid(
                "POST", "/security/users/\(selfUid)/revoke-own-sessions", body: ConfirmBody()
            )
            message = String(localized: "m6a.security.sessions.revoked", table: "M6A")
        } catch {
            message = M6AErrorText.describe(error)
        }
    }

    /// Un-freeze a login-frozen account (either partner can unlock the other).
    func unlock(_ profile: CareDTOs.SecurityProfile) async {
        working = true
        defer { working = false }
        do {
            _ = try await api.requestVoid(
                "POST", "/security/users/\(profile.uid)/unlock", body: ConfirmBody()
            )
            message = String(localized: "m6a.security.unlocked", table: "M6A")
            await refresh()
        } catch {
            message = M6AErrorText.describe(error)
        }
    }

    // MARK: TOTP

    /// `POST /auth/totp/setup` — fresh secret + otpauth URI (inactive until
    /// enabled with a code). Already enabled → server 400.
    func beginTotpSetup() async -> CareDTOs.TotpSetup? {
        working = true
        defer { working = false }
        do {
            return try await api.request(
                CareDTOs.TotpSetup.self, "POST", "/auth/totp/setup"
            )
        } catch {
            message = M6AErrorText.describe(error)
            return nil
        }
    }

    /// `POST /auth/totp/enable` — returns the one-time recovery codes, or nil
    /// (with `message` set) on failure.
    func enableTotp(code: String) async -> [String]? {
        working = true
        defer { working = false }
        do {
            let enabled = try await api.request(
                CareDTOs.TotpEnabled.self, "POST", "/auth/totp/enable",
                body: TotpCodeBody(code: code)
            )
            return enabled.recoveryCodes
        } catch {
            message = M6AErrorText.describe(error)
            return nil
        }
    }

    /// `POST /auth/totp/disable` — takes a TOTP code *or* a recovery code.
    func disableTotp(code: String, password: String) async -> String? {
        working = true
        defer { working = false }
        do {
            _ = try await api.request(
                CareDTOs.TotpStatus.self, "POST", "/auth/totp/disable",
                body: TotpDisableBody(code: code, password: password)
            )
            await refresh()
            message = String(localized: "m6a.security.totp.disabled", table: "M6A")
            return nil
        } catch {
            return M6AErrorText.describe(error)
        }
    }

    // MARK: Devices

    func deleteDevice(_ device: CareDTOs.LoginDevice) async {
        working = true
        defer { working = false }
        do {
            _ = try await api.requestVoid("DELETE", "/auth/devices/\(device.did)")
            await refresh()
            message = String(localized: "m6a.security.device.removed", table: "M6A")
        } catch {
            message = M6AErrorText.describe(error)
        }
    }

    func deleteAllDevices() async {
        working = true
        defer { working = false }
        do {
            _ = try await api.requestVoid("DELETE", "/auth/devices")
            await refresh()
            message = String(localized: "m6a.security.relogin.hint", table: "M6A")
        } catch {
            message = M6AErrorText.describe(error)
        }
    }
}

// MARK: - View

struct SecurityCenterView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: SecurityViewModel?

    @State private var changePasswordPresented = false
    @State private var revokeConfirm = false
    @State private var totpSetupPresented = false
    @State private var totpDisablePresented = false
    @State private var deviceTarget: CareDTOs.LoginDevice?
    @State private var deviceAllConfirm = false

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m6a: "m6a.security.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                let uid: String?
                if case .loggedIn(let profile) = environment.session.state {
                    uid = profile.uid
                } else {
                    uid = nil
                }
                model = SecurityViewModel(api: environment.api, selfUid: uid)
                Task { await model?.refresh() }
            }
        }
        .refreshable { await model?.refresh() }
        .sheet(isPresented: $changePasswordPresented) {
            if let model {
                ChangePasswordSheet(model: model)
            }
        }
        .sheet(isPresented: $totpSetupPresented) {
            if let model {
                TotpSetupSheet(model: model)
            }
        }
        .sheet(isPresented: $totpDisablePresented) {
            if let model {
                TotpDisableSheet(model: model)
            }
        }
        .confirmationDialog(
            Text(String(localized: "m6a.security.revoke.confirm", table: "M6A")),
            isPresented: $revokeConfirm,
            titleVisibility: .visible
        ) {
            Button(String(localized: "m6a.security.revoke.action", table: "M6A"), role: .destructive) {
                Task { await model?.revokeOtherSessions() }
            }
            Button(String(localized: "common.cancel"), role: .cancel) {}
        } message: {
            Text(String(localized: "m6a.security.relogin.hint", table: "M6A"))
        }
        .confirmationDialog(
            Text(deviceTarget == nil
                ? ""
                : String(localized: "m6a.security.device.remove.confirm", table: "M6A")),
            isPresented: Binding(
                get: { deviceTarget != nil },
                set: { if !$0 { deviceTarget = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button(String(localized: "common.delete"), role: .destructive) {
                if let device = deviceTarget {
                    Task { await model?.deleteDevice(device) }
                }
                deviceTarget = nil
            }
            Button(String(localized: "common.cancel"), role: .cancel) {
                deviceTarget = nil
            }
        }
        .confirmationDialog(
            Text(String(localized: "m6a.security.device.removeall.confirm", table: "M6A")),
            isPresented: $deviceAllConfirm,
            titleVisibility: .visible
        ) {
            Button(String(localized: "m6a.security.device.removeall", table: "M6A"), role: .destructive) {
                Task { await model?.deleteAllDevices() }
            }
            Button(String(localized: "common.cancel"), role: .cancel) {}
        } message: {
            Text(String(localized: "m6a.security.relogin.hint", table: "M6A"))
        }
    }

    private func content(_ model: SecurityViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error, model.profiles.isEmpty {
                    LoveErrorView(message: error) {
                        Task { await model.refresh() }
                    }
                } else if model.loading {
                    LoveLoadingView()
                } else {
                    ForEach(model.profiles) { profile in
                        profileCard(model, profile)
                    }
                    selfActionsCard(model)
                    totpCard(model)
                    devicesCard(model)
                }
            }
            .padding(16)
        }
    }

    // MARK: Profile card

    private func profileCard(
        _ model: SecurityViewModel, _ profile: CareDTOs.SecurityProfile
    ) -> some View {
        LoveSoftCard {
            HStack(spacing: 8) {
                Text(profile.nickname)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(LoveTheme.text)
                LovePill(
                    text: String(
                        localized: profile.role == "PartnerA"
                            ? "m6a.security.role.a" : "m6a.security.role.b",
                        table: "M6A"
                    ),
                    tint: LoveTheme.lavender
                )
                if profile.uid == model.selfUid {
                    LovePill(
                        text: String(localized: "m6a.security.me", table: "M6A"),
                        tint: LoveTheme.primaryAccessible
                    )
                }
                Spacer()
                if let freezeUntil = profile.loginFreezeUntil, freezeUntil > Date() {
                    LovePill(
                        text: String(localized: "m6a.security.frozen.until \(Format.dateTime(freezeUntil))", table: "M6A"),
                        tint: LoveTheme.rose
                    )
                } else {
                    LovePill(
                        text: String(localized: "m6a.security.normal", table: "M6A"),
                        tint: LoveTheme.mint
                    )
                }
            }
            infoRow(
                labelKey: .init(m6a: "m6a.security.failed.count"),
                value: "\(profile.loginFailedCount)"
            )
            infoRow(
                labelKey: .init(m6a: "m6a.security.last.login"),
                value: profile.lastLoginAt.map {
                    (profile.lastLoginIp ?? "—") + " · " + Format.dateTime($0)
                } ?? "—"
            )
            if let changedAt = profile.passwordChangedAt {
                infoRow(
                    labelKey: .init(m6a: "m6a.security.password.changed"),
                    value: Format.dateTime(changedAt)
                )
            }
            infoRow(
                labelKey: .init(m6a: "m6a.security.session.version"),
                value: "\(profile.sessionVersion)"
            )
            if let freezeUntil = profile.loginFreezeUntil, freezeUntil > Date() {
                LoveSecondaryButton(
                    titleKey: .init(m6a: "m6a.security.unlock"),
                    loading: model.working
                ) {
                    Task { await model.unlock(profile) }
                }
            }
        }
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

    // MARK: Self actions

    private func selfActionsCard(_ model: SecurityViewModel) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.security.self.actions"))
            LoveSecondaryButton(titleKey: .init(m6a: "m6a.security.change.password")) {
                changePasswordPresented = true
            }
            LoveSecondaryButton(
                titleKey: .init(m6a: "m6a.security.revoke.sessions"),
                loading: model.working
            ) {
                revokeConfirm = true
            }
            Text(.init(m6a: "m6a.security.relogin.note"))
                .font(.caption)
                .foregroundStyle(LoveTheme.secondaryText)
        }
    }

    // MARK: TOTP

    private func totpCard(_ model: SecurityViewModel) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.security.totp.title"))
            if let totp = model.totp {
                HStack(spacing: 8) {
                    Image(systemName: totp.enabled ? "checkmark.shield.fill" : "shield")
                        .font(.footnote)
                        .foregroundStyle(totp.enabled ? LoveTheme.mint : LoveTheme.secondaryText)
                    Text(
                        totp.enabled
                            ? String(localized: "m6a.security.totp.on \(totp.recoveryCodesRemaining)", table: "M6A")
                            : String(localized: "m6a.security.totp.off", table: "M6A")
                    )
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.text)
                    Spacer()
                }
                if totp.enabled {
                    LoveSecondaryButton(titleKey: .init(m6a: "m6a.security.totp.disable")) {
                        totpDisablePresented = true
                    }
                } else {
                    LovePrimaryButton(titleKey: .init(m6a: "m6a.security.totp.enable")) {
                        totpSetupPresented = true
                    }
                }
            }
        }
    }

    // MARK: Devices

    private func devicesCard(_ model: SecurityViewModel) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.security.devices.title"))
            if model.devices.isEmpty {
                Text(.init(m6a: "m6a.security.devices.empty"))
                    .font(.footnote)
                    .foregroundStyle(LoveTheme.secondaryText)
            } else {
                ForEach(model.devices) { device in
                    HStack(alignment: .center, spacing: 8) {
                        Image(systemName: "iphone.gen3")
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.primaryAccessible)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(device.deviceName)
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(LoveTheme.text)
                                .lineLimit(1)
                            Text(
                                (device.ip ?? "—") + " · "
                                    + (device.lastLoginAt.map { Format.dateTime($0) } ?? "—")
                            )
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                        }
                        Spacer()
                        Button {
                            deviceTarget = device
                        } label: {
                            Image(systemName: "trash")
                                .font(.footnote)
                                .foregroundStyle(LoveTheme.rose)
                        }
                        .buttonStyle(.plain)
                    }
                    .padding(.vertical, 2)
                }
                LoveSecondaryButton(
                    titleKey: .init(m6a: "m6a.security.device.removeall"),
                    loading: model.working
                ) {
                    deviceAllConfirm = true
                }
                Text(.init(m6a: "m6a.security.relogin.note"))
                    .font(.caption)
                    .foregroundStyle(LoveTheme.secondaryText)
            }
        }
    }
}

// MARK: - Change password sheet

private struct ChangePasswordSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: SecurityViewModel

    @State private var oldPassword = ""
    @State private var newPassword = ""
    @State private var errorText: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    Text(.init(m6a: "m6a.security.relogin.note"))
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                    LoveField(labelKey: .init(m6a: "m6a.security.password.old")) {
                        SecureField(.init(m6a: "m6a.security.password.old"), text: $oldPassword)
                    }
                    LoveField(labelKey: .init(m6a: "m6a.security.password.new")) {
                        SecureField(.init(m6a: "m6a.security.password.new"), text: $newPassword)
                    }
                    Text(.init(m6a: "m6a.security.password.policy.hint"))
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                    if let errorText {
                        LoveErrorBanner(message: errorText)
                    }
                    LovePrimaryButton(
                        titleKey: .init(m6a: "m6a.security.change.password"),
                        loading: model.working
                    ) {
                        submit()
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(.init(m6a: "m6a.security.change.password"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(String(localized: "common.cancel")) { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }

    private func submit() {
        Task {
            if let failure = await model.changePassword(old: oldPassword, new: newPassword) {
                errorText = failure
            } else {
                dismiss()
            }
        }
    }
}

// MARK: - TOTP setup sheet

private struct TotpSetupSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: SecurityViewModel

    private enum Stage {
        case loading
        case pending(CareDTOs.TotpSetup)
        case recoveryCodes([String])
    }

    @State private var stage: Stage = .loading
    @State private var code = ""
    @State private var errorText: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    switch stage {
                    case .loading:
                        LoveLoadingView()
                            .frame(height: 120)
                    case .pending(let setup):
                        setupCard(setup)
                    case .recoveryCodes(let codes):
                        recoveryCard(codes)
                    }
                    if let errorText {
                        LoveErrorBanner(message: errorText)
                            .padding(.horizontal, 20)
                    }
                }
                .padding(.vertical, 20)
            }
            .loveScreenBackground()
            .navigationTitle(.init(m6a: "m6a.security.totp.enable"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(String(localized: "common.cancel")) { dismiss() }
                }
            }
        }
        .presentationDetents([.large])
        .task {
            if case .loading = stage {
                if let setup = await model.beginTotpSetup() {
                    stage = .pending(setup)
                } else {
                    errorText = model.message
                    dismiss()
                }
            }
        }
    }

    private func setupCard(_ setup: CareDTOs.TotpSetup) -> some View {
        LoveSoftCard {
            Text(.init(m6a: "m6a.security.totp.setup.intro"))
                .font(.footnote)
                .foregroundStyle(LoveTheme.secondaryText)
            M6ACopyRow(titleKey: .init(m6a: "m6a.security.totp.secret"), value: setup.secret)
            M6ACopyRow(titleKey: .init(m6a: "m6a.security.totp.uri"), value: setup.uri)
            LoveField(labelKey: .init(m6a: "m6a.security.totp.code")) {
                TextField("123456", text: $code)
                    .keyboardType(.numberPad)
            }
            LovePrimaryButton(
                titleKey: .init(m6a: "m6a.security.totp.confirm"),
                loading: model.working,
                enabled: code.count >= 6
            ) {
                submit()
            }
        }
        .padding(.horizontal, 20)
    }

    private func recoveryCard(_ codes: [String]) -> some View {
        LoveSoftCard {
            Label {
                Text(.init(m6a: "m6a.security.totp.codes.once"))
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(LoveTheme.rose)
            } icon: {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(LoveTheme.rose)
            }
            ForEach(codes, id: \.self) { recoveryCode in
                Text(recoveryCode)
                    .font(.footnote.weight(.medium).monospaced())
                    .foregroundStyle(LoveTheme.text)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 2)
            }
            M6ACopyRow(
                titleKey: .init(m6a: "m6a.security.totp.codes.copy"),
                value: codes.joined(separator: "\n")
            )
            LovePrimaryButton(titleKey: .init(m6a: "common.done")) {
                dismiss()
            }
        }
        .padding(.horizontal, 20)
    }

    private func submit() {
        Task {
            if let codes = await model.enableTotp(code: code) {
                stage = .recoveryCodes(codes)
                errorText = nil
            } else {
                errorText = model.message
            }
        }
    }
}

// MARK: - TOTP disable sheet

private struct TotpDisableSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: SecurityViewModel

    @State private var code = ""
    @State private var password = ""
    @State private var errorText: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    Text(.init(m6a: "m6a.security.totp.disable.intro"))
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                    LoveField(labelKey: .init(m6a: "m6a.security.totp.code.or.recovery")) {
                        SecureField(.init(m6a: "m6a.security.totp.code.or.recovery"), text: $code)
                    }
                    LoveField(labelKey: .init(m6a: "m6a.security.password.current")) {
                        SecureField(.init(m6a: "m6a.security.password.current"), text: $password)
                    }
                    if let errorText {
                        LoveErrorBanner(message: errorText)
                    }
                    LovePrimaryButton(
                        titleKey: .init(m6a: "m6a.security.totp.disable"),
                        loading: model.working,
                        enabled: code.count >= 6 && !password.isEmpty
                    ) {
                        submit()
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(.init(m6a: "m6a.security.totp.disable"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(String(localized: "common.cancel")) { dismiss() }
                }
            }
        }
        .presentationDetents([.medium])
    }

    private func submit() {
        Task {
            if let failure = await model.disableTotp(code: code, password: password) {
                errorText = failure
            } else {
                dismiss()
            }
        }
    }
}
