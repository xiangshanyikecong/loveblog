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

import CryptoKit
import Observation
import SwiftUI

import LoveCore

// MARK: - Wire bodies (vault setup/rekey — CareDTOs has no public inits)

/// `POST /cottage/vault/setup` and the setup half of `/rekey`: seven fields,
/// no `verifier_hash` (unlike chat) — the server only persists salt/verifier.
private struct VaultSetupBody: Encodable {
    var salt: String
    var kdf = "PBKDF2"
    var kdfHash = "SHA-256"
    var iterations: Int
    var algo = "AES-GCM"
    var verifierIv: String
    var verifierCipher: String

    enum CodingKeys: String, CodingKey {
        case salt, kdf, iterations, algo
        case kdfHash = "kdf_hash"
        case verifierIv = "verifier_iv"
        case verifierCipher = "verifier_cipher"
    }
}

/// `POST /cottage/vault/rekey` — setup fields plus every entry re-encrypted
/// under the new key (missing any vid → 400, so the full list is required).
private struct VaultRekeyBody: Encodable {
    var salt: String
    var kdf = "PBKDF2"
    var kdfHash = "SHA-256"
    var iterations: Int
    var algo = "AES-GCM"
    var verifierIv: String
    var verifierCipher: String
    var entries: [CareDTOs.VaultRekey.EntryBody]

    enum CodingKeys: String, CodingKey {
        case salt, kdf, iterations, algo, entries
        case kdfHash = "kdf_hash"
        case verifierIv = "verifier_iv"
        case verifierCipher = "verifier_cipher"
    }
}

/// Thrown by the background rekey pass when an entry no longer decrypts.
private enum VaultRekeyError: Error {
    case undecryptableEntry
}

// MARK: - View model

/// Client-side E2EE vault. The flow mirrors the chat key session exactly:
/// first setup derives a key from a passphrase with a fresh salt and
/// publishes a verifier the server cannot open; later visits re-derive from
/// the stored salt/iterations and validate locally before anything renders.
/// The key lives in memory only — cold starts re-unlock.
@MainActor
@Observable
final class VaultViewModel {
    enum Phase {
        case loading
        /// No verifier on the server yet: offer first-time setup.
        case setup
        /// Initialized but the local key session is closed.
        case locked
        /// Key derived and held in memory.
        case unlocked
    }

    struct Item: Identifiable {
        let entry: CareDTOs.VaultEntry
        var envelope: CareDTOs.VaultEnvelope?
        var id: String { entry.vid }
    }

    private(set) var phase: Phase = .loading
    private(set) var items: [Item] = []
    private(set) var keyWorking = false
    private(set) var saving = false
    var error: String?
    var toast: String?

    private let api: LoveAPIClient
    private var meta: CareDTOs.VaultMeta?
    private var key: SymmetricKey?
    /// vid → decrypted envelope JSON (memory only, keeps rekey lossless).
    private var plaintexts: [String: String] = [:]
    private var toastTask: Task<Void, Never>?

    init(api: LoveAPIClient) {
        self.api = api
    }

    // MARK: Lifecycle

    func start() async {
        do {
            let meta = try await api.request(
                CareDTOs.VaultMeta.self, "GET", "/cottage/vault/meta"
            )
            self.meta = meta
            error = nil
            if meta.initialized {
                phase = key == nil ? .locked : .unlocked
                if key != nil { await loadEntries() }
            } else {
                phase = .setup
            }
        } catch {
            self.error = M6AErrorText.describe(error)
        }
    }

