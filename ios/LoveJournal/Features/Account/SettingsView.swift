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

// MARK: - Wire bodies (extra=forbid, partial update: nil fields are omitted)

/// `PUT /settings` — only the touched fields travel; `love_start_date` is a
/// preformatted ISO-8601 string (an empty string clears it server-side).
private struct SettingsPutBody: Encodable {
    var siteName: String?
    var loveStartDate: String?
    var allowRegistration: Bool?
    var partnerAAvatar: String?
    var partnerBAvatar: String?

    enum CodingKeys: String, CodingKey {
        case siteName = "site_name"
        case loveStartDate = "love_start_date"
        case allowRegistration = "allow_registration"
        case partnerAAvatar = "partner_a_avatar"
        case partnerBAvatar = "partner_b_avatar"
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeIfPresent(siteName, forKey: .siteName)
        try container.encodeIfPresent(loveStartDate, forKey: .loveStartDate)
        try container.encodeIfPresent(allowRegistration, forKey: .allowRegistration)
        try container.encodeIfPresent(partnerAAvatar, forKey: .partnerAAvatar)
        try container.encodeIfPresent(partnerBAvatar, forKey: .partnerBAvatar)
    }
}

/// `PUT /auth/partners/{uid}` — synthesized `encodeIfPresent` omits nils.
private struct PartnerUpdateBody: Encodable {
    var nickname: String?
}

// MARK: - View model

@MainActor
@Observable
final class SettingsViewModel {
    private(set) var loading = true
    private(set) var busy = false
    var error: String?
    var message: String?

    private(set) var settings: CareDTOs.SiteSettings?

    let profile: AuthDTOs.UserProfile?

    private let api: LoveAPIClient
    private static let isoFormatter = ISO8601DateFormatter()

    init(api: LoveAPIClient, profile: AuthDTOs.UserProfile?) {
        self.api = api
        self.profile = profile
    }

    /// My own avatar path from the site settings (role decides the slot).
    var myAvatarPath: String? {
        guard let settings else { return profile?.avatar }
        return profile?.role == "PartnerA" ? settings.partnerAAvatar : settings.partnerBAvatar
    }

    func refresh() async {
        do {
            settings = try await api.request(
                CareDTOs.SiteSettings.self, "GET", "/settings"
            )
            error = nil
        } catch {
            self.error = M6AErrorText.describe(error)
        }
        loading = false
    }

    private func put(_ body: SettingsPutBody, successKey: String) async {
        busy = true
        defer { busy = false }
        do {
            settings = try await api.request(
                CareDTOs.SiteSettings.self, "PUT", "/settings", body: body
            )
            message = String(localized: String.LocalizationValue(successKey), table: "M6A")
        } catch {
            self.error = M6AErrorText.describe(error)
        }
    }

