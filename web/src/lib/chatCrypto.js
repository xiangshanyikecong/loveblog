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

/**
 * Browser-side crypto for the cottage 端到端加密聊天 (E2E chat).
 *
 * The server is a blind store: it only ever sees opaque ciphertext +
 * the public KDF parameters (salt / iterations) and a "verifier"
 * blob used to confirm a passphrase is correct without decrypting
 * any real message.
 *
 *   passphrase ──PBKDF2(salt, iterations, SHA-256)──▶ AES-GCM 256-bit key
 *   plaintext  ──AES-GCM(key, random iv)───────────▶ { iv, ciphertext }
 *
 * Both partners derive the same key from one shared passphrase and one shared
 * public salt. The server never holds the derived key.
 *
 * The crypto primitives are identical to ``vaultCrypto.js``; this
 * module is a thin wrapper that keeps the chat passphrases in a
 * separate ``localStorage`` slot so a compromised chat pass never
 * unlocks the vault.
 */

import {
  VAULT_DEFAULTS,
  decryptJSON,
  decryptString,
  deriveKey,
  encryptBytes,
  encryptJSON,
  encryptString,
  generateSalt,
  isCryptoAvailable,
} from "./vaultCrypto";

const VERIFIER_TOKEN = "cottage-chat::verify::v1";
const STORAGE_KEY = "love_cottage_chat_key_v1";

export const CHAT_DEFAULTS = Object.freeze({
  ...VAULT_DEFAULTS,
  // The session key material (salt + derived AES key) is cached in
  // memory and a small encrypted blob in localStorage. The derived
  // CryptoKey itself is non-extractable so it cannot be read out of
  // memory.
  verifier: VERIFIER_TOKEN,
});

// ─── helpers ───────────────────────────────────────────────────────

const cachedSession = { value: null };

function persistSession(blob) {
  try {
    if (blob == null) {
      window.localStorage.removeItem(STORAGE_KEY);
    } else {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(blob));
    }
  } catch (_) {
    /* ignore quota / private mode */
  }
}

function loadSession() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

// ─── lifecycle ────────────────────────────────────────────────────

/** True iff the local browser has a saved chat-key envelope. */
export function hasStoredChatSession() {
  return loadSession() != null;
}

/** Forget the in-memory + localStorage chat key. */
export function clearChatSession() {
  cachedSession.value = null;
  persistSession(null);
}

export function isChatCryptoAvailable() {
  return isCryptoAvailable();
}

/**
 * One-time setup: generate a salt + verifier, derive a key from the
 * passphrase, and return the public metadata + verifier blob the
 * client should POST to ``/v1/cottage/chat/keys/setup``.
 */
export async function createChatKeySetup(passphrase) {
  if (!passphrase || passphrase.length < 6) {
    throw new Error(t("chatCrypto.passphraseTooShort"));
  }
  const salt = generateSalt();
  const key = await deriveKey(passphrase, salt);
  // Re-use the same wire-format as the vault: verifier = encrypt(known
  // constant, key). The client uses this on subsequent unlocks to
  // prove it derived the right key.
  const { iv, ciphertext } = await encryptString(key, VERIFIER_TOKEN);
  // SHA-256 of the cipher text; the server uses this to dedup /
  // sanity-check, not to learn the cipher.
  const hash = await sha256Hex(ciphertext);
  return {
    publicMeta: {
      salt,
      kdf: "PBKDF2",
      kdf_hash: "SHA-256",
      iterations: CHAT_DEFAULTS.iterations,
      algo: "AES-GCM",
      verifier_iv: iv,
      verifier_cipher: ciphertext,
      verifier_hash: hash,
    },
  };
}

/**
 * Re-encrypt the KDF parameters with a new passphrase (rotates salt
 * too so the partner's next deriveKey() call uses the fresh salt).
 */
export async function createChatRekey(newPassphrase) {
  return createChatKeySetup(newPassphrase);
}

/**
 * Derive a chat key from a passphrase + the server's stored salt
 * and return an object with both the live CryptoKey (for encrypt /
 * decrypt calls) and the unlock-proof payload (so the server can
 * confirm the unlock happened).
 */
export async function unlockChatKey({ passphrase, publicMeta }) {
  if (!publicMeta?.initialized) {
    throw new Error("服务器未启用加密聊天");
  }
  const key = await deriveVerifiedChatKey(passphrase, publicMeta);
  if (!key) {
    throw new Error(t("chatCrypto.passphraseWrong"));
  }
  // Generate a fresh "proof" envelope and send it to the server.
  const proof = await encryptString(key, `${VERIFIER_TOKEN}::proof::${Date.now()}`);
  const session = {
    key,
    publicMeta,
    proof: { iv: proof.iv, cipher: proof.ciphertext },
    unlockedAt: Date.now(),
  };
  cachedSession.value = session;
  // Persist ONLY the public metadata + proof so a page reload
  // doesn't lose the unlocked state. The derived CryptoKey itself
  // is non-extractable so it can't be cached.
  persistSession({
    publicMeta,
    proof: session.proof,
    unlockedAt: session.unlockedAt,
  });
  return session;
}