    /// First-time setup: fresh salt, background derivation, verifier with the
    /// **vault** token, then the setup POST. Returns nil on success.
    func setup(passphrase: String) async -> String? {
        keyWorking = true
        defer { keyWorking = false }
        let salt = ChatCrypto.randomSaltBase64()
        do {
            let key = try await deriveInBackground(
                passphrase: passphrase, salt: salt, iterations: ChatCrypto.defaultIterations
            )
            let verifier = try ChatCrypto.makeVerifier(
                key: key, token: ChatCrypto.vaultVerifierToken
            )
            let body = VaultSetupBody(
                salt: salt,
                iterations: ChatCrypto.defaultIterations,
                verifierIv: verifier.ivBase64,
                verifierCipher: verifier.cipherBase64
            )
            let meta = try await api.request(
                CareDTOs.VaultMeta.self, "POST", "/cottage/vault/setup", body: body
            )
            self.meta = meta
            self.key = key
            phase = .unlocked
            showToast(String(localized: "m6a.vault.setup.done", table: "M6A"))
            await loadEntries()
            return nil
        } catch {
            return M6AErrorText.describe(error)
        }
    }

    /// Unlock: derive from the stored salt/iterations, validate against the
    /// server's verifier locally (wrong passphrase → friendly message, no
    /// request leaves the device). Returns nil on success.
    func unlock(passphrase: String) async -> String? {
        guard let meta, meta.initialized,
              let salt = meta.salt, let iterations = meta.iterations,
              let verifierIv = meta.verifierIv, let verifierCipher = meta.verifierCipher
        else {
            return String(localized: "m6a.vault.meta.missing", table: "M6A")
        }
        keyWorking = true
        defer { keyWorking = false }
        do {
            let key = try await deriveInBackground(
                passphrase: passphrase, salt: salt, iterations: iterations
            )
            guard ChatCrypto.verifierMatches(
                key: key,
                verifierIvBase64: verifierIv,
                verifierCipherBase64: verifierCipher,
                token: ChatCrypto.vaultVerifierToken
            ) else {
                return String(localized: "m6a.vault.wrong.passphrase", table: "M6A")
            }
            self.key = key
            phase = .unlocked
            await loadEntries()
            return nil
        } catch {
            return M6AErrorText.describe(error)
        }
    }

    /// Drop the in-memory key (titles fall back to 🔒 placeholders).
    func lock() {
        key = nil
        plaintexts.removeAll()
        if phase == .unlocked { phase = .locked }
        items = items.map { Item(entry: $0.entry, envelope: nil) }
    }

    /// PBKDF2 (~210k iterations) runs off the main thread.
    private func deriveInBackground(
        passphrase: String, salt: String, iterations: Int
    ) async throws -> SymmetricKey {
        try await Task.detached(priority: .userInitiated) {
            try ChatCrypto.deriveKey(passphrase: passphrase, saltBase64: salt, iterations: iterations)
        }.value
    }

    // MARK: Entries

    private func loadEntries() async {
        do {
            let entries = try await api.request(
                [CareDTOs.VaultEntry].self, "GET", "/cottage/vault/entries"
            )
            // Server already sorts by updated_at desc — keep the wire order.
            items = entries.map { Item(entry: $0, envelope: envelope(for: $0)) }
            error = nil
        } catch {
            self.error = M6AErrorText.describe(error)
        }
    }

    func refresh() async {
        await start()
        if phase == .unlocked { await loadEntries() }
    }

    /// Decrypts one entry's envelope JSON, caching the plaintext for rekey.
    private func envelope(for entry: CareDTOs.VaultEntry) -> CareDTOs.VaultEnvelope? {
        guard let key else { return nil }
        let json: String
        if let cached = plaintexts[entry.vid] {
            json = cached
        } else if let decrypted = try? ChatCrypto.decryptString(
            key: key, ivBase64: entry.iv, ciphertextBase64: entry.ciphertext
        ) {
            json = decrypted
            plaintexts[entry.vid] = decrypted
        } else {
            return nil
        }
        return try? JSONDecoder().decode(
            CareDTOs.VaultEnvelope.self, from: Data(json.utf8)
        )
    }