    func saveSiteName(_ name: String) async {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            error = String(localized: "m6a.settings.site.name.required", table: "M6A")
            return
        }
        await put(SettingsPutBody(siteName: trimmed), successKey: "m6a.settings.saved")
    }

    func saveLoveStartDate(_ date: Date?) async {
        // Empty string clears the date server-side; a real date goes as ISO.
        let wire = date.map { Self.isoFormatter.string(from: $0) } ?? ""
        await put(SettingsPutBody(loveStartDate: wire), successKey: "m6a.settings.saved")
    }

    func setAllowRegistration(_ allowed: Bool) async {
        await put(
            SettingsPutBody(allowRegistration: allowed),
            successKey: "m6a.settings.saved"
        )
    }

    // MARK: Profile

    /// Compress → upload to `/uploads/avatars` → write my avatar slot.
    func uploadAvatar(data: Data) async {
        busy = true
        defer { busy = false }
        do {
            let uploaded = try await MediaUploadService.uploadImage(
                data, path: "/uploads/avatars", api: api
            )
            let body = SettingsPutBody(
                partnerAAvatar: profile?.role == "PartnerA" ? uploaded.url : nil,
                partnerBAvatar: profile?.role == "PartnerA" ? nil : uploaded.url
            )
            settings = try await api.request(
                CareDTOs.SiteSettings.self, "PUT", "/settings", body: body
            )
            message = String(localized: "m6a.settings.avatar.updated", table: "M6A")
        } catch {
            self.error = M6AErrorText.describe(error)
        }
    }

    /// Rename myself via `PUT /auth/partners/{uid}`.
    func saveNickname(_ nickname: String) async -> String? {
        let trimmed = nickname.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            return String(localized: "m6a.settings.nickname.required", table: "M6A")
        }
        guard let uid = profile?.uid else {
            return String(localized: "m6a.error.generic", table: "M6A")
        }
        busy = true
        defer { busy = false }
        do {
            _ = try await api.request(
                AuthDTOs.UserProfile.self, "PUT", "/auth/partners/\(uid)",
                body: PartnerUpdateBody(nickname: trimmed)
            )
            message = String(localized: "m6a.settings.saved", table: "M6A")
            return nil
        } catch {
            return M6AErrorText.describe(error)
        }
    }

    /// Invite the other half: `POST /auth/register` with role PartnerB.
    /// 409 (slot/username taken) surfaces the server detail verbatim.
    func invitePartner(username: String, password: String, nickname: String) async -> String? {
        let trimmedUser = username.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedNick = nickname.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmedUser.count >= 3 else {
            return String(localized: "m6a.settings.invite.username.rule", table: "M6A")
        }
        guard password.count >= 8,
              password.contains(where: \.isLetter), password.contains(where: \.isNumber)
        else {
            return String(localized: "m6a.settings.invite.password.rule", table: "M6A")
        }
        guard !trimmedNick.isEmpty else {
            return String(localized: "m6a.settings.nickname.required", table: "M6A")
        }
        busy = true
        defer { busy = false }
        do {
            _ = try await api.request(
                AuthDTOs.UserProfile.self, "POST", "/auth/register",
                body: AuthDTOs.RegisterRequest(
                    username: trimmedUser,
                    password: password,
                    nickname: trimmedNick,
                    role: "PartnerB"
                )
            )
            message = String(localized: "m6a.settings.invite.done", table: "M6A")
            return nil
        } catch {
            return M6AErrorText.describe(error)
        }
    }
}

// MARK: - View