/** Verify a candidate passphrase without caching an unlocked chat session. */
export async function verifyChatPassphrase(passphrase, publicMeta) {
  return (await deriveVerifiedChatKey(passphrase, publicMeta)) != null;
}

async function deriveVerifiedChatKey(passphrase, publicMeta) {
  if (!publicMeta?.initialized || !publicMeta.verifier_iv || !publicMeta.verifier_cipher) {
    return null;
  }
  try {
    const key = await deriveKey(passphrase, publicMeta.salt, {
      iterations: publicMeta.iterations,
      kdf_hash: publicMeta.kdf_hash,
    });
    const token = await decryptString(
      key,
      publicMeta.verifier_iv,
      publicMeta.verifier_cipher
    );
    return token === VERIFIER_TOKEN ? key : null;
  } catch (_) {
    return null;
  }
}

/** Re-load an unlocked session from localStorage; returns null if the
 * user has to re-enter their passphrase. */
export function restoreChatSession() {
  if (cachedSession.value) return cachedSession.value;
  const blob = loadSession();
  if (!blob) return null;
  // The CryptoKey can't be re-derived without the passphrase, so a
  // page reload always falls back to the locked state. That's the
  // intended trade-off: stronger security at the cost of one extra
  // unlock on each cold start.
  return null;
}

export function isChatUnlocked() {
  return cachedSession.value != null;
}

// ─── encrypt / decrypt ────────────────────────────────────────────

/**
 * Encrypt a UTF-8 string into the { iv, ciphertext } envelope the
 * server stores verbatim. Caller is expected to be holding a live
 * unlocked session.
 */
export async function encryptChatText(plaintext) {
  const session = requireSession();
  return encryptString(session.key, plaintext);
}

export async function decryptChatText(iv, ciphertext) {
  const session = requireSession();
  if (!iv || !ciphertext) return null;
  try {
    return await decryptString(session.key, iv, ciphertext);
  } catch (_) {
    return null;
  }
}

export async function encryptChatJSON(value) {
  const session = requireSession();
  return encryptJSON(session.key, value);
}

export async function decryptChatJSON(iv, ciphertext) {
  const session = requireSession();
  if (!iv || !ciphertext) return null;
  try {
    return await decryptJSON(session.key, iv, ciphertext);
  } catch (_) {
    return null;
  }
}

/**
 * Encrypt raw bytes (ArrayBuffer) for E2E media messages (image / voice).
 * Returns { iv, ciphertext } (both base64). The encrypted blob is uploaded as a
 * file; only the iv is sent in the chat message envelope.
 */
export async function encryptChatBytes(plaintext) {
  const session = requireSession();
  return encryptBytes(session.key, plaintext);
}

/**
 * Like encryptChatBytes but returns the raw encrypted ArrayBuffer (no base64
 * round-trip). Use this when you need to upload the encrypted bytes directly
 * as a Blob – avoids encoding to base64 then immediately decoding back.
 * Returns { iv (base64 string for the chat envelope), cipherBuffer (ArrayBuffer) }.
 */
export async function encryptChatRaw(plaintext) {
  const session = requireSession();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const cipherBuffer = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    session.key,
    plaintext
  );
  // IV needs to be base64 for the chat message envelope.
  let ivBinary = "";
  for (let i = 0; i < iv.length; i += 1) ivBinary += String.fromCharCode(iv[i]);
  return { iv: btoa(ivBinary), cipherBuffer };
}

/**
 * Decrypt an E2E media payload. `ciphertextBytes` is the raw encrypted file
 * content (ArrayBuffer fetched from media_url); `ivB64` is the envelope IV.
 * Returns the decrypted ArrayBuffer.
 */
export async function decryptChatBytes(ivB64, ciphertextBytes) {
  const session = requireSession();
  if (!ivB64) throw new Error(t("chatCrypto.missingIv"));
  const iv = Uint8Array.from(atob(ivB64), (c) => c.charCodeAt(0));
  return crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    session.key,
    ciphertextBytes
  );
}

function requireSession() {
  if (!cachedSession.value) {
    throw new Error(t("chatCrypto.chatLocked"));
  }
  return cachedSession.value;
}

// ─── low-level ─────────────────────────────────────────────────────

async function sha256Hex(text) {
  const buf = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