    /// Create or update an entry: the {title,body} envelope is JSON-encoded,
    /// encrypted with the in-memory key, and posted as {iv,ciphertext}.
    /// Returns nil on success, otherwise a user-facing message.
    func saveEntry(existing: Item?, title: String, body: String) async -> String? {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty else {
            return String(localized: "m6a.vault.title.required", table: "M6A")
        }
        guard let key else {
            return String(localized: "m6a.vault.locked.hint", table: "M6A")
        }
        saving = true
        defer { saving = false }
        do {
            let envelope = CareDTOs.VaultEnvelope(title: trimmedTitle, body: body)
            let jsonData = try LoveAPIClient.encoder.encode(envelope)
            guard let plaintext = String(data: jsonData, encoding: .utf8) else {
                return String(localized: "m6a.vault.entry.encode.failed", table: "M6A")
            }
            let sealed = try ChatCrypto.encryptString(key: key, plaintext: plaintext)
            let body = CareDTOs.VaultCipherBody(
                iv: sealed.ivBase64, ciphertext: sealed.ciphertextBase64
            )
            let entry: CareDTOs.VaultEntry
            if let existing {
                entry = try await api.request(
                    CareDTOs.VaultEntry.self, "PUT",
                    "/cottage/vault/entries/\(existing.entry.vid)", body: body
                )
            } else {
                entry = try await api.request(
                    CareDTOs.VaultEntry.self, "POST", "/cottage/vault/entries", body: body
                )
            }
            plaintexts[entry.vid] = plaintext
            let item = Item(entry: entry, envelope: envelope)
            if let existing, let index = items.firstIndex(where: { $0.id == existing.id }) {
                items[index] = item
            } else {
                items.insert(item, at: 0)
            }
            showToast(String(
                localized: existing == nil ? "m6a.vault.entry.created" : "m6a.vault.entry.saved",
                table: "M6A"
            ))
            return nil
        } catch {
            return M6AErrorText.describe(error)
        }
    }

    /// Soft-delete one entry server-side and drop it locally.
    func delete(_ item: Item) async {
        do {
            try await api.requestVoid("DELETE", "/cottage/vault/entries/\(item.entry.vid)")
            items.removeAll { $0.id == item.id }
            plaintexts[item.id] = nil
            showToast(String(localized: "m6a.vault.entry.deleted", table: "M6A"))
        } catch {
            showToast(M6AErrorText.describe(error))
        }
    }

    // MARK: Rekey & reset

    /// Change the passphrase: decrypt every entry with the current key, then
    /// re-encrypt under a key derived from the new passphrase and upload the
    /// full bundle (setup fields + every entry). Requires an unlocked key
    /// session. Returns nil on success.
    func rekey(newPassphrase: String) async -> String? {
        guard let oldKey = key else {
            return String(localized: "m6a.vault.locked.hint", table: "M6A")
        }
        keyWorking = true
        defer { keyWorking = false }
        let entries = items.map(\.entry)
        let newSalt = ChatCrypto.randomSaltBase64()
        let iterations = ChatCrypto.defaultIterations
        do {
            let bundle = try await Task.detached(priority: .userInitiated) {
                try Self.rekeyBundle(
                    oldKey: oldKey,
                    newPassphrase: newPassphrase,
                    newSalt: newSalt,
                    iterations: iterations,
                    entries: entries
                )
            }.value
            let body = VaultRekeyBody(
                salt: newSalt,
                iterations: iterations,
                verifierIv: bundle.verifierIv,
                verifierCipher: bundle.verifierCipher,
                entries: bundle.entries
            )
            let meta = try await api.request(
                CareDTOs.VaultMeta.self, "POST", "/cottage/vault/rekey", body: body
            )
            self.meta = meta
            key = bundle.newKey
            showToast(String(localized: "m6a.vault.rekey.done", table: "M6A"))
            return nil
        } catch is VaultRekeyError {
            return String(localized: "m6a.vault.rekey.decrypt.failed", table: "M6A")
        } catch {
            return M6AErrorText.describe(error)
        }
    }