struct SettingsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: SettingsViewModel?

    @State private var siteNameDraft = ""
    @State private var loveStartDate: Date = Date()
    @State private var hasLoveStartDate = false
    @State private var nicknameDraft = ""
    @State private var nicknameError: String?
    @State private var draftsLoaded = false

    @State private var inviteUsername = ""
    @State private var invitePassword = ""
    @State private var inviteNickname = ""
    @State private var inviteError: String?
    @State private var invitePresented = false

    private static let dateOnlyParser: DateFormatter = {
        let parser = DateFormatter()
        parser.dateFormat = "yyyy-MM-dd"
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.timeZone = TimeZone(identifier: "UTC")
        return parser
    }()

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m6a: "m6a.settings.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                let profile: AuthDTOs.UserProfile?
                if case .loggedIn(let current) = environment.session.state {
                    profile = current
                } else {
                    profile = nil
                }
                model = SettingsViewModel(api: environment.api, profile: profile)
                Task { await model?.refresh() }
            }
        }
        .sheet(isPresented: $invitePresented) {
            if let model {
                InvitePartnerSheet(model: model)
            }
        }
    }

    private func content(_ model: SettingsViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let message = model.message {
                    LoveSuccessBanner(message: message)
                }
                if let error = model.error {
                    LoveErrorBanner(message: error)
                }
                if model.loading {
                    LoveLoadingView()
                } else if let settings = model.settings {
                    siteCard(model, settings)
                    profileCard(model)
                    inviteCard(model)
                    entriesCard()
                    logoutCard()
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
        .onAppear { prepareDrafts(model) }
    }

    /// Seeds the editor drafts once settings arrive (only once — re-renders
    /// must never clobber what the user is typing).
    private func prepareDrafts(_ model: SettingsViewModel) {
        guard !draftsLoaded, let settings = model.settings else { return }
        draftsLoaded = true
        siteNameDraft = settings.siteName
        nicknameDraft = model.profile?.nickname ?? ""
        if let raw = settings.loveStartDate {
            hasLoveStartDate = true
            loveStartDate = Self.dateOnlyParser.date(from: String(raw.prefix(10)))
                ?? Self.parseISO(raw) ?? Date()
        } else {
            hasLoveStartDate = false
        }
    }

    private static func parseISO(_ raw: String) -> Date? {
        ISO8601DateFormatter().date(from: raw)
    }

    // MARK: Cards

    private func siteCard(_ model: SettingsViewModel, _ settings: CareDTOs.SiteSettings) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.settings.site"))
            LoveField(labelKey: .init(m6a: "m6a.settings.site.name")) {
                TextField(.init(m6a: "m6a.settings.site.name"), text: $siteNameDraft)
            }
            LoveSecondaryButton(
                titleKey: .init(m6a: "m6a.settings.site.name.save"),
                loading: model.busy
            ) {
                Task { await model.saveSiteName(siteNameDraft) }
            }
            Toggle(isOn: $hasLoveStartDate) {
                Text(.init(m6a: "m6a.settings.love.start.date"))
            }
            .tint(LoveTheme.primaryAccessible)
            .onChange(of: hasLoveStartDate) { _, enabled in
                if !enabled {
                    Task { await model.saveLoveStartDate(nil) }
                }
            }
            if hasLoveStartDate {
                DatePicker(
                    .init(m6a: "m6a.settings.love.start.date"),
                    selection: $loveStartDate,
                    displayedComponents: .date
                )
                .tint(LoveTheme.primaryAccessible)
                LoveSecondaryButton(
                    titleKey: .init(m6a: "m6a.settings.love.start.date.save"),
                    loading: model.busy
                ) {
                    Task { await model.saveLoveStartDate(loveStartDate) }
                }
            }
            Toggle(isOn: Binding(
                get: { settings.allowRegistration },
                set: { allowed in
                    Task { await model.setAllowRegistration(allowed) }
                }
            )) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(.init(m6a: "m6a.settings.allow.registration"))
                    Text(.init(m6a: "m6a.settings.allow.registration.hint"))
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
            }
            .tint(LoveTheme.primaryAccessible)
        }
    }

    private func profileCard(_ model: SettingsViewModel) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.settings.profile"))
            HStack(spacing: 14) {
                ZStack(alignment: .bottomTrailing) {
                    LoveAsyncImage(url: ServerSettings.mediaURL(model.myAvatarPath))
                        .frame(width: 68, height: 68)
                        .clipShape(Circle())
                        .overlay(Circle().stroke(LoveTheme.outline, lineWidth: 1))
                    if model.busy {
                        ProgressView()
                            .tint(LoveTheme.primaryAccessible)
                            .padding(4)
                            .background(LoveTheme.surface, in: Circle())
                    }
                }
                VStack(alignment: .leading, spacing: 4) {
                    LoveImagePicker { data in
                        Task { await model.uploadAvatar(data: data) }
                    }
                    .font(.footnote.weight(.medium))
                    Text(.init(m6a: "m6a.settings.avatar.hint"))
                        .font(.caption2)
                        .foregroundStyle(LoveTheme.secondaryText)
                }
                Spacer()
            }
            LoveField(labelKey: .init(m6a: "m6a.settings.nickname")) {
                TextField(.init(m6a: "m6a.settings.nickname"), text: $nicknameDraft)
            }
            if let nicknameError {
                LoveErrorBanner(message: nicknameError)
            }
            LoveSecondaryButton(
                titleKey: .init(m6a: "m6a.settings.nickname.save"),
                loading: model.busy
            ) {
                Task {
                    nicknameError = await model.saveNickname(nicknameDraft)
                }
            }
        }
    }

    private func inviteCard(_ model: SettingsViewModel) -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.settings.invite"))
            Text(.init(m6a: "m6a.settings.invite.hint"))
                .font(.caption)
                .foregroundStyle(LoveTheme.secondaryText)
            LoveSecondaryButton(titleKey: .init(m6a: "m6a.settings.invite.open")) {
                invitePresented = true
            }
        }
    }

    private func entriesCard() -> some View {
        LoveSoftCard {
            LoveSectionTitle(textKey: .init(m6a: "m6a.settings.entries"))
            NavigationLink(value: CottageRoute.security) {
                entryRow(
                    systemImage: "shield.lefthalf.filled",
                    titleKey: .init(m6a: "m6a.security.title")
                )
            }
            .buttonStyle(.plain)
            NavigationLink(value: CottageRoute.privacy) {
                entryRow(
                    systemImage: "hand.raised.fill",
                    titleKey: .init(m6a: "m6a.privacy.title")
                )
            }
            .buttonStyle(.plain)
            NavigationLink(value: CottageRoute.recycleBin) {
                entryRow(
                    systemImage: "trash.slash",
                    titleKey: .init(m6a: "m6a.recycle.title")
                )
            }
            .buttonStyle(.plain)
        }
    }

    private func entryRow(systemImage: String, titleKey: LocalizedStringKey) -> some View {
        HStack(spacing: 10) {
            Image(systemName: systemImage)
                .font(.subheadline)
                .foregroundStyle(LoveTheme.primaryAccessible)
                .frame(width: 24)
            Text(titleKey)
                .font(.subheadline)
                .foregroundStyle(LoveTheme.text)
            Spacer()
            Image(systemName: "chevron.right")
                .font(.caption.weight(.semibold))
                .foregroundStyle(LoveTheme.secondaryText)
        }
        .padding(.vertical, 6)
    }

    private func logoutCard() -> some View {
        Button(role: .destructive) {
            Task { await environment.session.logout() }
        } label: {
            Label(.init(m6a: "m6a.settings.logout"), systemImage: "rectangle.portrait.and.arrow.right")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(LoveTheme.rose)
                .frame(maxWidth: .infinity)
                .frame(height: 46)
                .overlay(Capsule().stroke(LoveTheme.rose.opacity(0.5), lineWidth: 1))
        }
        .buttonStyle(.plain)
        .padding(.top, 4)
    }
}

