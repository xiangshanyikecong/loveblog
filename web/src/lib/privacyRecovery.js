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

import { t } from "../locales";

const KIT_FORMAT = "love-journal-recovery-kit";
const KIT_VERSION = 1;
const RECOVERY_KEY_BYTES = 32;
const RECOVERY_CODE_CHARS = 43;
const RECOVERY_CODE_GROUP_SIZE = 5;
const MAX_KIT_BYTES = 32 * 1024;

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function bytesToBase64Url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlToBytes(value) {
  const normalized = String(value || "").replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const binary = atob(padded);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function base64ToBytes(value) {
  const binary = atob(String(value || ""));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function bytesToBase64(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function randomBytes(length) {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return bytes;
}

function normalizeRecoveryCode(value) {
  const compact = String(value || "").replace(/\s/g, "");
  if (compact.length === RECOVERY_CODE_CHARS) return compact;

  const separators = Math.floor((RECOVERY_CODE_CHARS - 1) / RECOVERY_CODE_GROUP_SIZE);
  if (compact.length !== RECOVERY_CODE_CHARS + separators) return compact;
  let normalized = "";
  let sourceIndex = 0;
  for (let index = 0; index < RECOVERY_CODE_CHARS; index += 1) {
    if (index > 0 && index % RECOVERY_CODE_GROUP_SIZE === 0) {
      if (compact[sourceIndex] !== "-") return compact;
      sourceIndex += 1;
    }
    normalized += compact[sourceIndex];
    sourceIndex += 1;
  }
  return normalized;
}

function displayRecoveryCode(value) {
  return String(value || "").match(/.{1,5}/g)?.join("-") || "";
}

async function importRecoveryKey(code) {
  const normalized = normalizeRecoveryCode(code);
  if (!new RegExp(`^[A-Za-z0-9_-]{${RECOVERY_CODE_CHARS}}$`).test(normalized)) {
    throw new Error(t("privacyRecovery.codeInvalid"));
  }
  const raw = base64UrlToBytes(normalized);
  if (raw.byteLength !== RECOVERY_KEY_BYTES) throw new Error(t("privacyRecovery.codeInvalid"));
  return crypto.subtle.importKey("raw", raw, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}

export async function encryptionMetaFingerprint(scope, meta) {
  const canonical = JSON.stringify({
    scope,
    salt: meta?.salt || "",
    kdf: meta?.kdf || "",
    kdf_hash: meta?.kdf_hash || "",
    iterations: Number(meta?.iterations || 0),
    algo: meta?.algo || "",
    verifier_iv: meta?.verifier_iv || "",
    verifier_cipher: meta?.verifier_cipher || "",
  });
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(canonical));
  return bytesToBase64Url(new Uint8Array(digest));
}

export async function createRecoveryKit({ scope, passphrase, fingerprint }) {
  if (!['chat', 'vault'].includes(scope)) throw new Error(t("privacyRecovery.unsupportedScope"));
  if (!passphrase) throw new Error(t("privacyRecovery.passphraseRequired"));
  if (!fingerprint) throw new Error(t("privacyRecovery.fingerprintMissing"));

  const rawRecoveryKey = randomBytes(RECOVERY_KEY_BYTES);
  const recoveryCode = bytesToBase64Url(rawRecoveryKey);
  const key = await importRecoveryKey(recoveryCode);
  const iv = randomBytes(12);
  const createdAt = new Date().toISOString();
  const plaintext = encoder.encode(JSON.stringify({
    scope,
    passphrase,
    fingerprint,
    created_at: createdAt,
  }));
  const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plaintext);

  return {
    recoveryCode: displayRecoveryCode(recoveryCode),
    kit: {
      format: KIT_FORMAT,
      version: KIT_VERSION,
      scope,
      fingerprint,
      created_at: createdAt,
      algorithm: "AES-GCM",
      iv: bytesToBase64(iv),
      ciphertext: bytesToBase64(new Uint8Array(encrypted)),
    },
  };
}

export function parseRecoveryKit(raw) {
  const text = typeof raw === "string" ? raw : JSON.stringify(raw);
  if (encoder.encode(text).byteLength > MAX_KIT_BYTES) throw new Error(t("privacyRecovery.kitTooLarge"));
  let kit;
  try {
    kit = typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch (_) {
    throw new Error(t("privacyRecovery.kitInvalidJson"));
  }
  if (
    !kit ||
    kit.format !== KIT_FORMAT ||
    kit.version !== KIT_VERSION ||
    !['chat', 'vault'].includes(kit.scope) ||
    !kit.fingerprint ||
    !kit.iv ||
    !kit.ciphertext
  ) {
    throw new Error(t("privacyRecovery.kitUnsupported"));
  }
  return kit;
}

export async function recoverPassphrase({ kit: rawKit, recoveryCode, expectedScope, expectedFingerprint }) {
  const kit = parseRecoveryKit(rawKit);
  if (kit.scope !== expectedScope) throw new Error(t("privacyRecovery.kitScopeMismatch"));
  if (kit.fingerprint !== expectedFingerprint) throw new Error(t("privacyRecovery.kitOldKey"));

  try {
    const key = await importRecoveryKey(recoveryCode);
    const decrypted = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: base64ToBytes(kit.iv) },
      key,
      base64ToBytes(kit.ciphertext)
    );
    const payload = JSON.parse(decoder.decode(decrypted));
    if (
      payload.scope !== expectedScope ||
      payload.fingerprint !== expectedFingerprint ||
      typeof payload.passphrase !== "string" ||
      !payload.passphrase
    ) {
      const err = new Error(t("privacyRecovery.kitPayloadInvalid"));
      err.code = "kit_payload_invalid";
      throw err;
    }
    return payload.passphrase;
  } catch (error) {
    if (error?.code === "kit_payload_invalid") throw error;
    throw new Error(t("privacyRecovery.codeOrKitCorrupt"));
  }
}

export const recoveryKitConstants = Object.freeze({
  format: KIT_FORMAT,
  version: KIT_VERSION,
  maxBytes: MAX_KIT_BYTES,
});