    /// Pure crypto step for `rekey`: derive the new key + verifier and
    /// re-encrypt every entry. Runs on a background thread.
    nonisolated private static func rekeyBundle(
        oldKey: SymmetricKey,
        newPassphrase: String,
        newSalt: String,
        iterations: Int,
        entries: [CareDTOs.VaultEntry]
    ) throws -> (newKey: SymmetricKey, verifierIv: String, verifierCipher: String, entries: [CareDTOs.VaultRekey.EntryBody]) {
        let newKey = try ChatCrypto.deriveKey(
            passphrase: newPassphrase, saltBase64: newSalt, iterations: iterations
        )
        let verifier = try ChatCrypto.makeVerifier(
            key: newKey, token: ChatCrypto.vaultVerifierToken
        )
        var resealed: [CareDTOs.VaultRekey.EntryBody] = []
        resealed.reserveCapacity(entries.count)
        for entry in entries {
            guard let json = try? ChatCrypto.decryptString(
                key: oldKey, ivBase64: entry.iv, ciphertextBase64: entry.ciphertext
            ) else {
                throw VaultRekeyError.undecryptableEntry
            }
            let sealed = try ChatCrypto.encryptString(key: newKey, plaintext: json)
            resealed.append(
                CareDTOs.VaultRekey.EntryBody(
                    vid: entry.vid, iv: sealed.ivBase64, ciphertext: sealed.ciphertextBase64
                )
            )
        }
        return (newKey, verifier.ivBase64, verifier.cipherBase64, resealed)
    }

    /// Danger zone: hard-delete every entry and the verifier. Irreversible.
    func resetVault() async {
        keyWorking = true
        defer { keyWorking = false }
        do {
            try await api.requestVoid("POST", "/cottage/vault/reset")
            key = nil
            meta = nil
            plaintexts.removeAll()
            items = []
            phase = .setup
            showToast(String(localized: "m6a.vault.reset.done", table: "M6A"))
        } catch {
            showToast(M6AErrorText.describe(error))
        }
    }

    // MARK: Toast

    func showToast(_ text: String) {
        toast = text
        toastTask?.cancel()
        toastTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(3.5))
            guard !Task.isCancelled else { return }
            self?.toast = nil
        }
    }
}

// MARK: - View