// MARK: - Invite sheet

private struct InvitePartnerSheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: SettingsViewModel

    @State private var username = ""
    @State private var password = ""
    @State private var nickname = ""
    @State private var errorText: String?
    @State private var succeeded = false

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    Text(.init(m6a: "m6a.settings.invite.form.hint"))
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                    LoveField(labelKey: .init(m6a: "m6a.settings.invite.username")) {
                        TextField(.init(m6a: "m6a.settings.invite.username"), text: $username)
                            .textInputAutocapitalization(.never)
                    }
                    LoveField(labelKey: .init(m6a: "m6a.settings.invite.password")) {
                        SecureField(.init(m6a: "m6a.settings.invite.password"), text: $password)
                    }
                    Text(.init(m6a: "m6a.settings.invite.password.rule"))
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                    LoveField(labelKey: .init(m6a: "m6a.settings.nickname")) {
                        TextField(.init(m6a: "m6a.settings.nickname"), text: $nickname)
                    }
                    if let errorText {
                        LoveErrorBanner(message: errorText)
                    }
                    if succeeded {
                        LoveSuccessBanner(message: String(localized: "m6a.settings.invite.done", table: "M6A"))
                    }
                    LovePrimaryButton(
                        titleKey: .init(m6a: "m6a.settings.invite.submit"),
                        loading: model.busy
                    ) {
                        submit()
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(.init(m6a: "m6a.settings.invite"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(String(localized: "common.done")) { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }

    private func submit() {
        Task {
            if let failure = await model.invitePartner(
                username: username, password: password, nickname: nickname
            ) {
                errorText = failure
                succeeded = false
            } else {
                errorText = nil
                succeeded = true
                username = ""
                password = ""
                nickname = ""
            }
        }
    }
}