struct VaultView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var model: VaultViewModel?

    @State private var keySheet: VaultKeySheet.Mode?
    @State private var editorPresented = false
    @State private var editingItem: VaultViewModel.Item?
    @State private var rekeyPresented = false
    @State private var resetConfirm = false
    @State private var deleteTarget: VaultViewModel.Item?
    @State private var expandedId: String?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoveLoadingView()
            }
        }
        .loveScreenBackground()
        .navigationTitle(.init(m6a: "m6a.vault.title"))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if model == nil {
                model = VaultViewModel(api: environment.api)
                Task { await model?.start() }
            }
        }
        .sheet(item: $keySheet) { mode in
            if let model {
                VaultKeySheet(mode: mode, model: model)
            }
        }
        .sheet(isPresented: $editorPresented) {
            if let model {
                VaultEntrySheet(model: model, editing: editingItem)
            }
        }
        .sheet(isPresented: $rekeyPresented) {
            if let model {
                VaultRekeySheet(model: model)
            }
        }
        .confirmationDialog(
            Text(String(localized: "m6a.vault.reset.confirm", table: "M6A")),
            isPresented: $resetConfirm,
            titleVisibility: .visible
        ) {
            Button(String(localized: "m6a.vault.reset.action", table: "M6A"), role: .destructive) {
                Task { await model?.resetVault() }
            }
            Button(String(localized: "common.cancel"), role: .cancel) {}
        } message: {
            Text(String(localized: "m6a.vault.reset.message", table: "M6A"))
        }
        .confirmationDialog(
            Text(deleteTarget == nil
                ? ""
                : String(localized: "m6a.vault.entry.delete.confirm", table: "M6A")),
            isPresented: Binding(
                get: { deleteTarget != nil },
                set: { if !$0 { deleteTarget = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button(String(localized: "common.delete"), role: .destructive) {
                if let target = deleteTarget {
                    Task { await model?.delete(target) }
                }
                deleteTarget = nil
            }
            Button(String(localized: "common.cancel"), role: .cancel) {
                deleteTarget = nil
            }
        }
    }

    @ViewBuilder
    private func content(_ model: VaultViewModel) -> some View {
        switch model.phase {
        case .loading:
            if let error = model.error {
                LoveErrorView(message: error) {
                    Task { await model.start() }
                }
            } else {
                LoveLoadingView()
            }
        case .setup:
            gate(
                model,
                systemImage: "lock.rectangle.stack",
                titleKey: .init(m6a: "m6a.vault.setup.title"),
                messageKey: .init(m6a: "m6a.vault.setup.intro"),
                buttonKey: .init(m6a: "m6a.vault.setup"),
                action: { keySheet = .setup }
            )
        case .locked:
            gate(
                model,
                systemImage: "lock.fill",
                titleKey: .init(m6a: "m6a.vault.locked.title"),
                messageKey: .init(m6a: "m6a.vault.locked.message"),
                buttonKey: .init(m6a: "m6a.vault.unlock"),
                action: { keySheet = .unlock }
            )
        case .unlocked:
            entryList(model)
        }
    }

    private func gate(
        _ model: VaultViewModel,
        systemImage: String,
        titleKey: LocalizedStringKey,
        messageKey: LocalizedStringKey,
        buttonKey: LocalizedStringKey,
        action: @escaping () -> Void
    ) -> some View {
        VStack(spacing: 16) {
            if let error = model.error {
                LoveErrorBanner(message: error)
            }
            LoveEmptyState(
                systemImage: systemImage,
                titleKey: titleKey,
                messageKey: messageKey
            )
            LovePrimaryButton(titleKey: buttonKey, loading: model.keyWorking, action: action)
                .padding(.horizontal, 40)
            if model.phase == .locked {
                Text(.init(m6a: "m6a.vault.blind.hint"))
                    .font(.caption)
                    .foregroundStyle(LoveTheme.secondaryText)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func entryList(_ model: VaultViewModel) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                if let toast = model.toast {
                    LoveSuccessBanner(message: toast)
                }
                if let error = model.error {
                    LoveErrorBanner(message: error)
                }
                if model.items.isEmpty {
                    LoveEmptyState(
                        systemImage: "lock.rectangle",
                        titleKey: .init(m6a: "m6a.vault.empty"),
                        messageKey: .init(m6a: "m6a.vault.empty.hint")
                    )
                } else {
                    ForEach(model.items) { item in
                        VaultEntryCard(
                            item: item,
                            isExpanded: expandedId == item.id,
                            onToggle: {
                                withAnimation(.easeOut(duration: 0.18)) {
                                    expandedId = expandedId == item.id ? nil : item.id
                                }
                            },
                            onEdit: {
                                editingItem = item
                                editorPresented = true
                            },
                            onDelete: { deleteTarget = item }
                        )
                    }
                }
            }
            .padding(16)
        }
        .refreshable { await model.refresh() }
        .overlay(alignment: .bottomTrailing) {
            Button {
                editingItem = nil
                editorPresented = true
            } label: {
                Label(.init(m6a: "m6a.vault.entry.add"), systemImage: "plus")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(LoveTheme.gradient, in: Capsule())
                    .shadow(color: LoveTheme.rose.opacity(0.35), radius: 8, y: 3)
            }
            .padding(20)
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    model.lock()
                    expandedId = nil
                } label: {
                    Image(systemName: "lock.open.fill")
                }
            }
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button {
                        rekeyPresented = true
                    } label: {
                        Label(.init(m6a: "m6a.vault.rekey"), systemImage: "key.horizontal")
                    }
                    Button(role: .destructive) {
                        resetConfirm = true
                    } label: {
                        Label(.init(m6a: "m6a.vault.reset"), systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
    }
}

// MARK: - Entry card

private struct VaultEntryCard: View {
    let item: VaultViewModel.Item
    let isExpanded: Bool
    let onToggle: () -> Void
    let onEdit: () -> Void
    let onDelete: () -> Void

    private var title: String {
        item.envelope?.title ?? String(localized: "m6a.vault.entry.undecryptable", table: "M6A")
    }

    var body: some View {
        LoveSoftCard {
            Button(action: onToggle) {
                HStack(alignment: .center, spacing: 8) {
                    Image(systemName: item.envelope == nil ? "lock.slash" : "lock.fill")
                        .font(.footnote)
                        .foregroundStyle(item.envelope == nil ? LoveTheme.rose : LoveTheme.lavender)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(title)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(LoveTheme.text)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Text(Format.dateTime(item.entry.updatedAt))
                            .font(.caption2)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    Spacer()
                    Image(systemName: "chevron.down")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(LoveTheme.secondaryText)
                        .rotationEffect(.degrees(isExpanded ? 180 : 0))
                }
            }
            .buttonStyle(.plain)
            if isExpanded {
                VStack(alignment: .leading, spacing: 10) {
                    Text(item.envelope?.body ?? String(localized: "m6a.vault.entry.undecryptable", table: "M6A"))
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.text)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(12)
                        .background(LoveTheme.background.opacity(0.6))
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    HStack(spacing: 12) {
                        Button {
                            onEdit()
                        } label: {
                            Label(.init(m6a: "common.edit"), systemImage: "pencil")
                                .font(.footnote.weight(.medium))
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(LoveTheme.primaryAccessible)
                        Spacer()
                        Button {
                            onDelete()
                        } label: {
                            Label(.init(m6a: "common.delete"), systemImage: "trash")
                                .font(.footnote.weight(.medium))
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(LoveTheme.rose)
                    }
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
    }
}

// MARK: - Setup / unlock sheet

private struct VaultKeySheet: View {
    enum Mode: Identifiable {
        case setup
        case unlock
        var id: Self { self }
    }

    let mode: Mode
    let model: VaultViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var passphrase = ""
    @State private var confirmation = ""
    @State private var errorText: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    if case .setup = mode {
                        Text(.init(m6a: "m6a.vault.setup.intro"))
                            .font(.footnote)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    LoveField(labelKey: .init(m6a: "m6a.vault.passphrase")) {
                        SecureField(.init(m6a: "m6a.vault.passphrase"), text: $passphrase)
                    }
                    if case .setup = mode {
                        LoveField(labelKey: .init(m6a: "m6a.vault.passphrase.confirm")) {
                            SecureField(.init(m6a: "m6a.vault.passphrase.confirm"), text: $confirmation)
                        }
                        Text(.init(m6a: "m6a.vault.passphrase.hint"))
                            .font(.caption)
                            .foregroundStyle(LoveTheme.secondaryText)
                    }
                    if let errorText {
                        LoveErrorBanner(message: errorText)
                    }
                    LovePrimaryButton(
                        titleKey: submitTitle,
                        loading: model.keyWorking,
                        action: { submit() }
                    )
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(sheetTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(String(localized: "common.cancel")) { dismiss() }
                }
            }
        }
        .presentationDetents([.medium])
    }

    private var sheetTitle: LocalizedStringKey {
        mode == .setup ? .init(m6a: "m6a.vault.setup.title") : .init(m6a: "m6a.vault.unlock")
    }

    private var submitTitle: LocalizedStringKey {
        mode == .setup ? .init(m6a: "m6a.vault.setup") : .init(m6a: "m6a.vault.unlock")
    }

    private func submit() {
        if case .setup = mode {
            guard passphrase.count >= 6 else {
                errorText = String(localized: "m6a.vault.passphrase.too.short", table: "M6A")
                return
            }
            guard passphrase == confirmation else {
                errorText = String(localized: "m6a.vault.passphrase.mismatch", table: "M6A")
                return
            }
        }
        Task {
            let result: String?
            if case .setup = mode {
                result = await model.setup(passphrase: passphrase)
            } else {
                result = await model.unlock(passphrase: passphrase)
            }
            if let result {
                errorText = result
            } else {
                dismiss()
            }
        }
    }
}

// MARK: - Entry editor sheet

private struct VaultEntrySheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: VaultViewModel
    let editing: VaultViewModel.Item?

    @State private var title = ""
    @State private var bodyText = ""
    @State private var errorText: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    LoveField(labelKey: .init(m6a: "m6a.vault.entry.title")) {
                        TextField(.init(m6a: "m6a.vault.entry.title"), text: $title)
                    }
                    VStack(alignment: .leading, spacing: 6) {
                        Text(.init(m6a: "m6a.vault.entry.body"))
                            .font(.footnote.weight(.medium))
                            .foregroundStyle(LoveTheme.secondaryText)
                        TextEditor(text: $bodyText)
                            .font(.body)
                            .frame(minHeight: 140)
                            .scrollContentBackground(.hidden)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 8)
                            .background(LoveTheme.background.opacity(0.6))
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                            .overlay {
                                RoundedRectangle(cornerRadius: 14, style: .continuous)
                                    .stroke(LoveTheme.outline, lineWidth: 1)
                            }
                    }
                    if let errorText {
                        LoveErrorBanner(message: errorText)
                    }
                    LovePrimaryButton(
                        titleKey: editing == nil ? .init(m6a: "m6a.vault.entry.create") : .init(m6a: "common.save"),
                        loading: model.saving
                    ) {
                        submit()
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(editing == nil ? .init(m6a: "m6a.vault.entry.new") : .init(m6a: "m6a.vault.entry.edit"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(String(localized: "common.cancel")) { dismiss() }
                }
            }
        }
        .presentationDetents([.large])
        .onAppear {
            if let editing, let envelope = editing.envelope {
                title = envelope.title
                bodyText = envelope.body
            }
        }
    }

    private func submit() {
        Task {
            if let failure = await model.saveEntry(
                existing: editing, title: title, body: bodyText
            ) {
                errorText = failure
            } else {
                dismiss()
            }
        }
    }
}

// MARK: - Rekey sheet

private struct VaultRekeySheet: View {
    @Environment(\.dismiss) private var dismiss
    let model: VaultViewModel

    @State private var passphrase = ""
    @State private var confirmation = ""
    @State private var errorText: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LoveSoftCard {
                    Text(.init(m6a: "m6a.vault.rekey.intro"))
                        .font(.footnote)
                        .foregroundStyle(LoveTheme.secondaryText)
                    LoveField(labelKey: .init(m6a: "m6a.vault.rekey.new.passphrase")) {
                        SecureField(.init(m6a: "m6a.vault.rekey.new.passphrase"), text: $passphrase)
                    }
                    LoveField(labelKey: .init(m6a: "m6a.vault.passphrase.confirm")) {
                        SecureField(.init(m6a: "m6a.vault.passphrase.confirm"), text: $confirmation)
                    }
                    Text(.init(m6a: "m6a.vault.passphrase.hint"))
                        .font(.caption)
                        .foregroundStyle(LoveTheme.secondaryText)
                    if let errorText {
                        LoveErrorBanner(message: errorText)
                    }
                    LovePrimaryButton(
                        titleKey: .init(m6a: "m6a.vault.rekey"),
                        loading: model.keyWorking
                    ) {
                        submit()
                    }
                }
                .padding(20)
            }
            .loveScreenBackground()
            .navigationTitle(.init(m6a: "m6a.vault.rekey"))
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
        guard passphrase.count >= 6 else {
            errorText = String(localized: "m6a.vault.passphrase.too.short", table: "M6A")
            return
        }
        guard passphrase == confirmation else {
            errorText = String(localized: "m6a.vault.passphrase.mismatch", table: "M6A")
            return
        }
        Task {
            if let failure = await model.rekey(newPassphrase: passphrase) {
                errorText = failure
            } else {
                dismiss()
            }
        }
    }
}
